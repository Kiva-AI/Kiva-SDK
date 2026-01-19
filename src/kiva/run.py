"""SDK entry point - the run() function.

This module provides the main entry point for running multi-agent orchestration.
The run() function is an async generator that yields StreamEvent objects for
real-time monitoring of execution progress, including instance-level events.

Example:
    >>> async for event in run(prompt="...", agents=[...]):
    ...     if event.type == EventType.EXECUTION_END:
    ...         print(event.data["result"])
"""

import uuid
from collections.abc import AsyncIterator
from typing import Any

from kiva.events import (
    EventFactory,
    EventPhase,
    EventType,
    StreamEvent,
)
from kiva.exceptions import ConfigurationError
from kiva.graph import build_orchestrator_graph


def _should_emit(event_type: EventType, filter_set: set[EventType] | None) -> bool:
    """Check if event should be emitted based on filter.

    This function is designed to be called BEFORE event creation to avoid
    unnecessary object allocations when events will be filtered out.

    Args:
        event_type: The type of event to check.
        filter_set: Optional set of event types to emit. If None, all events
            are emitted.

    Returns:
        True if the event should be emitted, False otherwise.
    """
    return filter_set is None or event_type in filter_set


async def run(
    prompt: str,
    agents: list[Any],
    *,
    model_name: str = "gpt-4o",
    api_key: str | None = None,
    base_url: str | None = None,
    workflow_override: str | None = None,
    max_iterations: int = 10,
    worker_max_iterations: int = 100,
    max_retries: int = 3,
    max_parallel_agents: int = 5,
    event_filter: set[EventType] | None = None,
) -> AsyncIterator[StreamEvent]:
    """Run multi-agent orchestration and yield streaming events.

    This is the main entry point for the Kiva SDK. It analyzes the task,
    selects an appropriate workflow, optionally spawns multiple agent
    instances for parallel execution, and synthesizes results.

    Args:
        prompt: User input or task description.
        agents: List of worker agents. Each agent must have an `ainvoke` method.
        model_name: Model identifier for the lead agent. Defaults to "gpt-4o".
        api_key: API authentication key. Optional.
        base_url: API endpoint URL. Optional.
        workflow_override: Force a specific workflow ("router", "supervisor",
            "parliament"). If None, workflow is selected automatically.
        max_iterations: Maximum iterations for parliament workflow. Defaults to 10.
        worker_max_iterations: Maximum iterations for worker agents. Defaults to 100.
        max_retries: Maximum retry attempts for failed worker agents. Defaults to 3.
        max_parallel_agents: Maximum concurrent agent executions. Defaults to 5.
        event_filter: Optional set of EventType values to filter which events are
            emitted. If None, all events are emitted. Use this to subscribe to
            specific event types only.

    Yields:
        StreamEvent objects representing execution progress, including:
        - execution_start/end/error: Lifecycle events
        - phase_change: Phase transition events
        - planning_start/progress/complete: Planning events
        - workflow_selected/start/end: Workflow events
        - agent_start/progress/end/error/retry: Agent events
        - instance_spawn/start/progress/end/error/retry: Instance events
        - parallel_start/progress/complete: Parallel execution events
        - synthesis_start/progress/complete: Synthesis events
        - token: Streaming token events
        - tool_call_start/end: Tool call events

    Raises:
        ConfigurationError: If agents list is empty or agents lack ainvoke method.

    Example:
        >>> from kiva import run, create_agent, ChatOpenAI, tool
        >>> from kiva.events import EventType
        >>>
        >>> @tool
        ... def search(query: str) -> str:
        ...     '''Search for information.'''
        ...     return f"Results for {query}"
        >>>
        >>> model = ChatOpenAI(model="gpt-4o", api_key="...")
        >>> agent = create_agent(model=model, tools=[search])
        >>> agent.name = "searcher"
        >>> agent.description = "Searches for information"
        >>>
        >>> # Get all events
        >>> async for event in run("Search for Python", agents=[agent]):
        ...     print(event.type)
        >>>
        >>> # Filter to specific event types
        >>> filter_set = {EventType.EXECUTION_START, EventType.EXECUTION_END}
        >>> async for event in run("Search", agents=[agent], event_filter=filter_set):
        ...     print(event.type)
    """
    if not agents:
        raise ConfigurationError("agents list cannot be empty")

    for i, agent in enumerate(agents):
        if not hasattr(agent, "ainvoke"):
            raise ConfigurationError(
                f"Agent at index {i} must have ainvoke method. "
                f"Please use create_agent() to create agents."
            )

    execution_id = str(uuid.uuid4())
    factory = EventFactory(execution_id)
    graph = build_orchestrator_graph()

    # Build execution config
    config_data = {
        "model_name": model_name,
        "max_iterations": max_iterations,
        "worker_max_iterations": worker_max_iterations,
        "max_retries": max_retries,
        "max_parallel_agents": max_parallel_agents,
    }

    # Emit execution_start event - check filter before creating
    if _should_emit(EventType.EXECUTION_START, event_filter):
        yield factory.execution_start(prompt, agents, config_data)

    # Phase change: initializing -> analyzing - check filter before creating
    if _should_emit(EventType.PHASE_CHANGE, event_filter):
        yield factory.phase_change(
            EventPhase.INITIALIZING,
            EventPhase.ANALYZING,
            10,
            "Starting task analysis",
        )

    initial_state = {
        "prompt": prompt,
        "agents": agents,
        "messages": [],
        "agent_results": [],
        "execution_id": execution_id,
        "conflicts": [],
        "iteration": 0,
        "model_name": model_name,
        "api_key": api_key,
        "base_url": base_url,
        "workflow_override": workflow_override,
        "max_iterations": max_iterations,
        "worker_max_iterations": worker_max_iterations,
        "max_retries": max_retries,
        "max_parallel_agents": max_parallel_agents,
        "complexity": "",
        "workflow": "",
        "task_assignments": [],
        "final_result": None,
        "parallel_strategy": "none",
        "total_instances": 0,
        "instance_contexts": [],
    }

    # Pass agents via configurable for Send-based instance execution
    config = {"configurable": {"agents": agents}}

    final_result = None
    agent_results_count = 0

    try:
        async for chunk in graph.astream(
            initial_state, config=config, stream_mode=["messages", "updates", "custom"]
        ):
            async for event in _process_stream_chunk(chunk, factory, event_filter):
                # Track final result for execution_end event
                if event.type == EventType.SYNTHESIS_COMPLETE:
                    final_result = event.data.get("result", "")
                elif event.type == EventType.WORKFLOW_END:
                    agent_results_count = event.data.get("results_count", 0)
                yield event

        # Emit execution_end event on success - check filter before creating
        if _should_emit(EventType.EXECUTION_END, event_filter):
            yield factory.execution_end(
                result=final_result or "",
                agent_results_count=agent_results_count,
                success=True,
            )

    except Exception as e:
        # Emit execution_error event - check filter before creating
        if _should_emit(EventType.EXECUTION_ERROR, event_filter):
            import traceback

            yield factory.execution_error(
                error_type=type(e).__name__,
                error_message=str(e),
                stack_trace=traceback.format_exc(),
                recovery_suggestion=_get_recovery_suggestion(e),
            )
        raise


def _get_recovery_suggestion(error: Exception) -> str | None:
    """Get a recovery suggestion based on the error type.

    Args:
        error: The exception that occurred.

    Returns:
        A suggested recovery action, or None if no suggestion is available.
    """
    suggestions = {
        "ConfigurationError": "Check agent configuration.",
        "TimeoutError": "Increase timeout or reduce task complexity.",
        "ConnectionError": "Check network connection and API endpoint.",
        "AuthenticationError": "Verify API key and permissions.",
        "RateLimitError": "Wait and retry, or reduce parallel agents.",
    }
    return suggestions.get(type(error).__name__)


async def _process_stream_chunk(
    chunk: tuple[str, Any],
    factory: EventFactory,
    event_filter: set[EventType] | None,
) -> AsyncIterator[StreamEvent]:
    """Process a stream chunk and yield StreamEvent objects.

    Checks event filter BEFORE creating events to avoid unnecessary allocations.
    """
    mode, data = chunk

    if mode == "messages":
        # Check filter before creating token event
        if not _should_emit(EventType.TOKEN, event_filter):
            return
        msg_chunk, metadata = data
        if content := getattr(msg_chunk, "content", ""):
            yield factory.token(
                content=content,
                agent_id=metadata.get("langgraph_node"),
            )

    elif mode == "updates" and isinstance(data, dict):
        for node_name, node_data in data.items():
            if isinstance(node_data, dict):
                async for event in _process_node_update(
                    node_name, node_data, factory, event_filter
                ):
                    yield event

    elif mode == "custom" and isinstance(data, dict):
        # Workflows emit StreamEvent.to_dict(), reconstruct with monotonic timestamp
        try:
            event_type = EventType(data.get("type", ""))
            # Check filter before reconstructing event
            if _should_emit(event_type, event_filter):
                # Reconstruct event but use factory's monotonic timestamp
                # to ensure all events have strictly increasing timestamps
                event = StreamEvent.from_dict(data)
                # Override timestamp with monotonic timestamp from main factory
                object.__setattr__(
                    event, "timestamp", factory._get_monotonic_timestamp()
                )
                yield event
        except (KeyError, ValueError):
            pass  # Ignore malformed events


async def _process_node_update(
    node_name: str,
    node_data: dict[str, Any],
    factory: EventFactory,
    event_filter: set[EventType] | None,
) -> AsyncIterator[StreamEvent]:
    """Process a node update and yield appropriate StreamEvent objects.

    Checks event filter BEFORE creating events to avoid unnecessary allocations.
    """
    if node_name == "analyze_and_plan":
        # Planning start (when workflow not yet determined)
        if "workflow" not in node_data and "complexity" not in node_data:
            # Check filter before creating planning_start event
            if _should_emit(EventType.PLANNING_START, event_filter):
                agents_info = [
                    {"name": getattr(a, "name", f"agent_{i}")}
                    for i, a in enumerate(node_data.get("agents", []))
                ]
                yield factory.planning_start(
                    prompt=node_data.get("prompt", ""),
                    available_agents=agents_info,
                )

        # Planning complete (when workflow is determined)
        if workflow := node_data.get("workflow"):
            # Check filter before creating phase_change event
            if _should_emit(EventType.PHASE_CHANGE, event_filter):
                yield factory.phase_change(
                    EventPhase.ANALYZING, EventPhase.EXECUTING, 30, "Planning complete"
                )

            # Check filter before creating planning_complete event
            if _should_emit(EventType.PLANNING_COMPLETE, event_filter):
                yield factory.planning_complete(
                    complexity=node_data.get("complexity", ""),
                    workflow=workflow,
                    reasoning=node_data.get("reasoning", ""),
                    task_assignments=node_data.get("task_assignments", []),
                    parallel_strategy=node_data.get("parallel_strategy"),
                    total_instances=node_data.get("total_instances", 0),
                )

            # Check filter before creating workflow_selected event
            if _should_emit(EventType.WORKFLOW_SELECTED, event_filter):
                yield factory.workflow_selected(
                    workflow=workflow,
                    complexity=node_data.get("complexity", ""),
                    task_assignments=node_data.get("task_assignments", []),
                    parallel_strategy=node_data.get("parallel_strategy"),
                    total_instances=node_data.get("total_instances", 1),
                )

    elif node_name == "synthesize_results":
        final_result = node_data.get("final_result", "")
        partial_info = node_data.get("partial_result_info", {})

        if final_result is not None:
            is_executing = factory.current_phase == EventPhase.EXECUTING
            # Check filter before creating phase_change event
            if is_executing and _should_emit(EventType.PHASE_CHANGE, event_filter):
                yield factory.phase_change(
                    EventPhase.EXECUTING, EventPhase.SYNTHESIZING, 75, "Synthesizing"
                )

            success_count = partial_info.get("success_count", 0)
            failure_count = partial_info.get("failure_count", 0)

            # Check filter before creating synthesis_start event
            if _should_emit(EventType.SYNTHESIS_START, event_filter):
                yield factory.synthesis_start(
                    success_count + failure_count, success_count, failure_count
                )

            # Check filter before creating synthesis_complete event
            if _should_emit(EventType.SYNTHESIS_COMPLETE, event_filter):
                citations = node_data.get("citations") or _extract_citations(
                    final_result or ""
                )
                yield factory.synthesis_complete(
                    result=final_result,
                    citations=[str(c) for c in citations] if citations else [],
                    is_partial=partial_info.get("is_partial", False),
                    duration_ms=0,
                )

            # Check filter before creating phase_change event
            if _should_emit(EventType.PHASE_CHANGE, event_filter):
                yield factory.phase_change(
                    EventPhase.SYNTHESIZING, EventPhase.COMPLETE, 100, "Complete"
                )


def _extract_citations(result: str) -> list[dict[str, str]]:
    """Extract citations from the final result text."""
    from kiva.nodes.synthesize import extract_citations

    return extract_citations(result)
