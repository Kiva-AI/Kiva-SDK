"""Event definitions for the Kiva SDK.

Provides StreamEvent dataclass and EventFactory for real-time event streaming.
"""

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class EventType(str, Enum):
    """Event types for orchestration lifecycle."""

    # Lifecycle
    EXECUTION_START = "execution_start"
    EXECUTION_END = "execution_end"
    EXECUTION_ERROR = "execution_error"
    # Phase
    PHASE_CHANGE = "phase_change"
    # Planning
    PLANNING_START = "planning_start"
    PLANNING_PROGRESS = "planning_progress"
    PLANNING_COMPLETE = "planning_complete"
    # Workflow
    WORKFLOW_SELECTED = "workflow_selected"
    WORKFLOW_START = "workflow_start"
    WORKFLOW_END = "workflow_end"
    # Agent
    AGENT_START = "agent_start"
    AGENT_PROGRESS = "agent_progress"
    AGENT_END = "agent_end"
    AGENT_ERROR = "agent_error"
    AGENT_RETRY = "agent_retry"
    # Instance
    INSTANCE_SPAWN = "instance_spawn"
    INSTANCE_START = "instance_start"
    INSTANCE_PROGRESS = "instance_progress"
    INSTANCE_END = "instance_end"
    INSTANCE_ERROR = "instance_error"
    INSTANCE_RETRY = "instance_retry"
    # Parallel
    PARALLEL_START = "parallel_start"
    PARALLEL_PROGRESS = "parallel_progress"
    PARALLEL_COMPLETE = "parallel_complete"
    # Synthesis
    SYNTHESIS_START = "synthesis_start"
    SYNTHESIS_PROGRESS = "synthesis_progress"
    SYNTHESIS_COMPLETE = "synthesis_complete"
    # Token & Tool
    TOKEN = "token"
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_END = "tool_call_end"
    DEBUG = "debug"


class EventPhase(str, Enum):
    """Execution phases during orchestration."""

    INITIALIZING = "initializing"
    ANALYZING = "analyzing"
    EXECUTING = "executing"
    SYNTHESIZING = "synthesizing"
    COMPLETE = "complete"
    ERROR = "error"


class EventSeverity(str, Enum):
    """Event severity levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(slots=True)
class StreamEvent:
    """Streaming event emitted during orchestration execution."""

    type: EventType
    data: dict[str, Any]
    execution_id: str
    phase: EventPhase = EventPhase.INITIALIZING
    severity: EventSeverity = EventSeverity.INFO
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)
    agent_id: str | None = None
    instance_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "event_id": self.event_id,
            "type": self.type.value,
            "phase": self.phase.value,
            "severity": self.severity.value,
            "timestamp": self.timestamp,
            "timestamp_iso": datetime.fromtimestamp(self.timestamp, tz=UTC).isoformat(),
            "execution_id": self.execution_id,
            "data": self.data,
            "metadata": self.metadata,
            "agent_id": self.agent_id,
            "instance_id": self.instance_id,
        }

    def to_json(self) -> str:
        """Convert event to JSON string.

        Non-serializable objects are converted to their string representation.
        """
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)

    def to_sse(self) -> str:
        """Convert event to SSE (Server-Sent Events) format string.

        Returns:
            SSE formatted string with event, id, and data fields,
            ending with double newline.
        """
        # JSON already escapes newlines properly, so no additional escaping needed
        json_data = self.to_json()
        return f"event: {self.type.value}\nid: {self.event_id}\ndata: {json_data}\n\n"

    def to_ndjson(self) -> str:
        """Convert event to NDJSON (Newline Delimited JSON) format.

        Returns:
            Single-line JSON string followed by newline character.
        """
        return self.to_json() + "\n"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StreamEvent":
        """Create a StreamEvent from a dictionary."""
        return cls(
            event_id=data.get("event_id", str(uuid.uuid4())),
            type=EventType(data["type"]),
            phase=EventPhase(data.get("phase", "initializing")),
            severity=EventSeverity(data.get("severity", "info")),
            timestamp=data.get("timestamp", time.time()),
            execution_id=data.get("execution_id", ""),
            data=data.get("data", {}),
            metadata=data.get("metadata", {}),
            agent_id=data.get("agent_id"),
            instance_id=data.get("instance_id"),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "StreamEvent":
        """Create a StreamEvent from a JSON string."""
        return cls.from_dict(json.loads(json_str))


class EventFactory:
    """Factory for creating StreamEvent instances with execution context.

    Maintains monotonic timestamp guarantee for event ordering.
    """

    __slots__ = ("execution_id", "current_phase", "start_time", "_last_timestamp")

    def __init__(self, execution_id: str) -> None:
        self.execution_id = execution_id
        self.current_phase = EventPhase.INITIALIZING
        self.start_time = time.time()
        self._last_timestamp = self.start_time

    def set_phase(self, phase: EventPhase) -> None:
        """Set the current execution phase."""
        self.current_phase = phase

    def _get_monotonic_timestamp(self) -> float:
        """Get a monotonically increasing timestamp.

        Ensures timestamps are strictly monotonically increasing even if
        the system clock returns the same or earlier time.

        Returns:
            A timestamp guaranteed to be greater than the previous timestamp.
        """
        now = time.time()
        if now <= self._last_timestamp:
            # Ensure monotonic by adding small increment (1 microsecond)
            # Using 1e-6 instead of 1e-9 to ensure float precision at typical
            # timestamp magnitudes
            self._last_timestamp += 1e-6
        else:
            self._last_timestamp = now
        return self._last_timestamp

    def create(
        self,
        event_type: EventType,
        data: dict[str, Any],
        *,
        severity: EventSeverity = EventSeverity.INFO,
        agent_id: str | None = None,
        instance_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> StreamEvent:
        """Create a new StreamEvent with the current execution context.

        Uses monotonic timestamps to ensure event ordering.
        """
        return StreamEvent(
            type=event_type,
            phase=self.current_phase,
            severity=severity,
            execution_id=self.execution_id,
            data=data,
            metadata=metadata or {},
            agent_id=agent_id,
            instance_id=instance_id,
            timestamp=self._get_monotonic_timestamp(),
        )

    # Lifecycle
    def execution_start(self, prompt: str, agents: list, config: dict) -> StreamEvent:
        """Create an execution start event."""
        return self.create(
            EventType.EXECUTION_START,
            {
                "prompt": prompt,
                "agent_count": len(agents),
                "agent_names": [
                    getattr(a, "name", f"agent_{i}") for i, a in enumerate(agents)
                ],
                "config": config,
            },
        )

    def execution_end(
        self, result: str, agent_results_count: int, success: bool = True
    ) -> StreamEvent:
        """Create an execution end event."""
        return self.create(
            EventType.EXECUTION_END,
            {
                "duration_ms": int((time.time() - self.start_time) * 1000),
                "result": result[:500] if result else "",
                "agent_results_count": agent_results_count,
                "success": success,
            },
        )

    def execution_error(
        self,
        error_type: str,
        error_message: str,
        stack_trace: str | None = None,
        recovery_suggestion: str | None = None,
    ) -> StreamEvent:
        """Create an execution error event."""
        return self.create(
            EventType.EXECUTION_ERROR,
            {
                "error_type": error_type,
                "error_message": error_message,
                "stack_trace": stack_trace,
                "recovery_suggestion": recovery_suggestion,
            },
            severity=EventSeverity.ERROR,
        )

    # Phase
    def phase_change(
        self,
        previous_phase: EventPhase,
        current_phase: EventPhase,
        progress_percent: int,
        message: str,
    ) -> StreamEvent:
        """Create a phase change event."""
        self.set_phase(current_phase)
        return self.create(
            EventType.PHASE_CHANGE,
            {
                "previous_phase": previous_phase.value,
                "current_phase": current_phase.value,
                "progress_percent": progress_percent,
                "message": message,
            },
        )

    # Planning
    def planning_start(self, prompt: str, available_agents: list) -> StreamEvent:
        """Create a planning start event."""
        return self.create(
            EventType.PLANNING_START,
            {"prompt": prompt, "available_agents": available_agents},
        )

    def planning_progress(self, content: str, accumulated_content: str) -> StreamEvent:
        """Create a planning progress event."""
        return self.create(
            EventType.PLANNING_PROGRESS,
            {"content": content, "accumulated_content": accumulated_content},
        )

    def planning_complete(
        self,
        complexity: str,
        workflow: str,
        reasoning: str,
        task_assignments: list,
        parallel_strategy: str | None = None,
        total_instances: int = 0,
        duration_ms: int | None = None,
    ) -> StreamEvent:
        """Create a planning complete event."""
        return self.create(
            EventType.PLANNING_COMPLETE,
            {
                "complexity": complexity,
                "workflow": workflow,
                "reasoning": reasoning,
                "task_assignments": task_assignments,
                "parallel_strategy": parallel_strategy,
                "total_instances": total_instances,
                "duration_ms": duration_ms,
            },
        )

    # Workflow
    def workflow_selected(
        self,
        workflow: str,
        complexity: str,
        task_assignments: list,
        parallel_strategy: str | None = None,
        total_instances: int = 0,
    ) -> StreamEvent:
        """Create a workflow selected event."""
        return self.create(
            EventType.WORKFLOW_SELECTED,
            {
                "workflow": workflow,
                "complexity": complexity,
                "task_assignments": task_assignments,
                "parallel_strategy": parallel_strategy,
                "total_instances": total_instances,
            },
        )

    def workflow_start(
        self, workflow: str, agent_ids: list, iteration: int = 1
    ) -> StreamEvent:
        """Create a workflow start event."""
        return self.create(
            EventType.WORKFLOW_START,
            {"workflow": workflow, "agent_ids": agent_ids, "iteration": iteration},
        )

    def workflow_end(
        self,
        workflow: str,
        success: bool,
        results_count: int,
        duration_ms: int,
        conflicts_found: int = 0,
    ) -> StreamEvent:
        """Create a workflow end event."""
        return self.create(
            EventType.WORKFLOW_END,
            {
                "workflow": workflow,
                "success": success,
                "results_count": results_count,
                "duration_ms": duration_ms,
                "conflicts_found": conflicts_found,
            },
        )

    # Agent
    def agent_start(
        self, agent_id: str, invocation_id: str, task: str, iteration: int = 1
    ) -> StreamEvent:
        """Create an agent start event."""
        return self.create(
            EventType.AGENT_START,
            {
                "agent_id": agent_id,
                "invocation_id": invocation_id,
                "task": task,
                "iteration": iteration,
            },
            agent_id=agent_id,
        )

    def agent_progress(
        self,
        agent_id: str,
        invocation_id: str,
        message_type: str,
        content: str,
        tool_calls: list | None = None,
    ) -> StreamEvent:
        """Create an agent progress event."""
        return self.create(
            EventType.AGENT_PROGRESS,
            {
                "agent_id": agent_id,
                "invocation_id": invocation_id,
                "message_type": message_type,
                "content": content,
                "tool_calls": tool_calls or [],
            },
            agent_id=agent_id,
        )

    def agent_end(
        self,
        agent_id: str,
        invocation_id: str,
        result: str,
        duration_ms: int,
        success: bool = True,
    ) -> StreamEvent:
        """Create an agent end event."""
        return self.create(
            EventType.AGENT_END,
            {
                "agent_id": agent_id,
                "invocation_id": invocation_id,
                "result": result,
                "duration_ms": duration_ms,
                "success": success,
            },
            agent_id=agent_id,
        )

    def agent_error(
        self,
        agent_id: str,
        invocation_id: str,
        error_type: str,
        error_message: str,
        recovery_suggestion: str | None = None,
    ) -> StreamEvent:
        """Create an agent error event."""
        return self.create(
            EventType.AGENT_ERROR,
            {
                "agent_id": agent_id,
                "invocation_id": invocation_id,
                "error_type": error_type,
                "error_message": error_message,
                "recovery_suggestion": recovery_suggestion,
            },
            agent_id=agent_id,
            severity=EventSeverity.ERROR,
        )

    def agent_retry(
        self,
        agent_id: str,
        invocation_id: str,
        attempt: int,
        max_retries: int,
        reason: str,
    ) -> StreamEvent:
        """Create an agent retry event."""
        return self.create(
            EventType.AGENT_RETRY,
            {
                "agent_id": agent_id,
                "invocation_id": invocation_id,
                "attempt": attempt,
                "max_retries": max_retries,
                "reason": reason,
            },
            agent_id=agent_id,
            severity=EventSeverity.WARNING,
        )

    # Instance
    def instance_spawn(
        self,
        instance_id: str,
        agent_id: str,
        task: str,
        instance_num: int,
        context: dict | None = None,
    ) -> StreamEvent:
        """Create an instance spawn event."""
        return self.create(
            EventType.INSTANCE_SPAWN,
            {
                "instance_id": instance_id,
                "agent_id": agent_id,
                "task": task,
                "instance_num": instance_num,
                "context": context or {},
            },
            agent_id=agent_id,
            instance_id=instance_id,
        )

    def instance_start(self, instance_id: str, agent_id: str, task: str) -> StreamEvent:
        """Create an instance start event."""
        return self.create(
            EventType.INSTANCE_START,
            {"instance_id": instance_id, "agent_id": agent_id, "task": task},
            agent_id=agent_id,
            instance_id=instance_id,
        )

    def instance_progress(
        self,
        instance_id: str,
        agent_id: str,
        message_type: str,
        content: str,
        tool_calls: list | None = None,
    ) -> StreamEvent:
        """Create an instance progress event."""
        return self.create(
            EventType.INSTANCE_PROGRESS,
            {
                "instance_id": instance_id,
                "agent_id": agent_id,
                "message_type": message_type,
                "content": content,
                "tool_calls": tool_calls or [],
            },
            agent_id=agent_id,
            instance_id=instance_id,
        )

    def instance_end(
        self,
        instance_id: str,
        agent_id: str,
        result: str,
        duration_ms: int,
        success: bool = True,
    ) -> StreamEvent:
        """Create an instance end event."""
        return self.create(
            EventType.INSTANCE_END,
            {
                "instance_id": instance_id,
                "agent_id": agent_id,
                "result": result,
                "duration_ms": duration_ms,
                "success": success,
            },
            agent_id=agent_id,
            instance_id=instance_id,
        )

    def instance_error(
        self, instance_id: str, agent_id: str, error_type: str, error_message: str
    ) -> StreamEvent:
        """Create an instance error event."""
        return self.create(
            EventType.INSTANCE_ERROR,
            {
                "instance_id": instance_id,
                "agent_id": agent_id,
                "error_type": error_type,
                "error_message": error_message,
            },
            agent_id=agent_id,
            instance_id=instance_id,
            severity=EventSeverity.ERROR,
        )

    def instance_retry(
        self, instance_id: str, agent_id: str, attempt: int, max_retries: int
    ) -> StreamEvent:
        """Create an instance retry event."""
        return self.create(
            EventType.INSTANCE_RETRY,
            {
                "instance_id": instance_id,
                "agent_id": agent_id,
                "attempt": attempt,
                "max_retries": max_retries,
            },
            agent_id=agent_id,
            instance_id=instance_id,
            severity=EventSeverity.WARNING,
        )

    # Parallel
    def parallel_start(
        self, batch_id: str, agent_ids: list, instance_count: int, strategy: str
    ) -> StreamEvent:
        """Create a parallel start event."""
        return self.create(
            EventType.PARALLEL_START,
            {
                "batch_id": batch_id,
                "agent_ids": agent_ids,
                "instance_count": instance_count,
                "strategy": strategy,
            },
        )

    def parallel_progress(
        self,
        batch_id: str,
        completed_count: int,
        total_count: int,
        progress_percent: int,
    ) -> StreamEvent:
        """Create a parallel progress event."""
        return self.create(
            EventType.PARALLEL_PROGRESS,
            {
                "batch_id": batch_id,
                "completed_count": completed_count,
                "total_count": total_count,
                "progress_percent": progress_percent,
            },
        )

    def parallel_complete(
        self,
        batch_id: str,
        results: list,
        success_count: int,
        failure_count: int,
        duration_ms: int,
    ) -> StreamEvent:
        """Create a parallel complete event."""
        return self.create(
            EventType.PARALLEL_COMPLETE,
            {
                "batch_id": batch_id,
                "results": results,
                "success_count": success_count,
                "failure_count": failure_count,
                "duration_ms": duration_ms,
            },
        )

    # Synthesis
    def synthesis_start(
        self, input_count: int, successful_count: int, failed_count: int
    ) -> StreamEvent:
        """Create a synthesis start event."""
        return self.create(
            EventType.SYNTHESIS_START,
            {
                "input_count": input_count,
                "successful_count": successful_count,
                "failed_count": failed_count,
            },
        )

    def synthesis_progress(self, content: str, accumulated_content: str) -> StreamEvent:
        """Create a synthesis progress event."""
        return self.create(
            EventType.SYNTHESIS_PROGRESS,
            {"content": content, "accumulated_content": accumulated_content},
        )

    def synthesis_complete(
        self, result: str, citations: list, is_partial: bool, duration_ms: int
    ) -> StreamEvent:
        """Create a synthesis complete event."""
        return self.create(
            EventType.SYNTHESIS_COMPLETE,
            {
                "result": result,
                "citations": citations,
                "is_partial": is_partial,
                "duration_ms": duration_ms,
            },
        )

    # Tool
    def tool_call_start(
        self,
        tool_name: str,
        tool_args: dict,
        call_id: str,
        agent_id: str | None = None,
        instance_id: str | None = None,
    ) -> StreamEvent:
        """Create a tool call start event."""
        return self.create(
            EventType.TOOL_CALL_START,
            {"tool_name": tool_name, "tool_args": tool_args, "call_id": call_id},
            agent_id=agent_id,
            instance_id=instance_id,
        )

    def tool_call_end(
        self,
        tool_name: str,
        call_id: str,
        result_preview: str,
        success: bool,
        duration_ms: int,
        agent_id: str | None = None,
        instance_id: str | None = None,
    ) -> StreamEvent:
        """Create a tool call end event."""
        return self.create(
            EventType.TOOL_CALL_END,
            {
                "tool_name": tool_name,
                "call_id": call_id,
                "result_preview": result_preview,
                "success": success,
                "duration_ms": duration_ms,
            },
            agent_id=agent_id,
            instance_id=instance_id,
        )

    # Token & Debug
    def token(
        self, content: str, agent_id: str | None = None, instance_id: str | None = None
    ) -> StreamEvent:
        """Create a token event."""
        return self.create(
            EventType.TOKEN,
            {"content": content},
            agent_id=agent_id,
            instance_id=instance_id,
        )

    def debug(self, message: str, details: dict | None = None) -> StreamEvent:
        """Create a debug event."""
        return self.create(
            EventType.DEBUG,
            {"message": message, "details": details or {}},
            severity=EventSeverity.DEBUG,
        )
