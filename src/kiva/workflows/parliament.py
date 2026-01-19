"""Parliament Workflow - iterative conflict resolution for complex reasoning.

This workflow implements a deliberative process where multiple agents work
on the same problem, their responses are compared for conflicts, and
disagreements are resolved through iterative refinement.

Use cases:
    - Complex reasoning tasks requiring multiple perspectives
    - Decision-making with potential for conflicting viewpoints
    - Tasks requiring validation and cross-checking
    - High-stakes outputs needing consensus
"""

import asyncio
import time
from typing import Any

from kiva.state import OrchestratorState
from kiva.workflows.utils import (
    create_workflow_factory,
    emit_stream_event,
    execute_single_agent,
    generate_batch_id,
    generate_invocation_id,
    get_agent_by_id,
    make_error_result,
)


def _identify_conflicts(agent_results: list[dict]) -> list[dict]:
    """Identify potential conflicts between agent results.

    Analyzes successful agent responses for contradictory statements by
    checking for opposing keyword pairs.

    Args:
        agent_results: List of result dictionaries from agent executions.

    Returns:
        List of conflict dictionaries with agents, type, and description.
    """
    successful = [r for r in agent_results if r.get("result") and not r.get("error")]
    if len(successful) < 2:
        return []

    conflicts = []
    contradiction_pairs = [
        ("yes", "no"),
        ("true", "false"),
        ("correct", "incorrect"),
        ("agree", "disagree"),
        ("possible", "impossible"),
    ]

    for i, r1 in enumerate(successful):
        for r2 in successful[i + 1 :]:
            c1, c2 = r1.get("result", "").lower(), r2.get("result", "").lower()
            for pos, neg in contradiction_pairs:
                if (pos in c1 and neg in c2) or (neg in c1 and pos in c2):
                    conflicts.append(
                        {
                            "agents": [r1.get("agent_id"), r2.get("agent_id")],
                            "type": "contradiction",
                            "description": (
                                f"Potential contradiction detected between "
                                f"{r1.get('agent_id')} and {r2.get('agent_id')}"
                            ),
                        }
                    )
                    break
    return conflicts


def _create_conflict_resolution_tasks(
    conflicts: list[dict], original_prompt: str, agent_results: list[dict]
) -> list[dict]:
    """Create task assignments to resolve identified conflicts.

    Generates new tasks for agents involved in conflicts, asking them to
    reconsider and justify their responses.

    Args:
        conflicts: List of conflict dictionaries from _identify_conflicts.
        original_prompt: The original user prompt/question.
        agent_results: Previous results from agent executions.

    Returns:
        List of task assignment dictionaries with agent_id and task fields.
    """
    if not conflicts:
        return []

    resolution_tasks, seen_agents = [], set()
    for conflict in conflicts:
        for agent_id in conflict.get("agents", []):
            if agent_id and agent_id not in seen_agents:
                seen_agents.add(agent_id)
                prev_result = next(
                    (
                        r.get("result", "")
                        for r in agent_results
                        if r.get("agent_id") == agent_id
                    ),
                    "",
                )
                resolution_tasks.append(
                    {
                        "agent_id": agent_id,
                        "task": (
                            "Review and verify your previous response "
                            "considering potential conflicts.\n\n"
                            f"Original question: {original_prompt}\n\n"
                            f"Your previous response: {prev_result[:500]}...\n\n"
                            "Please reconsider your answer and provide a more "
                            "detailed justification. If you find any errors in "
                            "your previous response, correct them."
                        ),
                    }
                )
    return resolution_tasks


async def _execute_agents_parallel(
    task_assignments: list[dict],
    agents: list,
    execution_id: str,
    prompt: str,
) -> list[dict]:
    """Execute multiple agents in parallel and collect results.

    Args:
        task_assignments: List of {agent_id, task} dictionaries.
        agents: List of available agent instances.
        execution_id: Parent execution identifier for correlation.
        prompt: Fallback prompt if task not specified in assignment.

    Returns:
        List of result dictionaries from all agent executions.
    """
    tasks = []
    for i, assignment in enumerate(task_assignments):
        agent_id = assignment.get("agent_id", f"agent_{i}")
        task = assignment.get("task", prompt)
        agent = get_agent_by_id(agents, agent_id)

        if agent is None:
            invocation_id = generate_invocation_id(execution_id, agent_id)
            tasks.append(
                make_error_result(
                    agent_id, invocation_id, f"Agent '{agent_id}' not found"
                )
            )
        else:
            tasks.append(execute_single_agent(agent, agent_id, task, execution_id))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    agent_results = []
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
        else:
            agent_results.append(result)
    return agent_results


async def parliament_workflow(state: OrchestratorState) -> dict[str, Any]:
    """Execute the Parliament workflow with iterative conflict resolution.

    Implements a multi-round deliberation process:
    1. First iteration: Execute all assigned agents in parallel
    2. Identify conflicts between agent responses
    3. Subsequent iterations: Ask conflicting agents to reconsider
    4. Repeat until no conflicts remain or max iterations reached

    Args:
        state: The orchestrator state containing task_assignments, agents,
            iteration count, max_iterations, conflicts, and agent_results.

    Returns:
        Updated state dictionary with agent_results, conflicts, iteration,
        and optionally workflow="synthesize" when complete.
    """
    task_assignments = state.get("task_assignments", [])
    agents = state.get("agents", [])
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 3)
    existing_conflicts = state.get("conflicts", [])
    existing_results = state.get("agent_results", [])
    prompt = state.get("prompt", "")
    execution_id = state.get("execution_id", "")

    factory = create_workflow_factory(execution_id)

    if iteration >= max_iterations:
        return {"workflow": "synthesize", "iteration": iteration}

    # First iteration: execute all assigned agents
    if iteration == 0:
        if not task_assignments:
            return {
                "agent_results": [
                    {
                        "agent_id": "unknown",
                        "result": None,
                        "error": "No task assignments provided",
                    }
                ],
                "conflicts": [],
                "iteration": 1,
            }

        if not agents:
            return {
                "agent_results": [
                    {
                        "agent_id": "unknown",
                        "result": None,
                        "error": "No agents available",
                    }
                ],
                "conflicts": [],
                "iteration": 1,
            }

        agent_ids = [
            a.get("agent_id", f"agent_{i}") for i, a in enumerate(task_assignments)
        ]
        batch_id = generate_batch_id(execution_id)
        batch_start_time = time.time()

        # Emit workflow_start event
        emit_stream_event(
            factory.workflow_start(
                workflow="parliament",
                agent_ids=agent_ids,
                iteration=iteration + 1,
            )
        )

        # Emit parallel_start event
        emit_stream_event(
            factory.parallel_start(
                batch_id=batch_id,
                agent_ids=agent_ids,
                instance_count=len(agent_ids),
                strategy="parliament",
            )
        )

        agent_results = await _execute_agents_parallel(
            task_assignments, agents, execution_id, prompt
        )
        conflicts = _identify_conflicts(agent_results)

        batch_duration_ms = int((time.time() - batch_start_time) * 1000)
        success_count = sum(1 for r in agent_results if r.get("error") is None)
        failure_count = len(agent_results) - success_count

        # Emit parallel_complete event
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

        if not conflicts:
            # Emit workflow_end event
            emit_stream_event(
                factory.workflow_end(
                    workflow="parliament",
                    success=True,
                    results_count=len(agent_results),
                    duration_ms=batch_duration_ms,
                    conflicts_found=0,
                )
            )
            return {
                "agent_results": agent_results,
                "conflicts": [],
                "iteration": iteration + 1,
                "workflow": "synthesize",
            }

        return {
            "agent_results": agent_results,
            "conflicts": conflicts,
            "iteration": iteration + 1,
        }

    # Subsequent iterations: resolve conflicts
    if existing_conflicts:
        resolution_tasks = _create_conflict_resolution_tasks(
            existing_conflicts, prompt, existing_results
        )

        if not resolution_tasks:
            return {"workflow": "synthesize", "iteration": iteration}

        agent_ids = [t.get("agent_id") for t in resolution_tasks]
        batch_id = generate_batch_id(execution_id)
        batch_start_time = time.time()

        # Emit workflow_start for conflict resolution iteration
        emit_stream_event(
            factory.workflow_start(
                workflow="parliament",
                agent_ids=agent_ids,
                iteration=iteration + 1,
            )
        )

        # Emit parallel_start event
        emit_stream_event(
            factory.parallel_start(
                batch_id=batch_id,
                agent_ids=agent_ids,
                instance_count=len(agent_ids),
                strategy="conflict_resolution",
            )
        )

        new_results = await _execute_agents_parallel(
            resolution_tasks, agents, execution_id, prompt
        )

        # Merge results
        merged_results = list(existing_results)
        for new_result in new_results:
            agent_id = new_result.get("agent_id")
            for i, existing in enumerate(merged_results):
                if existing.get("agent_id") == agent_id:
                    merged_results[i] = new_result
                    break
            else:
                merged_results.append(new_result)

        new_conflicts = _identify_conflicts(merged_results)

        batch_duration_ms = int((time.time() - batch_start_time) * 1000)
        success_count = sum(1 for r in new_results if r.get("error") is None)
        failure_count = len(new_results) - success_count

        # Emit parallel_complete event
        emit_stream_event(
            factory.parallel_complete(
                batch_id=batch_id,
                results=[
                    {"agent_id": r.get("agent_id"), "success": r.get("error") is None}
                    for r in new_results
                ],
                success_count=success_count,
                failure_count=failure_count,
                duration_ms=batch_duration_ms,
            )
        )

        if not new_conflicts or iteration + 1 >= max_iterations:
            # Emit workflow_end event
            emit_stream_event(
                factory.workflow_end(
                    workflow="parliament",
                    success=True,
                    results_count=len(merged_results),
                    duration_ms=batch_duration_ms,
                    conflicts_found=len(new_conflicts),
                )
            )
            return {
                "agent_results": merged_results,
                "conflicts": new_conflicts,
                "iteration": iteration + 1,
                "workflow": "synthesize",
            }

        return {
            "agent_results": merged_results,
            "conflicts": new_conflicts,
            "iteration": iteration + 1,
        }

    return {"workflow": "synthesize", "iteration": iteration}


def should_continue_parliament(state: OrchestratorState) -> str:
    """Determine if parliament workflow should continue or move to synthesis.

    Decision logic:
    - If workflow is explicitly set to "synthesize", proceed to synthesis
    - If max iterations reached, proceed to synthesis
    - If no conflicts remain, proceed to synthesis
    - Otherwise, continue parliament deliberation

    Args:
        state: Current orchestrator state.

    Returns:
        Either "synthesize" or "parliament_workflow" indicating next step.
    """
    if state.get("workflow") == "synthesize":
        return "synthesize"
    if state.get("iteration", 0) >= state.get("max_iterations", 3):
        return "synthesize"
    if not state.get("conflicts", []):
        return "synthesize"
    return "parliament_workflow"
