"""Agent instance executor for parallel execution.

This module provides the execution node for individual agent instances
spawned via the Send API. Each instance runs with isolated context.
"""

import time
from typing import Any

from langchain_core.runnables import RunnableConfig

from kiva.state import AgentInstanceState
from kiva.workflows.utils import (
    create_workflow_factory,
    emit_stream_event,
    execute_agent_instance,
    get_agent_by_id,
)


async def execute_instance_node(
    state: AgentInstanceState, config: RunnableConfig | None = None
) -> dict[str, Any]:
    """Execute a single agent instance with isolated context.

    This node is invoked via Send from the routing logic. Each instance
    has its own context/scratchpad and executes independently.

    Args:
        state: The AgentInstanceState containing instance-specific data.
        config: Optional LangGraph config with parent state access.

    Returns:
        Dictionary with agent_results and instance_contexts to merge
        back into the parent OrchestratorState.
    """
    instance_id = state.get("instance_id", "")
    agent_id = state.get("agent_id", "")
    task = state.get("task", "")
    context = state.get("context", {})
    execution_id = state.get("execution_id", "")
    worker_max_iterations = state.get("worker_max_iterations", 100)
    max_retries = state.get("max_retries", 3)

    # Get agents from configurable or use empty list
    # Note: In Send-based execution, we need to pass agents via config
    agents = []
    if config and "configurable" in config:
        agents = config["configurable"].get("agents", [])

    factory = create_workflow_factory(execution_id)
    instance_num = context.get("instance_num", 0)

    # Emit instance_spawn event using new format
    emit_stream_event(
        factory.instance_spawn(
            instance_id=instance_id,
            agent_id=agent_id,
            task=task,
            instance_num=instance_num,
            context=context,
        )
    )

    agent = get_agent_by_id(agents, agent_id)
    if agent is None:
        # Emit instance_error for missing agent
        emit_stream_event(
            factory.instance_error(
                instance_id=instance_id,
                agent_id=agent_id,
                error_type="AgentNotFoundError",
                error_message=f"Agent '{agent_id}' not found",
            )
        )
        error_result = {
            "instance_id": instance_id,
            "agent_id": agent_id,
            "result": None,
            "error": f"Agent '{agent_id}' not found",
            "context": context,
        }
        return {
            "agent_results": [error_result],
            "instance_contexts": [context],
        }

    start_time = time.time()
    result = await execute_agent_instance(
        agent=agent,
        instance_id=instance_id,
        agent_id=agent_id,
        task=task,
        context=context,
        execution_id=execution_id,
        worker_max_iterations=worker_max_iterations,
        max_retries=max_retries,
    )

    duration_ms = int((time.time() - start_time) * 1000)
    success = result.get("error") is None

    # Emit instance completion event (instance_end is already emitted in
    # execute_agent_instance, but we emit a summary event here)
    if success:
        emit_stream_event(
            factory.instance_end(
                instance_id=instance_id,
                agent_id=agent_id,
                result=result.get("result", "")[:500] if result.get("result") else "",
                duration_ms=duration_ms,
                success=True,
            )
        )

    return {
        "agent_results": [result],
        "instance_contexts": [result.get("context", context)],
    }


async def execute_instances_batch(
    instances: list[dict],
    agents: list,
    execution_id: str,
) -> list[dict[str, Any]]:
    """Execute multiple agent instances in parallel.

    This is a utility function for workflows that need to execute
    multiple instances without using the Send API directly.

    Args:
        instances: List of instance configurations with agent_id, task, context.
        agents: List of available agent definitions.
        execution_id: Parent execution ID for correlation.

    Returns:
        List of result dictionaries from all instances.
    """
    import asyncio

    from kiva.workflows.utils import (
        create_instance_context,
        generate_instance_id,
    )

    factory = create_workflow_factory(execution_id)
    tasks = []

    for i, inst in enumerate(instances):
        agent_id = inst.get("agent_id", f"agent_{i}")
        task = inst.get("task", "")
        base_context = inst.get("context", {})

        instance_id = generate_instance_id(execution_id, agent_id, i)
        context = create_instance_context(instance_id, agent_id, task, base_context)

        # Emit instance_spawn event
        emit_stream_event(
            factory.instance_spawn(
                instance_id=instance_id,
                agent_id=agent_id,
                task=task,
                instance_num=i,
                context=context,
            )
        )

        agent = get_agent_by_id(agents, agent_id)
        if agent is None:
            # Create error result for missing agent
            async def make_error(
                aid: str = agent_id,
                iid: str = instance_id,
                ctx: dict = context,
            ) -> dict[str, Any]:
                # Emit instance_error event
                emit_stream_event(
                    factory.instance_error(
                        instance_id=iid,
                        agent_id=aid,
                        error_type="AgentNotFoundError",
                        error_message=f"Agent '{aid}' not found",
                    )
                )
                return {
                    "instance_id": iid,
                    "agent_id": aid,
                    "result": None,
                    "error": f"Agent '{aid}' not found",
                    "context": ctx,
                }

            tasks.append(make_error())
        else:
            tasks.append(
                execute_agent_instance(
                    agent=agent,
                    instance_id=instance_id,
                    agent_id=agent_id,
                    task=task,
                    context=context,
                    execution_id=execution_id,
                )
            )

    results = await asyncio.gather(*tasks, return_exceptions=True)

    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            agent_id = instances[i].get("agent_id", f"agent_{i}")
            instance_id = f"error-{i}"

            # Emit instance_error event for exception
            emit_stream_event(
                factory.instance_error(
                    instance_id=instance_id,
                    agent_id=agent_id,
                    error_type=type(result).__name__,
                    error_message=str(result),
                )
            )

            processed_results.append(
                {
                    "instance_id": instance_id,
                    "agent_id": agent_id,
                    "result": None,
                    "error": str(result),
                }
            )
        else:
            processed_results.append(result)

    return processed_results
