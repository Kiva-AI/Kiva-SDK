"""Analyze and plan node for the Lead Agent.

This module implements the task analysis, intent detection, and workflow
selection logic. Uses async streaming for real-time token output.
"""

import json
import re
import time
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from kiva.events import EventFactory, EventPhase
from kiva.state import OrchestratorState, PlanningResult, TaskAssignment
from kiva.workflows.utils import emit_stream_event

ANALYZE_SYSTEM_PROMPT = """You are a task coordinator. Analyze user requests.

## Complexity: simple | medium | complex
## Workflow: router | supervisor | parliament
## Parallel Strategy: none | fan_out | map_reduce

## Available Agents
{agent_descriptions}

## Output JSON (no markdown)
{{"complexity":"...","workflow":"...","parallel_strategy":"...","reasoning":"...","task_assignments":[{{"agent_id":"...","task":"...","instances":1}}],"total_instances":N}}"""


def _get_agent_descriptions(agents: list) -> str:
    """Extract descriptions from agents for the system prompt."""
    if not agents:
        return "No agents available"
    return "\n".join(
        f"- {getattr(a, 'name', None) or f'agent_{i}'}: "
        f"{getattr(a, 'description', 'No description available')}"
        for i, a in enumerate(agents)
    )


def _parse_json_response(content: str) -> PlanningResult:
    """Parse JSON from LLM response, handling markdown code blocks."""
    if match := re.search(r"```(?:json)?\s*([\s\S]*?)```", content):
        content = match.group(1).strip()
    try:
        parsed = json.loads(content)
        return PlanningResult(
            complexity=parsed.get("complexity", "simple"),
            workflow=parsed.get("workflow", "router"),
            reasoning=parsed.get("reasoning", ""),
            task_assignments=parsed.get("task_assignments", []),
            parallel_strategy=parsed.get("parallel_strategy", "none"),
            total_instances=parsed.get("total_instances", 1),
        )
    except json.JSONDecodeError:
        return PlanningResult(
            complexity="simple",
            workflow="router",
            reasoning="Failed to parse response",
            task_assignments=[],
            parallel_strategy="none",
            total_instances=1,
        )


def _normalize_task_assignments(
    assignments: list[dict], agents: list, prompt: str, max_parallel: int
) -> tuple[list[TaskAssignment], int]:
    """Normalize and validate task assignments."""
    if not assignments and agents:
        agent_id = getattr(agents[0], "name", None) or "agent_0"
        return [TaskAssignment(agent_id=agent_id, task=prompt, instances=1)], 1

    normalized = []
    total_instances = 0

    for assignment in assignments:
        instances = min(
            max(1, assignment.get("instances", 1)), max_parallel - total_instances
        )
        if total_instances + instances > max_parallel:
            instances = max(1, max_parallel - total_instances)

        normalized.append(
            TaskAssignment(
                agent_id=assignment.get("agent_id", "agent_0"),
                task=assignment.get("task", prompt),
                instances=instances,
                instance_context=assignment.get("instance_context", {}),
            )
        )
        total_instances += instances
        if total_instances >= max_parallel:
            break

    return normalized, total_instances


async def analyze_and_plan(state: OrchestratorState) -> dict[str, Any]:
    """Lead Agent analyzes user intent and plans execution strategy.

    Uses async streaming for real-time token output during planning.
    """
    from langchain_openai import ChatOpenAI

    execution_id = state.get("execution_id", "")
    factory = EventFactory(execution_id)
    factory.set_phase(EventPhase.ANALYZING)

    start_time = time.time()

    model_kwargs = {"model": state.get("model_name", "gpt-4o")}
    if api_key := state.get("api_key"):
        model_kwargs["api_key"] = api_key
    if base_url := state.get("base_url"):
        model_kwargs["base_url"] = base_url

    model = ChatOpenAI(**model_kwargs)
    agents = state.get("agents", [])
    max_parallel = state.get("max_parallel_agents", 5)

    available_agents = [
        {
            "name": getattr(a, "name", None) or f"agent_{i}",
            "description": getattr(a, "description", "No description"),
        }
        for i, a in enumerate(agents)
    ]

    emit_stream_event(
        factory.planning_start(
            prompt=state["prompt"], available_agents=available_agents
        )
    )

    messages = [
        SystemMessage(
            content=ANALYZE_SYSTEM_PROMPT.format(
                agent_descriptions=_get_agent_descriptions(agents)
            )
        ),
        HumanMessage(content=state["prompt"]),
    ]

    # Stream planning with real-time token emission
    accumulated_content = ""
    async for chunk in model.astream(messages):
        if content := chunk.content:
            accumulated_content += content
            emit_stream_event(
                factory.planning_progress(
                    content=content, accumulated_content=accumulated_content
                )
            )

    result = _parse_json_response(accumulated_content)

    complexity = result.get("complexity", "simple")
    if complexity not in ("simple", "medium", "complex"):
        complexity = "simple"

    workflow = state.get("workflow_override") or result.get("workflow", "router")
    if workflow not in ("router", "supervisor", "parliament"):
        workflow = "router"

    parallel_strategy = result.get("parallel_strategy", "none")
    if parallel_strategy not in ("none", "fan_out", "map_reduce"):
        parallel_strategy = "none"

    task_assignments, total_instances = _normalize_task_assignments(
        result.get("task_assignments", []), agents, state["prompt"], max_parallel
    )

    task_assignments_dicts = [
        {
            "agent_id": ta.get("agent_id") if isinstance(ta, dict) else ta.agent_id,
            "task": ta.get("task") if isinstance(ta, dict) else ta.task,
            "instances": ta.get("instances", 1)
            if isinstance(ta, dict)
            else ta.instances,
        }
        for ta in task_assignments
    ]

    emit_stream_event(
        factory.planning_complete(
            complexity=complexity,
            workflow=workflow,
            reasoning=result.get("reasoning", ""),
            task_assignments=task_assignments_dicts,
            parallel_strategy=parallel_strategy,
            total_instances=total_instances,
            duration_ms=int((time.time() - start_time) * 1000),
        )
    )

    return {
        "complexity": complexity,
        "workflow": workflow,
        "task_assignments": task_assignments,
        "parallel_strategy": parallel_strategy,
        "total_instances": total_instances,
        "messages": [],
    }
