"""Rich console output for Kiva orchestration."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from rich.box import DOUBLE, HEAVY, ROUNDED
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from kiva.events import EventPhase, StreamEvent

if TYPE_CHECKING:
    from kiva.client import Kiva

__all__ = ["KivaLiveRenderer", "run_with_console"]

AGENT_COLORS = ["cyan", "magenta", "yellow", "green", "blue", "red"]


@dataclass
class ExecutionState:
    """Unified state tracking for agents and instances."""

    id: str
    agent_id: str
    status: str = "pending"
    task: str = ""
    result: str = ""
    color: str = "white"
    current_action: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    instance_num: int = -1
    start_time: float | None = None
    end_time: float | None = None
    error: str | None = None
    retry_count: int = 0

    @property
    def is_instance(self) -> bool:
        return self.instance_num >= 0


@dataclass
class BatchState:
    """State tracking for parallel batch execution."""

    batch_id: str
    agent_ids: list[str] = field(default_factory=list)
    instance_count: int = 0
    completed: int = 0
    failed: int = 0
    progress: int = 0
    start_time: float | None = None
    end_time: float | None = None


class KivaLiveRenderer:
    """Dynamic live renderer for Kiva orchestration visualization."""

    def __init__(self, prompt: str):
        self.prompt = prompt
        self.phase = EventPhase.INITIALIZING
        self.progress_percent = 0
        self.token_buffer = ""
        self.synthesis_buffer = ""
        self.workflow_info: dict = {}
        self.task_assignments: list = []
        self.parallel_strategy: str = "none"
        self.total_instances: int = 0
        self.states: dict[str, ExecutionState] = {}
        self.parallel_batches: dict[str, BatchState] = {}
        self.final_result: str | None = None
        self.citations: list = []
        self.execution_start_time: float = time.time()
        self.phase_start_time: float = time.time()
        self._color_index = 0
        self._agent_colors: dict[str, str] = {}

    def _get_color(self, agent_id: str) -> str:
        if agent_id not in self._agent_colors:
            self._agent_colors[agent_id] = AGENT_COLORS[
                self._color_index % len(AGENT_COLORS)
            ]
            self._color_index += 1
        return self._agent_colors[agent_id]

    def _get_or_create_state(
        self, id_: str, agent_id: str, instance_num: int = -1
    ) -> ExecutionState:
        if id_ not in self.states:
            self.states[id_] = ExecutionState(
                id=id_,
                agent_id=agent_id,
                color=self._get_color(agent_id),
                instance_num=instance_num,
            )
        return self.states[id_]

    def _extract_ids(self, event: StreamEvent) -> tuple[str, str, str | None]:
        data = event.data
        agent_id = data.get("agent_id") or event.agent_id or "unknown"
        instance_id = data.get("instance_id") or event.instance_id
        return instance_id or agent_id, agent_id, instance_id

    def handle_event(self, event: StreamEvent) -> None:
        """Handle a stream event by dispatching to the appropriate handler."""
        handler = getattr(self, f"_handle_{event.type.value}", None)
        if handler:
            handler(event)

    # Event handlers
    def _handle_execution_start(self, event: StreamEvent) -> None:
        self.execution_start_time = self.phase_start_time = event.timestamp

    def _handle_execution_end(self, event: StreamEvent) -> None:
        self.phase, self.progress_percent = EventPhase.COMPLETE, 100

    def _handle_execution_error(self, event: StreamEvent) -> None:
        self.phase, self.progress_percent = EventPhase.ERROR, -1

    def _handle_phase_change(self, event: StreamEvent) -> None:
        try:
            self.phase = EventPhase(event.data.get("current_phase", "initializing"))
        except ValueError:
            self.phase = EventPhase.INITIALIZING
        self.progress_percent = event.data.get("progress_percent", 0)
        self.phase_start_time = event.timestamp

    def _handle_planning_start(self, event: StreamEvent) -> None:
        self.phase, self.token_buffer = EventPhase.ANALYZING, ""

    def _handle_planning_progress(self, event: StreamEvent) -> None:
        self.token_buffer = event.data.get("accumulated_content", "")
        if self.phase == EventPhase.INITIALIZING:
            self.phase = EventPhase.ANALYZING

    def _handle_planning_complete(self, event: StreamEvent) -> None:
        pass

    def _handle_workflow_selected(self, event: StreamEvent) -> None:
        self.workflow_info = {
            "workflow": event.data.get("workflow", "unknown"),
            "complexity": event.data.get("complexity", "N/A"),
        }
        self.task_assignments = event.data.get("task_assignments", [])
        self.parallel_strategy = event.data.get("parallel_strategy", "none")
        self.total_instances = event.data.get("total_instances", 1)
        self.token_buffer = ""
        self.phase = EventPhase.EXECUTING
        for i, task in enumerate(self.task_assignments):
            agent_id = task.get("agent_id", f"agent_{i}")
            state = self._get_or_create_state(agent_id, agent_id)
            state.status = "pending" if self.parallel_strategy == "none" else "_hidden"
            if state.status == "pending":
                state.task = task.get("task", "")

    def _handle_workflow_start(self, event: StreamEvent) -> None:
        self.phase = EventPhase.EXECUTING

    def _handle_workflow_end(self, event: StreamEvent) -> None:
        pass

    def _handle_agent_start(self, event: StreamEvent) -> None:
        _, agent_id, _ = self._extract_ids(event)
        state = self._get_or_create_state(agent_id, agent_id)
        state.status, state.start_time = "running", event.timestamp
        if task := event.data.get("task"):
            state.task = task

    def _handle_agent_progress(self, event: StreamEvent) -> None:
        _, agent_id, _ = self._extract_ids(event)
        if state := self.states.get(agent_id):
            if content := event.data.get("content", ""):
                state.current_action = content[:100]
            if tool_calls := event.data.get("tool_calls", []):
                state.tool_calls = tool_calls

    def _handle_agent_end(self, event: StreamEvent) -> None:
        _, agent_id, _ = self._extract_ids(event)
        if state := self.states.get(agent_id):
            state.status, state.result = "completed", event.data.get("result", "")
            state.end_time, state.current_action, state.tool_calls = (
                event.timestamp,
                "",
                [],
            )

    def _handle_agent_error(self, event: StreamEvent) -> None:
        _, agent_id, _ = self._extract_ids(event)
        if state := self.states.get(agent_id):
            state.status, state.error, state.end_time = (
                "error",
                event.data.get("error_message", "Unknown error"),
                event.timestamp,
            )

    def _handle_agent_retry(self, event: StreamEvent) -> None:
        _, agent_id, _ = self._extract_ids(event)
        if state := self.states.get(agent_id):
            state.status, state.retry_count = "retrying", event.data.get("attempt", 0)

    def _handle_instance_spawn(self, event: StreamEvent) -> None:
        primary_id, agent_id, _ = self._extract_ids(event)
        state = self._get_or_create_state(primary_id, agent_id)
        state.status, state.task, state.instance_num = (
            "spawned",
            event.data.get("task", ""),
            event.data.get("instance_num", 0),
        )

    def _handle_instance_start(self, event: StreamEvent) -> None:
        primary_id, agent_id, _ = self._extract_ids(event)
        state = self._get_or_create_state(primary_id, agent_id)
        state.status, state.start_time = "running", event.timestamp
        if task := event.data.get("task"):
            state.task = task

    def _handle_instance_progress(self, event: StreamEvent) -> None:
        primary_id, _, _ = self._extract_ids(event)
        if state := self.states.get(primary_id):
            if content := event.data.get("content", ""):
                state.current_action = content[:100]
            if tool_calls := event.data.get("tool_calls", []):
                state.tool_calls = tool_calls

    def _handle_instance_end(self, event: StreamEvent) -> None:
        primary_id, _, _ = self._extract_ids(event)
        if state := self.states.get(primary_id):
            state.status, state.result = "completed", event.data.get("result", "")
            state.end_time, state.current_action, state.tool_calls = (
                event.timestamp,
                "",
                [],
            )

    def _handle_instance_error(self, event: StreamEvent) -> None:
        primary_id, _, _ = self._extract_ids(event)
        if state := self.states.get(primary_id):
            state.status, state.error, state.end_time = (
                "error",
                event.data.get("error_message", "Unknown error"),
                event.timestamp,
            )

    def _handle_instance_retry(self, event: StreamEvent) -> None:
        primary_id, _, _ = self._extract_ids(event)
        if state := self.states.get(primary_id):
            state.status, state.retry_count = "retrying", event.data.get("attempt", 0)

    def _handle_parallel_start(self, event: StreamEvent) -> None:
        batch_id = event.data.get("batch_id", "")
        self.parallel_batches[batch_id] = BatchState(
            batch_id=batch_id,
            agent_ids=event.data.get("agent_ids", []),
            instance_count=event.data.get("instance_count", 0),
            start_time=event.timestamp,
        )
        for agent_id in event.data.get("agent_ids", []):
            state = self._get_or_create_state(agent_id, agent_id)
            if state.status == "_hidden":
                state.status = "running"

    def _handle_parallel_progress(self, event: StreamEvent) -> None:
        if batch := self.parallel_batches.get(event.data.get("batch_id", "")):
            batch.completed, batch.progress = (
                event.data.get("completed_count", 0),
                event.data.get("progress_percent", 0),
            )

    def _handle_parallel_complete(self, event: StreamEvent) -> None:
        if batch := self.parallel_batches.get(event.data.get("batch_id", "")):
            batch.completed, batch.failed = (
                event.data.get("success_count", 0),
                event.data.get("failure_count", 0),
            )
            batch.end_time, batch.progress = event.timestamp, 100

    def _handle_synthesis_start(self, event: StreamEvent) -> None:
        self.phase, self.synthesis_buffer, self.phase_start_time = (
            EventPhase.SYNTHESIZING,
            "",
            event.timestamp,
        )

    def _handle_synthesis_progress(self, event: StreamEvent) -> None:
        self.synthesis_buffer = event.data.get("accumulated_content", "")
        if self.phase != EventPhase.SYNTHESIZING:
            self.phase = EventPhase.SYNTHESIZING

    def _handle_synthesis_complete(self, event: StreamEvent) -> None:
        self.final_result, self.citations = (
            event.data.get("result", ""),
            event.data.get("citations", []),
        )
        self.phase, self.progress_percent = EventPhase.COMPLETE, 100

    def _handle_token(self, event: StreamEvent) -> None:
        self.token_buffer += event.data.get("content", "")
        if self.phase == EventPhase.INITIALIZING:
            self.phase = EventPhase.ANALYZING

    def _handle_tool_call_start(self, event: StreamEvent) -> None:
        pass

    def _handle_tool_call_end(self, event: StreamEvent) -> None:
        pass

    def _handle_debug(self, event: StreamEvent) -> None:
        pass

    # Rendering
    def _render_header(self) -> Panel:
        return Panel(
            Text(self.prompt, style="bold white"),
            title="[bold cyan]KIVA Orchestrator[/]",
            subtitle="[dim]Multi-Agent Workflow Engine[/]",
            border_style="cyan",
            box=DOUBLE,
        )

    def _render_phase_indicator(self) -> Text:
        phases = [
            EventPhase.INITIALIZING,
            EventPhase.ANALYZING,
            EventPhase.EXECUTING,
            EventPhase.SYNTHESIZING,
            EventPhase.COMPLETE,
        ]
        icons = {
            EventPhase.INITIALIZING: ("[ ]", "dim"),
            EventPhase.ANALYZING: ("[~]", "yellow"),
            EventPhase.EXECUTING: ("[>]", "green"),
            EventPhase.SYNTHESIZING: ("[*]", "magenta"),
            EventPhase.COMPLETE: ("[v]", "bold green"),
            EventPhase.ERROR: ("[x]", "bold red"),
        }
        text = Text()
        for i, p in enumerate(phases):
            icon, style = icons.get(p, ("[ ]", "dim"))
            text.append(
                f" {icon} {p.value.upper()} "
                if p == self.phase
                else f" {icon} {p.value} ",
                style=f"bold reverse {style}" if p == self.phase else "dim",
            )
            if i < len(phases) - 1:
                text.append("->", style="dim")
        return text

    def _render_phase_timing(self) -> Text:
        phase_time = time.time() - self.phase_start_time
        total_time = time.time() - self.execution_start_time
        return Text(f"Phase: {phase_time:.1f}s | Total: {total_time:.1f}s", style="dim")

    def _render_analyzing_panel(self) -> Panel:
        if not self.token_buffer:
            return Panel(
                Spinner("dots", text="Analyzing task...", style="cyan"),
                title="[yellow]Analyzing[/]",
                border_style="yellow",
                box=ROUNDED,
            )
        try:
            content = self._render_workflow_json(json.loads(self.token_buffer.strip()))
        except json.JSONDecodeError:
            content = Text(self.token_buffer + "_", style="white")
        return Panel(
            content,
            title="[yellow]Lead Agent Thinking[/]",
            border_style="yellow",
            box=ROUNDED,
        )

    def _render_workflow_json(self, data: dict) -> Table:
        table = Table(
            box=ROUNDED, show_header=False, border_style="yellow", padding=(0, 1)
        )
        table.add_column("Key", style="bold yellow")
        table.add_column("Value", style="white")
        if "workflow" in data:
            table.add_row(
                "Workflow", Text(data["workflow"].upper(), style="bold magenta")
            )
        if "complexity" in data:
            table.add_row(
                "Complexity",
                Text(
                    data["complexity"],
                    style={"low": "green", "medium": "yellow", "high": "red"}.get(
                        data["complexity"], "white"
                    ),
                ),
            )
        if "reasoning" in data:
            table.add_row(
                "Reasoning",
                Text(
                    data["reasoning"][:120] + "..."
                    if len(data["reasoning"]) > 120
                    else data["reasoning"],
                    style="italic dim",
                ),
            )
        if "task_assignments" in data:
            table.add_row(
                "Tasks", Text(str(len(data["task_assignments"])), style="cyan")
            )
        if data.get("parallel_strategy", "none") != "none":
            table.add_row(
                "Parallel Strategy",
                Text(data["parallel_strategy"].upper(), style="bold green"),
            )
        if data.get("total_instances", 0) > 1:
            table.add_row(
                "Total Instances", Text(str(data["total_instances"]), style="bold cyan")
            )
        return table

    def _render_workflow_info(self) -> Panel | None:
        if not self.workflow_info:
            return None
        table = Table(
            box=ROUNDED, show_header=False, border_style="blue", padding=(0, 1)
        )
        table.add_column("", style="bold blue")
        table.add_column("", style="white")
        table.add_row(
            "Workflow",
            Text(
                self.workflow_info.get("workflow", "unknown").upper(),
                style="bold magenta",
            ),
        )
        table.add_row(
            "Complexity",
            Text(
                self.workflow_info.get("complexity", "N/A"),
                style={"low": "green", "medium": "yellow", "high": "red"}.get(
                    self.workflow_info.get("complexity", ""), "white"
                ),
            ),
        )
        if self.parallel_strategy and self.parallel_strategy != "none":
            table.add_row(
                "Parallel Strategy",
                Text(self.parallel_strategy.upper(), style="bold green"),
            )
        if self.total_instances > 1:
            table.add_row(
                "Total Instances", Text(str(self.total_instances), style="bold cyan")
            )
        return Panel(
            table, title="[blue]Workflow Selected[/]", border_style="blue", box=ROUNDED
        )

    def _get_status_text(self, status: str, color: str) -> Text:
        status_map = {
            "pending": ("[ ] PENDING", "dim"),
            "spawned": ("[+] SPAWNED", f"bold {color}"),
            "running": ("[~] RUNNING", f"bold {color}"),
            "completed": ("[v] DONE", "bold green"),
            "error": ("[x] ERROR", "bold red"),
            "retrying": ("[R] RETRY", "bold yellow"),
        }
        text, style = status_map.get(status, (status, "dim"))
        return Text(text, style=style)

    def _render_agents_status(self) -> Panel | None:
        visible = {k: v for k, v in self.states.items() if v.status != "_hidden"}
        if not visible:
            return None
        table = Table(box=ROUNDED, border_style="green", show_lines=True)
        table.add_column("Agent", style="bold")
        table.add_column("Instance", justify="center")
        table.add_column("Status", justify="center")
        table.add_column("Task / Result", overflow="fold")
        for state in visible.values():
            status_text = (
                Text(f"[R] RETRY {state.retry_count}", style="bold yellow")
                if state.status == "retrying"
                else self._get_status_text(state.status, state.color)
            )
            content = (
                state.result[:80] + "..."
                if state.status == "completed"
                and state.result
                and len(state.result) > 80
                else (
                    f"{state.task[:20]}... | {state.current_action}"
                    if state.current_action and state.status == "running"
                    else (
                        state.task[:60] + "..." if len(state.task) > 60 else state.task
                    )
                )
            )
            instance_col = (
                Text(
                    state.id.split("-")[-1][:8] if "-" in state.id else state.id[:8],
                    style="dim cyan",
                )
                if state.is_instance
                else Text("-", style="dim")
            )
            table.add_row(
                Text(state.agent_id, style=f"bold {state.color}"),
                instance_col,
                status_text,
                Text(content, style="white" if state.status == "completed" else "dim"),
            )
        return Panel(
            table,
            title="[green]Agent Instances Execution[/]"
            if any(s.is_instance for s in visible.values())
            else "[green]Agent Execution[/]",
            border_style="green",
            box=ROUNDED,
        )

    def _render_parallel_batch(self) -> Panel | None:
        active = next(
            (b for b in self.parallel_batches.values() if b.end_time is None), None
        )
        if not active:
            return None
        progress = Progress(
            TextColumn("[bold green]{task.description}"),
            BarColumn(bar_width=30),
            TextColumn("{task.completed}/{task.total}"),
        )
        progress.add_task(
            f"Batch: {active.batch_id[:8]}...",
            total=active.instance_count,
            completed=active.completed,
        )
        return Panel(
            progress, title="[green]Parallel Execution[/]", border_style="green"
        )

    def _render_synthesis(self) -> Panel:
        if self.synthesis_buffer:
            return Panel(
                Text(self.synthesis_buffer + "_", style="white"),
                title="[magenta]Synthesizing Results[/]",
                border_style="magenta",
                box=ROUNDED,
            )
        return Panel(
            Spinner("dots", text="Synthesizing agent results...", style="magenta"),
            title="[magenta]Synthesizing[/]",
            border_style="magenta",
            box=ROUNDED,
        )

    def _render_final_result(self) -> Panel | None:
        if not self.final_result:
            return None
        citation_pattern = r"\[([^\]]+_agent)\]"
        parts = re.split(citation_pattern, self.final_result)
        styled_text = Text()
        for part in parts:
            if part.endswith("_agent") and part in self._agent_colors:
                styled_text.append(
                    f"[{part}]", style=f"bold {self._agent_colors[part]}"
                )
            else:
                for j, bp in enumerate(re.split(r"\*\*([^*]+)\*\*", part)):
                    styled_text.append(
                        bp, style="bold white" if j % 2 == 1 else "white"
                    )
        content_parts = [styled_text]
        citations_found = re.findall(citation_pattern, self.final_result)
        if citations_found:
            content_parts.append(Text())
            cite_table = Table(
                box=ROUNDED, border_style="dim blue", show_header=True, title="Sources"
            )
            cite_table.add_column("Agent", style="bold")
            cite_table.add_column("Contribution", style="dim")
            seen = set()
            for agent_id in citations_found:
                if agent_id in seen:
                    continue
                seen.add(agent_id)
                result = self.states.get(
                    agent_id, ExecutionState(agent_id, agent_id)
                ).result
                cite_table.add_row(
                    Text(
                        agent_id,
                        style=f"bold {self._agent_colors.get(agent_id, 'white')}",
                    ),
                    result[:50] + "..." if len(result) > 50 else result,
                )
            content_parts.append(cite_table)
        return Panel(
            Group(*content_parts),
            title="[bold white on blue] FINAL RESULT [/]",
            border_style="bold blue",
            box=HEAVY,
            padding=(1, 2),
        )

    def build_display(self) -> Group:
        """Build the complete display layout for the current state."""
        components = [
            self._render_header(),
            Text(),
            self._render_phase_indicator(),
            Text(),
            self._render_phase_timing(),
            Text(),
        ]
        if self.phase == EventPhase.INITIALIZING:
            components.append(
                Panel(
                    Spinner("dots", text="Initializing orchestration...", style="cyan"),
                    border_style="cyan",
                    box=ROUNDED,
                )
            )
        elif self.phase == EventPhase.ANALYZING:
            components.append(self._render_analyzing_panel())
        elif self.phase == EventPhase.EXECUTING:
            if wf := self._render_workflow_info():
                components.extend([wf, Text()])
            if agents := self._render_agents_status():
                components.append(agents)
            if batch := self._render_parallel_batch():
                components.extend([Text(), batch])
        elif self.phase == EventPhase.SYNTHESIZING:
            if wf := self._render_workflow_info():
                components.extend([wf, Text()])
            if agents := self._render_agents_status():
                components.extend([agents, Text()])
            components.append(self._render_synthesis())
        elif self.phase == EventPhase.COMPLETE:
            if wf := self._render_workflow_info():
                components.extend([wf, Text()])
            if agents := self._render_agents_status():
                components.extend([agents, Text()])
            if final := self._render_final_result():
                components.append(final)
            components.extend(
                [Text(), Text.from_markup("[bold green]✓ Orchestration Complete[/]")]
            )
        elif self.phase == EventPhase.ERROR:
            if wf := self._render_workflow_info():
                components.extend([wf, Text()])
            if agents := self._render_agents_status():
                components.extend([agents, Text()])
            components.append(Text.from_markup("[bold red]✗ Orchestration Failed[/]"))
        return Group(*components)


async def run_with_console(
    prompt: str,
    kiva: Kiva,
    worker_max_iterations: int = 100,
    refresh_per_second: int = 12,
) -> str | None:
    """Run orchestration with rich console visualization."""
    console = Console()
    renderer = KivaLiveRenderer(prompt)
    with Live(
        renderer.build_display(),
        console=console,
        refresh_per_second=refresh_per_second,
        transient=False,
    ) as live:
        async for event in kiva.stream(prompt, worker_max_iterations):
            renderer.handle_event(event)
            live.update(renderer.build_display())
    return renderer.final_result
