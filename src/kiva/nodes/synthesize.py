"""Result synthesis node for the Kiva SDK.

This module combines outputs from multiple worker agents into a unified
final response, handling conflicts, partial results, and citation extraction.
All LLM calls use async streaming for real-time token output.
"""

import re
import time
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from kiva.events import EventFactory, EventPhase
from kiva.state import OrchestratorState
from kiva.workflows.utils import emit_stream_event

SYNTHESIZE_SYSTEM_PROMPT = """You are a result synthesis expert. \
Based on multiple expert outputs, generate a unified final response.

Requirements:
1. Resolve conflicts between outputs
2. Integrate all valuable information
3. Include source attribution (Citation) using [agent_id] format
4. Generate clear, complete final answer

Expert outputs:
{agent_results}

Please generate the final response with source attribution."""

PARTIAL_RESULT_SYSTEM_PROMPT = """You are a result synthesis expert. \
Some experts failed, but we need to generate a response based on successful results.

Requirements:
1. Generate best possible response based on successful expert outputs
2. State at the beginning that this is a partial result
3. Include source attribution (Citation) using [agent_id] format
4. If missing information is critical, note it in the response

Successful expert outputs:
{successful_results}

Failed experts:
{failed_agents}

Please generate the final response with source attribution."""


def _format_agent_results(agent_results: list[dict]) -> str:
    """Format agent results for the synthesis prompt."""
    if not agent_results:
        return "No results available"
    return "\n\n---\n\n".join(
        f"[{r.get('agent_id', 'unknown')}] (Error: {r.get('error')})"
        if r.get("error")
        else f"[{r.get('agent_id', 'unknown')}]\n{r.get('result', 'No result')}"
        for r in agent_results
    )


def _analyze_partial_results(agent_results: list[dict]) -> dict[str, Any]:
    """Analyze agent results to identify successful and failed agents."""
    successful, failed = [], []
    for r in agent_results:
        agent_id = r.get("agent_id", "unknown")
        if r.get("error"):
            failed.append(
                {
                    "agent_id": agent_id,
                    "error": r.get("error"),
                    "recovery_suggestion": r.get("recovery_suggestion"),
                }
            )
        else:
            successful.append({"agent_id": agent_id, "result": r.get("result")})

    return {
        "successful": successful,
        "failed": failed,
        "total": len(agent_results),
        "success_count": len(successful),
        "failure_count": len(failed),
        "is_partial": bool(failed and successful),
        "all_failed": bool(failed and not successful),
    }


def extract_citations(text: str) -> list[dict[str, str]]:
    """Extract citations from the final result text."""
    citations, seen = [], set()

    for match in re.findall(r"\[([^\]]+)\]", text):
        if (
            match.lower() not in ("note", "example", "warning", "info", "tip")
            and match not in seen
        ):
            citations.append({"source": match, "type": "agent"})
            seen.add(match)

    for match in re.findall(
        r"(?:According to|Based on|From)\s+([A-Za-z_][A-Za-z0-9_]*)", text
    ):
        if match not in seen:
            citations.append({"source": match, "type": "reference"})
            seen.add(match)

    return citations


async def synthesize_results(state: OrchestratorState) -> dict[str, Any]:
    """Synthesize results from multiple worker agents into a final response.

    Uses async streaming for real-time token output during LLM synthesis.
    Emits synthesis_progress events for each token chunk.
    """
    from langchain_openai import ChatOpenAI

    execution_id = state.get("execution_id", "")
    factory = EventFactory(execution_id)
    factory.set_phase(EventPhase.SYNTHESIZING)

    start_time = time.time()
    agent_results = state.get("agent_results", [])
    analysis = _analyze_partial_results(agent_results)

    emit_stream_event(
        factory.synthesis_start(
            input_count=analysis["total"],
            successful_count=analysis["success_count"],
            failed_count=analysis["failure_count"],
        )
    )

    # Handle edge cases without LLM call
    if not agent_results:
        result = "No results available from agents."
        emit_stream_event(
            factory.synthesis_complete(
                result=result,
                citations=[],
                is_partial=False,
                duration_ms=int((time.time() - start_time) * 1000),
            )
        )
        return {
            "final_result": result,
            "citations": [],
            "messages": [],
            "partial_result_info": analysis,
        }

    if analysis["all_failed"]:
        failed_summary = "\n".join(
            f"- {f['agent_id']}: {f['error']}" for f in analysis["failed"]
        )
        result = f"All agents failed to execute.\n\nFailure details:\n{failed_summary}"
        emit_stream_event(
            factory.synthesis_complete(
                result=result,
                citations=[],
                is_partial=True,
                duration_ms=int((time.time() - start_time) * 1000),
            )
        )
        return {
            "final_result": result,
            "citations": [],
            "messages": [],
            "partial_result_info": analysis,
        }

    if len(analysis["successful"]) == 1 and not analysis["is_partial"]:
        result = analysis["successful"][0].get("result", "")
        citations = extract_citations(result)
        emit_stream_event(
            factory.synthesis_complete(
                result=result[:500] if result else "",
                citations=[c["source"] for c in citations],
                is_partial=False,
                duration_ms=int((time.time() - start_time) * 1000),
            )
        )
        return {
            "final_result": result,
            "citations": citations,
            "messages": [],
            "partial_result_info": analysis,
        }

    # Build model for streaming synthesis
    model_kwargs = {"model": state.get("model_name", "gpt-4o")}
    if api_key := state.get("api_key"):
        model_kwargs["api_key"] = api_key
    if base_url := state.get("base_url"):
        model_kwargs["base_url"] = base_url

    model = ChatOpenAI(**model_kwargs)

    if analysis["is_partial"]:
        system_prompt = PARTIAL_RESULT_SYSTEM_PROMPT.format(
            successful_results=_format_agent_results(
                [r for r in agent_results if not r.get("error")]
            ),
            failed_agents="\n".join(f"- {f['agent_id']}" for f in analysis["failed"]),
        )
    else:
        system_prompt = SYNTHESIZE_SYSTEM_PROMPT.format(
            agent_results=_format_agent_results(agent_results)
        )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=state["prompt"]),
    ]

    # Stream synthesis with real-time token emission
    accumulated_content = ""
    async for chunk in model.astream(messages):
        if content := chunk.content:
            accumulated_content += content
            emit_stream_event(
                factory.synthesis_progress(
                    content=content,
                    accumulated_content=accumulated_content,
                )
            )

    citations = extract_citations(accumulated_content)
    citation_sources = {c["source"] for c in citations}
    for r in analysis["successful"]:
        if (agent_id := r.get("agent_id")) and agent_id not in citation_sources:
            citations.append({"source": agent_id, "type": "agent"})

    emit_stream_event(
        factory.synthesis_complete(
            result=accumulated_content[:500] if accumulated_content else "",
            citations=[c["source"] for c in citations],
            is_partial=analysis["is_partial"],
            duration_ms=int((time.time() - start_time) * 1000),
        )
    )

    return {
        "final_result": accumulated_content,
        "citations": citations,
        "messages": [],
        "partial_result_info": analysis,
    }
