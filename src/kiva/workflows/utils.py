"""Shared utility functions for workflow implementations."""

import logging
import time
import uuid
from typing import Any

from langgraph.config import get_stream_writer

from kiva.events import EventFactory, EventPhase, StreamEvent
from kiva.exceptions import wrap_agent_error

logger = logging.getLogger(__name__)


def get_agent_by_id(
    agents: list, agent_id: str, fallback_first: bool = False
) -> Any | None:
    """Find an agent by its ID from the agents list."""
    for i, agent in enumerate(agents):
        if (getattr(agent, "name", None) or f"agent_{i}") == agent_id:
            return agent
    if agent_id.startswith("agent_") and agent_id[6:].isdigit():
        idx = int(agent_id[6:])
        if 0 <= idx < len(agents):
            return agents[idx]
    return agents[0] if fallback_first and agents else None


def generate_invocation_id(execution_id: str, agent_id: str) -> str:
    """Generate a unique invocation ID for an agent call."""
    return f"{execution_id[:8]}-{agent_id}-{uuid.uuid4().hex[:8]}"


def generate_instance_id(execution_id: str, agent_id: str, instance_num: int) -> str:
    """Generate a unique instance ID for a parallel agent instance."""
    return f"{execution_id[:8]}-{agent_id}-i{instance_num}-{uuid.uuid4().hex[:6]}"


def generate_batch_id(execution_id: str) -> str:
    """Generate a unique batch ID for parallel execution."""
    return f"{execution_id[:8]}-batch-{uuid.uuid4().hex[:8]}"


def create_instance_context(
    instance_id: str, agent_id: str, task: str, base_context: dict | None = None
) -> dict:
    """Create an isolated context for an agent instance."""
    return {
        "instance_id": instance_id,
        "agent_id": agent_id,
        "task": task,
        "scratchpad": [],
        "memory": {},
        "created_at": time.time(),
        **(base_context or {}),
    }


def emit_event(event: dict) -> None:
    """Emit a stream event to the LangGraph stream writer."""
    try:
        get_stream_writer()(event)
    except Exception as e:
        logger.debug(
            "Failed to emit stream event: %s (event type: %s)", e, event.get("type")
        )


def emit_stream_event(event: StreamEvent) -> None:
    """Emit a StreamEvent object to the LangGraph stream writer."""
    try:
        get_stream_writer()(event.to_dict())
    except Exception as e:
        logger.debug(
            "Failed to emit stream event: %s (event type: %s)",
            e,
            event.type.value if hasattr(event.type, "value") else event.type,
        )


def create_workflow_factory(execution_id: str) -> EventFactory:
    """Create an EventFactory for workflow event emission."""
    factory = EventFactory(execution_id)
    factory.set_phase(EventPhase.EXECUTING)
    return factory


def extract_content(result: Any) -> str:
    """Extract content from an agent's response result."""
    if isinstance(result, dict) and "messages" in result and result["messages"]:
        return getattr(result["messages"][-1], "content", str(result["messages"][-1]))
    return str(result)


async def execute_single_agent(
    agent: Any, agent_id: str, task: str, execution_id: str = ""
) -> dict[str, Any]:
    """Execute a single agent and return the result with event emission."""
    invocation_id = generate_invocation_id(execution_id, agent_id)
    factory = create_workflow_factory(execution_id)
    start_time = time.time()

    try:
        emit_stream_event(
            factory.agent_start(
                agent_id=agent_id, invocation_id=invocation_id, task=task, iteration=1
            )
        )
        result = await agent.ainvoke({"messages": [{"role": "user", "content": task}]})
        content = extract_content(result)
        emit_stream_event(
            factory.agent_end(
                agent_id=agent_id,
                invocation_id=invocation_id,
                result=content[:500] if content else "",
                duration_ms=int((time.time() - start_time) * 1000),
                success=True,
            )
        )
        return {"agent_id": agent_id, "invocation_id": invocation_id, "result": content}
    except Exception as e:
        error = wrap_agent_error(e, agent_id, task)
        emit_stream_event(
            factory.agent_error(
                agent_id=agent_id,
                invocation_id=invocation_id,
                error_type=type(e).__name__,
                error_message=str(error),
                recovery_suggestion=error.recovery_suggestion,
            )
        )
        return {
            "agent_id": agent_id,
            "invocation_id": invocation_id,
            "result": None,
            "error": str(error),
            "original_error_type": type(e).__name__,
            "recovery_suggestion": error.recovery_suggestion,
        }


async def execute_agent_instance(
    agent: Any,
    instance_id: str,
    agent_id: str,
    task: str,
    context: dict,
    execution_id: str = "",
    worker_max_iterations: int = 100,
    max_retries: int = 3,
) -> dict[str, Any]:
    """Execute an agent instance with isolated context and retry logic."""
    import asyncio

    factory = create_workflow_factory(execution_id)
    start_time = time.time()
    active_tool_calls: dict[str, float] = {}

    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                emit_stream_event(
                    factory.instance_retry(
                        instance_id=instance_id,
                        agent_id=agent_id,
                        attempt=attempt,
                        max_retries=max_retries,
                    )
                )
                await asyncio.sleep(min(2**attempt, 10))

            emit_stream_event(
                factory.instance_start(
                    instance_id=instance_id, agent_id=agent_id, task=task
                )
            )

            task_with_context = task
            if context.get("scratchpad"):
                task_with_context = (
                    f"{task}\n\nContext from previous steps:\n"
                    + "\n".join(str(s) for s in context["scratchpad"])
                )

            input_data = {"messages": [{"role": "user", "content": task_with_context}]}
            config = {"recursion_limit": worker_max_iterations}
            result = None

            if hasattr(agent, "astream"):
                last_state = None
                async for state_chunk in agent.astream(
                    input_data, config=config, stream_mode="values"
                ):
                    last_state = state_chunk
                    messages = state_chunk.get("messages", [])
                    if messages:
                        last_msg = messages[-1]
                        msg_type = getattr(last_msg, "type", "unknown")
                        content_preview = getattr(last_msg, "content", str(last_msg))
                        tool_calls = getattr(last_msg, "tool_calls", [])

                        emit_stream_event(
                            factory.instance_progress(
                                instance_id=instance_id,
                                agent_id=agent_id,
                                message_type=msg_type,
                                content=content_preview[:200]
                                if content_preview
                                else "",
                                tool_calls=tool_calls,
                            )
                        )

                        for tc in tool_calls:
                            call_id = tc.get("id", str(uuid.uuid4()))
                            if call_id not in active_tool_calls:
                                active_tool_calls[call_id] = time.time()
                                emit_stream_event(
                                    factory.tool_call_start(
                                        tool_name=tc.get("name", "unknown"),
                                        tool_args=tc.get("args", {}),
                                        call_id=call_id,
                                        agent_id=agent_id,
                                        instance_id=instance_id,
                                    )
                                )

                        if msg_type == "tool":
                            tool_call_id = getattr(last_msg, "tool_call_id", None)
                            if tool_call_id and tool_call_id in active_tool_calls:
                                emit_stream_event(
                                    factory.tool_call_end(
                                        tool_name=getattr(last_msg, "name", "unknown"),
                                        call_id=tool_call_id,
                                        result_preview=content_preview[:100]
                                        if content_preview
                                        else "",
                                        success=True,
                                        duration_ms=int(
                                            (
                                                time.time()
                                                - active_tool_calls[tool_call_id]
                                            )
                                            * 1000
                                        ),
                                        agent_id=agent_id,
                                        instance_id=instance_id,
                                    )
                                )
                                del active_tool_calls[tool_call_id]
                result = last_state
            else:
                result = await agent.ainvoke(input_data, config=config)

            content = extract_content(result)
            updated_context = {
                **context,
                "last_result": content,
                "completed_at": time.time(),
            }
            updated_context["scratchpad"].append({"task": task, "result": content})

            emit_stream_event(
                factory.instance_end(
                    instance_id=instance_id,
                    agent_id=agent_id,
                    result=content[:500] if content else "",
                    duration_ms=int((time.time() - start_time) * 1000),
                    success=True,
                )
            )
            return {
                "instance_id": instance_id,
                "agent_id": agent_id,
                "result": content,
                "context": updated_context,
            }

        except Exception as e:
            if attempt < max_retries:
                logger.warning(
                    f"Agent {agent_id} attempt {attempt + 1}/{max_retries + 1} failed"
                )
                continue
            error = wrap_agent_error(e, agent_id, task)
            emit_stream_event(
                factory.instance_error(
                    instance_id=instance_id,
                    agent_id=agent_id,
                    error_type=type(e).__name__,
                    error_message=str(error),
                )
            )
            return {
                "instance_id": instance_id,
                "agent_id": agent_id,
                "result": None,
                "error": str(error),
                "original_error_type": type(e).__name__,
                "recovery_suggestion": error.recovery_suggestion,
                "context": context,
            }

    return {
        "instance_id": instance_id,
        "agent_id": agent_id,
        "result": None,
        "error": "Unknown error (retries exhausted)",
        "context": context,
    }


async def make_error_result(
    agent_id: str, invocation_id: str, error_msg: str = ""
) -> dict[str, Any]:
    """Create a standardized error result dictionary."""
    return {
        "agent_id": agent_id,
        "invocation_id": invocation_id,
        "result": None,
        "error": error_msg or f"Agent '{agent_id}' not found",
    }
