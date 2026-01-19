"""Router Workflow - routes to a single worker agent for simple tasks.

This workflow is designed for straightforward tasks that can be handled by
a single agent. It selects the most appropriate agent from the available
pool and delegates the entire task to that agent.

Use cases:
    - Simple Q&A tasks
    - Single-domain queries
    - Tasks with clear, unambiguous requirements
"""

import time
from typing import Any

from kiva.state import OrchestratorState
from kiva.workflows.utils import (
    create_workflow_factory,
    emit_stream_event,
    extract_content,
    generate_invocation_id,
    get_agent_by_id,
)


async def router_workflow(state: OrchestratorState) -> dict[str, Any]:
    """Route and execute a task using a single worker agent.

    Selects the first assigned agent and delegates the complete task to it.
    Emits streaming events for observability and handles errors gracefully.

    Args:
        state: The orchestrator state containing task assignments, agents,
            execution ID, and prompt.

    Returns:
        Dictionary with 'agent_results' containing a single result entry.
    """
    task_assignments = state.get("task_assignments", [])
    agents = state.get("agents", [])
    execution_id = state.get("execution_id", "")

    if not task_assignments:
        return {
            "agent_results": [
                {
                    "agent_id": "unknown",
                    "result": None,
                    "error": "No task assignments provided",
                }
            ]
        }

    if not agents:
        return {
            "agent_results": [
                {"agent_id": "unknown", "result": None, "error": "No agents available"}
            ]
        }

    assignment = task_assignments[0]
    agent_id = assignment.get("agent_id", "agent_0")
    task = assignment.get("task", state.get("prompt", ""))
    invocation_id = generate_invocation_id(execution_id, agent_id)

    # Create factory for event emission
    factory = create_workflow_factory(execution_id)
    workflow_start_time = time.time()

    # Router uses fallback_first=True to ensure a valid agent is selected
    agent = get_agent_by_id(agents, agent_id, fallback_first=True)
    if agent is None:
        return {
            "agent_results": [
                {
                    "agent_id": agent_id,
                    "invocation_id": invocation_id,
                    "result": None,
                    "error": f"Agent '{agent_id}' not found",
                }
            ]
        }

    # Emit workflow_start event
    emit_stream_event(
        factory.workflow_start(
            workflow="router",
            agent_ids=[agent_id],
            iteration=1,
        )
    )

    try:
        agent_start_time = time.time()

        # Emit agent_start event
        emit_stream_event(
            factory.agent_start(
                agent_id=agent_id,
                invocation_id=invocation_id,
                task=task,
                iteration=1,
            )
        )

        result = await agent.ainvoke({"messages": [{"role": "user", "content": task}]})
        content = extract_content(result)

        agent_duration_ms = int((time.time() - agent_start_time) * 1000)

        # Emit agent_end event
        emit_stream_event(
            factory.agent_end(
                agent_id=agent_id,
                invocation_id=invocation_id,
                result=content[:500] if content else "",
                duration_ms=agent_duration_ms,
                success=True,
            )
        )

        workflow_duration_ms = int((time.time() - workflow_start_time) * 1000)

        # Emit workflow_end event
        emit_stream_event(
            factory.workflow_end(
                workflow="router",
                success=True,
                results_count=1,
                duration_ms=workflow_duration_ms,
                conflicts_found=0,
            )
        )

        return {
            "agent_results": [
                {
                    "agent_id": agent_id,
                    "invocation_id": invocation_id,
                    "result": content,
                }
            ]
        }

    except Exception as e:
        from kiva.exceptions import wrap_agent_error

        error = wrap_agent_error(e, agent_id, task)

        # Emit agent_error event
        emit_stream_event(
            factory.agent_error(
                agent_id=agent_id,
                invocation_id=invocation_id,
                error_type=type(e).__name__,
                error_message=str(error),
                recovery_suggestion=error.recovery_suggestion,
            )
        )

        workflow_duration_ms = int((time.time() - workflow_start_time) * 1000)

        # Emit workflow_end event with failure
        emit_stream_event(
            factory.workflow_end(
                workflow="router",
                success=False,
                results_count=0,
                duration_ms=workflow_duration_ms,
                conflicts_found=0,
            )
        )

        return {
            "agent_results": [
                {
                    "agent_id": agent_id,
                    "invocation_id": invocation_id,
                    "result": None,
                    "error": str(error),
                    "original_error_type": type(e).__name__,
                    "recovery_suggestion": error.recovery_suggestion,
                }
            ]
        }
