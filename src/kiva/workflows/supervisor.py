"""Supervisor Workflow - coordinates multiple agents with instance support.

This workflow manages parallel execution of multiple agents, each handling
a portion of the overall task. Now supports spawning multiple instances
of the same agent for parallel subtask processing.

Use cases:
    - Multi-faceted research tasks
    - Parallel data processing
    - Tasks requiring diverse expertise without conflict resolution
    - Map-reduce style operations with multiple instances
"""

import time
from typing import Any

from kiva.state import OrchestratorState
from kiva.workflows.executor import execute_instances_batch
from kiva.workflows.utils import (
    create_workflow_factory,
    emit_stream_event,
    execute_single_agent,
    generate_batch_id,
    generate_invocation_id,
    get_agent_by_id,
    make_error_result,
)


async def supervisor_workflow(state: OrchestratorState) -> dict[str, Any]:
    """Execute multiple worker agents/instances under supervisor coordination.

    Distributes task assignments across available agents, supporting both
    single-instance and multi-instance execution patterns. When instances > 1
    for an assignment, spawns multiple parallel instances of the same agent.

    Args:
        state: The orchestrator state containing:
            - task_assignments: List of {agent_id, task, instances} dictionaries
            - agents: List of available agent instances
            - max_parallel_agents: Maximum concurrent executions (default: 5)
            - execution_id: Parent execution identifier
            - prompt: Fallback prompt if task not specified
            - parallel_strategy: "none", "fan_out", or "map_reduce"

    Returns:
        Dictionary with 'agent_results' containing results from all agents/instances.
    """
    task_assignments = state.get("task_assignments", [])
    agents = state.get("agents", [])
    max_parallel = state.get("max_parallel_agents", 5)
    execution_id = state.get("execution_id", "")
    parallel_strategy = state.get("parallel_strategy", "none")

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

    # Check if we need multi-instance execution
    needs_instances = parallel_strategy in ("fan_out", "map_reduce") or any(
        a.get("instances", 1) > 1 for a in task_assignments
    )

    if needs_instances:
        return await _execute_with_instances(
            task_assignments, agents, max_parallel, execution_id, state
        )
    else:
        return await _execute_single_agents(
            task_assignments, agents, max_parallel, execution_id, state
        )


async def _execute_with_instances(
    task_assignments: list[dict],
    agents: list,
    max_parallel: int,
    execution_id: str,
    state: OrchestratorState,
) -> dict[str, Any]:
    """Execute with multi-instance support.

    Expands task assignments into individual instances and executes them
    in parallel batches.
    """
    factory = create_workflow_factory(execution_id)
    batch_id = generate_batch_id(execution_id)
    batch_start_time = time.time()

    # Expand assignments into instances
    instances = []
    for assignment in task_assignments:
        agent_id = assignment.get("agent_id", "agent_0")
        task = assignment.get("task", state.get("prompt", ""))
        num_instances = min(assignment.get("instances", 1), max_parallel)
        base_context = assignment.get("instance_context", {})

        for i in range(num_instances):
            instances.append(
                {
                    "agent_id": agent_id,
                    "task": task,
                    "context": {**base_context, "instance_num": i},
                }
            )

            if len(instances) >= max_parallel:
                break

        if len(instances) >= max_parallel:
            break

    # Get unique agent IDs
    agent_ids = list({inst["agent_id"] for inst in instances})

    # Emit parallel_start event using new format
    emit_stream_event(
        factory.parallel_start(
            batch_id=batch_id,
            agent_ids=agent_ids,
            instance_count=len(instances),
            strategy=state.get("parallel_strategy", "fan_out"),
        )
    )

    # Execute all instances
    results = await execute_instances_batch(instances, agents, execution_id)

    # Convert instance results to agent_results format
    agent_results = []
    instance_contexts = []
    success_count = 0
    failure_count = 0

    for result in results:
        has_error = result.get("error") is not None
        if has_error:
            failure_count += 1
        else:
            success_count += 1

        agent_results.append(
            {
                "agent_id": result.get("agent_id"),
                "instance_id": result.get("instance_id"),
                "invocation_id": result.get(
                    "instance_id"
                ),  # Use instance_id as invocation_id
                "result": result.get("result"),
                "error": result.get("error"),
            }
        )
        if ctx := result.get("context"):
            instance_contexts.append(ctx)

    batch_duration_ms = int((time.time() - batch_start_time) * 1000)

    # Emit parallel_complete event using new format
    emit_stream_event(
        factory.parallel_complete(
            batch_id=batch_id,
            results=[
                {
                    "agent_id": r.get("agent_id"),
                    "instance_id": r.get("instance_id"),
                    "success": r.get("error") is None,
                }
                for r in agent_results
            ],
            success_count=success_count,
            failure_count=failure_count,
            duration_ms=batch_duration_ms,
        )
    )

    return {
        "agent_results": agent_results,
        "instance_contexts": instance_contexts,
    }


async def _execute_single_agents(
    task_assignments: list[dict],
    agents: list,
    max_parallel: int,
    execution_id: str,
    state: OrchestratorState,
) -> dict[str, Any]:
    """Execute single-instance agents (original behavior)."""
    import asyncio

    factory = create_workflow_factory(execution_id)
    batch_id = generate_batch_id(execution_id)
    batch_start_time = time.time()

    agent_ids = [
        a.get("agent_id", f"agent_{i}") for i, a in enumerate(task_assignments)
    ]

    # Emit parallel_start event using new format
    emit_stream_event(
        factory.parallel_start(
            batch_id=batch_id,
            agent_ids=agent_ids,
            instance_count=len(agent_ids),
            strategy=state.get("parallel_strategy", "none"),
        )
    )

    tasks = []
    for i, assignment in enumerate(task_assignments[:max_parallel]):
        agent_id = assignment.get("agent_id", f"agent_{i}")
        task = assignment.get("task", state.get("prompt", ""))
        agent = get_agent_by_id(agents, agent_id)

        if agent is None:
            invocation_id = generate_invocation_id(execution_id, agent_id)
            tasks.append(make_error_result(agent_id, invocation_id))
        else:
            tasks.append(execute_single_agent(agent, agent_id, task, execution_id))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    agent_results = []
    success_count = 0
    failure_count = 0

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            agent_id = (
                task_assignments[i].get("agent_id", f"agent_{i}")
                if i < len(task_assignments)
                else f"agent_{i}"
            )
            invocation_id = generate_invocation_id(execution_id, agent_id)
            agent_results.append(
                {
                    "agent_id": agent_id,
                    "invocation_id": invocation_id,
                    "result": None,
                    "error": str(result),
                }
            )
            failure_count += 1
        else:
            agent_results.append(result)
            if result.get("error") is None:
                success_count += 1
            else:
                failure_count += 1

    batch_duration_ms = int((time.time() - batch_start_time) * 1000)

    # Emit parallel_complete event using new format
    emit_stream_event(
        factory.parallel_complete(
            batch_id=batch_id,
            results=[
                {"agent_id": r.get("agent_id"), "success": r.get("error") is None}
                for r in agent_results
            ],
            success_count=success_count,
            failure_count=failure_count,
            duration_ms=batch_duration_ms,
        )
    )

    return {"agent_results": agent_results}
