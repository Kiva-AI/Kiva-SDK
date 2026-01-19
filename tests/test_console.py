"""Tests for the console module.

Tests the KivaLiveRenderer and state data classes for event handling
and state updates.
"""

import pytest

from kiva.console import (
    BatchState,
    ExecutionState,
    KivaLiveRenderer,
)
from kiva.events import EventPhase, EventType, StreamEvent


# =============================================================================
# State Data Class Tests
# =============================================================================


class TestExecutionState:
    """Tests for ExecutionState dataclass."""

    def test_default_values(self):
        """Test ExecutionState has correct default values."""
        state = ExecutionState(id="test_agent", agent_id="test_agent")
        assert state.id == "test_agent"
        assert state.agent_id == "test_agent"
        assert state.status == "pending"
        assert state.task == ""
        assert state.result == ""
        assert state.color == "white"
        assert state.current_action == ""
        assert state.tool_calls == []
        assert state.instance_num == -1
        assert state.start_time is None
        assert state.end_time is None
        assert state.error is None
        assert state.retry_count == 0

    def test_custom_values(self):
        """Test ExecutionState with custom values."""
        state = ExecutionState(
            id="custom_agent",
            agent_id="custom_agent",
            status="running",
            task="Test task",
            color="cyan",
        )
        assert state.id == "custom_agent"
        assert state.status == "running"
        assert state.task == "Test task"
        assert state.color == "cyan"

    def test_is_instance_property(self):
        """Test is_instance property."""
        agent_state = ExecutionState(id="agent_1", agent_id="agent_1", instance_num=-1)
        assert not agent_state.is_instance

        instance_state = ExecutionState(
            id="inst_1", agent_id="agent_1", instance_num=0
        )
        assert instance_state.is_instance


class TestBatchState:
    """Tests for BatchState dataclass."""

    def test_default_values(self):
        """Test BatchState has correct default values."""
        state = BatchState(batch_id="batch_1")
        assert state.batch_id == "batch_1"
        assert state.agent_ids == []
        assert state.instance_count == 0
        assert state.completed == 0
        assert state.failed == 0
        assert state.progress == 0
        assert state.start_time is None
        assert state.end_time is None


# =============================================================================
# KivaLiveRenderer Tests
# =============================================================================


class TestKivaLiveRendererInit:
    """Tests for KivaLiveRenderer initialization."""

    def test_init_default_values(self):
        """Test renderer initializes with correct default values."""
        renderer = KivaLiveRenderer("Test prompt")
        assert renderer.prompt == "Test prompt"
        assert renderer.phase == EventPhase.INITIALIZING
        assert renderer.progress_percent == 0
        assert renderer.token_buffer == ""
        assert renderer.synthesis_buffer == ""
        assert renderer.workflow_info == {}
        assert renderer.task_assignments == []
        assert renderer.parallel_strategy == "none"
        assert renderer.total_instances == 0
        assert renderer.states == {}
        assert renderer.parallel_batches == {}
        assert renderer.final_result is None
        assert renderer.citations == []


class TestKivaLiveRendererEventHandling:
    """Tests for KivaLiveRenderer event handling."""

    def test_handle_event_dispatches_correctly(self):
        """Test handle_event dispatches to correct handler."""
        renderer = KivaLiveRenderer("Test")
        event = StreamEvent(
            type=EventType.PHASE_CHANGE,
            data={
                "previous_phase": "initializing",
                "current_phase": "analyzing",
                "progress_percent": 25,
            },
            execution_id="exec_1",
        )
        renderer.handle_event(event)
        assert renderer.phase == EventPhase.ANALYZING
        assert renderer.progress_percent == 25

    def test_handle_execution_start(self):
        """Test handling execution_start event."""
        renderer = KivaLiveRenderer("Test")
        event = StreamEvent(
            type=EventType.EXECUTION_START,
            data={"prompt": "Test", "agent_count": 2},
            execution_id="exec_1",
            timestamp=1000.0,
        )
        renderer.handle_event(event)
        assert renderer.execution_start_time == 1000.0

    def test_handle_execution_end(self):
        """Test handling execution_end event."""
        renderer = KivaLiveRenderer("Test")
        event = StreamEvent(
            type=EventType.EXECUTION_END,
            data={"result": "Done", "success": True},
            execution_id="exec_1",
        )
        renderer.handle_event(event)
        assert renderer.phase == EventPhase.COMPLETE
        assert renderer.progress_percent == 100

    def test_handle_execution_error(self):
        """Test handling execution_error event."""
        renderer = KivaLiveRenderer("Test")
        event = StreamEvent(
            type=EventType.EXECUTION_ERROR,
            data={"error_type": "TestError", "error_message": "Test error"},
            execution_id="exec_1",
        )
        renderer.handle_event(event)
        assert renderer.phase == EventPhase.ERROR
        assert renderer.progress_percent == -1

    def test_handle_phase_change(self):
        """Test handling phase_change event."""
        renderer = KivaLiveRenderer("Test")
        event = StreamEvent(
            type=EventType.PHASE_CHANGE,
            data={
                "previous_phase": "analyzing",
                "current_phase": "executing",
                "progress_percent": 50,
            },
            execution_id="exec_1",
            timestamp=2000.0,
        )
        renderer.handle_event(event)
        assert renderer.phase == EventPhase.EXECUTING
        assert renderer.progress_percent == 50
        assert renderer.phase_start_time == 2000.0

    def test_handle_planning_start(self):
        """Test handling planning_start event."""
        renderer = KivaLiveRenderer("Test")
        event = StreamEvent(
            type=EventType.PLANNING_START,
            data={"prompt": "Test", "available_agents": []},
            execution_id="exec_1",
        )
        renderer.handle_event(event)
        assert renderer.phase == EventPhase.ANALYZING
        assert renderer.token_buffer == ""

    def test_handle_planning_progress(self):
        """Test handling planning_progress event."""
        renderer = KivaLiveRenderer("Test")
        event = StreamEvent(
            type=EventType.PLANNING_PROGRESS,
            data={"content": "new", "accumulated_content": "accumulated content"},
            execution_id="exec_1",
        )
        renderer.handle_event(event)
        assert renderer.token_buffer == "accumulated content"

    def test_handle_workflow_selected(self):
        """Test handling workflow_selected event."""
        renderer = KivaLiveRenderer("Test")
        event = StreamEvent(
            type=EventType.WORKFLOW_SELECTED,
            data={
                "workflow": "router",
                "complexity": "low",
                "task_assignments": [{"agent_id": "agent_1", "task": "Task 1"}],
                "parallel_strategy": "none",
                "total_instances": 1,
            },
            execution_id="exec_1",
        )
        renderer.handle_event(event)
        assert renderer.workflow_info["workflow"] == "router"
        assert renderer.workflow_info["complexity"] == "low"
        assert renderer.phase == EventPhase.EXECUTING
        assert "agent_1" in renderer.states


class TestKivaLiveRendererAgentEvents:
    """Tests for agent event handling."""

    def test_handle_agent_start(self):
        """Test handling agent_start event."""
        renderer = KivaLiveRenderer("Test")
        event = StreamEvent(
            type=EventType.AGENT_START,
            data={"agent_id": "agent_1", "task": "Test task"},
            execution_id="exec_1",
            timestamp=1000.0,
        )
        renderer.handle_event(event)
        assert "agent_1" in renderer.states
        assert renderer.states["agent_1"].status == "running"
        assert renderer.states["agent_1"].task == "Test task"
        assert renderer.states["agent_1"].start_time == 1000.0

    def test_handle_agent_progress(self):
        """Test handling agent_progress event."""
        renderer = KivaLiveRenderer("Test")
        # First start the agent
        renderer.states["agent_1"] = ExecutionState(id="agent_1", agent_id="agent_1")
        event = StreamEvent(
            type=EventType.AGENT_PROGRESS,
            data={
                "agent_id": "agent_1",
                "content": "Working on task",
                "tool_calls": [{"name": "tool1"}],
            },
            execution_id="exec_1",
        )
        renderer.handle_event(event)
        assert renderer.states["agent_1"].current_action == "Working on task"
        assert renderer.states["agent_1"].tool_calls == [{"name": "tool1"}]

    def test_handle_agent_end(self):
        """Test handling agent_end event."""
        renderer = KivaLiveRenderer("Test")
        renderer.states["agent_1"] = ExecutionState(
            id="agent_1", agent_id="agent_1", status="running"
        )
        event = StreamEvent(
            type=EventType.AGENT_END,
            data={"agent_id": "agent_1", "result": "Task completed"},
            execution_id="exec_1",
            timestamp=2000.0,
        )
        renderer.handle_event(event)
        assert renderer.states["agent_1"].status == "completed"
        assert renderer.states["agent_1"].result == "Task completed"
        assert renderer.states["agent_1"].end_time == 2000.0

    def test_handle_agent_error(self):
        """Test handling agent_error event."""
        renderer = KivaLiveRenderer("Test")
        renderer.states["agent_1"] = ExecutionState(
            id="agent_1", agent_id="agent_1", status="running"
        )
        event = StreamEvent(
            type=EventType.AGENT_ERROR,
            data={"agent_id": "agent_1", "error_message": "Something went wrong"},
            execution_id="exec_1",
        )
        renderer.handle_event(event)
        assert renderer.states["agent_1"].status == "error"
        assert renderer.states["agent_1"].error == "Something went wrong"

    def test_handle_agent_retry(self):
        """Test handling agent_retry event."""
        renderer = KivaLiveRenderer("Test")
        renderer.states["agent_1"] = ExecutionState(
            id="agent_1", agent_id="agent_1", status="running"
        )
        event = StreamEvent(
            type=EventType.AGENT_RETRY,
            data={"agent_id": "agent_1", "attempt": 2, "max_retries": 3},
            execution_id="exec_1",
        )
        renderer.handle_event(event)
        assert renderer.states["agent_1"].status == "retrying"
        assert renderer.states["agent_1"].retry_count == 2


class TestKivaLiveRendererInstanceEvents:
    """Tests for instance event handling."""

    def test_handle_instance_spawn(self):
        """Test handling instance_spawn event."""
        renderer = KivaLiveRenderer("Test")
        event = StreamEvent(
            type=EventType.INSTANCE_SPAWN,
            data={
                "instance_id": "inst_1",
                "agent_id": "agent_1",
                "task": "Instance task",
                "instance_num": 0,
            },
            execution_id="exec_1",
        )
        renderer.handle_event(event)
        assert "inst_1" in renderer.states
        assert renderer.states["inst_1"].status == "spawned"
        assert renderer.states["inst_1"].agent_id == "agent_1"
        assert renderer.states["inst_1"].task == "Instance task"

    def test_handle_instance_start(self):
        """Test handling instance_start event."""
        renderer = KivaLiveRenderer("Test")
        renderer.states["inst_1"] = ExecutionState(
            id="inst_1", agent_id="agent_1", status="spawned", instance_num=0
        )
        event = StreamEvent(
            type=EventType.INSTANCE_START,
            data={"instance_id": "inst_1", "agent_id": "agent_1", "task": "Task"},
            execution_id="exec_1",
            timestamp=1000.0,
        )
        renderer.handle_event(event)
        assert renderer.states["inst_1"].status == "running"
        assert renderer.states["inst_1"].start_time == 1000.0

    def test_handle_instance_end(self):
        """Test handling instance_end event."""
        renderer = KivaLiveRenderer("Test")
        renderer.states["inst_1"] = ExecutionState(
            id="inst_1", agent_id="agent_1", status="running", instance_num=0
        )
        event = StreamEvent(
            type=EventType.INSTANCE_END,
            data={"instance_id": "inst_1", "result": "Done"},
            execution_id="exec_1",
            timestamp=2000.0,
        )
        renderer.handle_event(event)
        assert renderer.states["inst_1"].status == "completed"
        assert renderer.states["inst_1"].result == "Done"
        assert renderer.states["inst_1"].end_time == 2000.0

    def test_handle_instance_error(self):
        """Test handling instance_error event."""
        renderer = KivaLiveRenderer("Test")
        renderer.states["inst_1"] = ExecutionState(
            id="inst_1", agent_id="agent_1", status="running", instance_num=0
        )
        event = StreamEvent(
            type=EventType.INSTANCE_ERROR,
            data={"instance_id": "inst_1", "error_message": "Failed"},
            execution_id="exec_1",
        )
        renderer.handle_event(event)
        assert renderer.states["inst_1"].status == "error"
        assert renderer.states["inst_1"].error == "Failed"


class TestKivaLiveRendererParallelEvents:
    """Tests for parallel execution event handling."""

    def test_handle_parallel_start(self):
        """Test handling parallel_start event."""
        renderer = KivaLiveRenderer("Test")
        event = StreamEvent(
            type=EventType.PARALLEL_START,
            data={
                "batch_id": "batch_1",
                "agent_ids": ["agent_1", "agent_2"],
                "instance_count": 4,
            },
            execution_id="exec_1",
            timestamp=1000.0,
        )
        renderer.handle_event(event)
        assert "batch_1" in renderer.parallel_batches
        assert renderer.parallel_batches["batch_1"].agent_ids == ["agent_1", "agent_2"]
        assert renderer.parallel_batches["batch_1"].instance_count == 4
        assert renderer.parallel_batches["batch_1"].start_time == 1000.0

    def test_handle_parallel_progress(self):
        """Test handling parallel_progress event."""
        renderer = KivaLiveRenderer("Test")
        renderer.parallel_batches["batch_1"] = BatchState(
            batch_id="batch_1", instance_count=4
        )
        event = StreamEvent(
            type=EventType.PARALLEL_PROGRESS,
            data={
                "batch_id": "batch_1",
                "completed_count": 2,
                "progress_percent": 50,
            },
            execution_id="exec_1",
        )
        renderer.handle_event(event)
        assert renderer.parallel_batches["batch_1"].completed == 2
        assert renderer.parallel_batches["batch_1"].progress == 50

    def test_handle_parallel_complete(self):
        """Test handling parallel_complete event."""
        renderer = KivaLiveRenderer("Test")
        renderer.parallel_batches["batch_1"] = BatchState(
            batch_id="batch_1", instance_count=4
        )
        event = StreamEvent(
            type=EventType.PARALLEL_COMPLETE,
            data={
                "batch_id": "batch_1",
                "success_count": 3,
                "failure_count": 1,
            },
            execution_id="exec_1",
            timestamp=2000.0,
        )
        renderer.handle_event(event)
        assert renderer.parallel_batches["batch_1"].completed == 3
        assert renderer.parallel_batches["batch_1"].failed == 1
        assert renderer.parallel_batches["batch_1"].end_time == 2000.0
        assert renderer.parallel_batches["batch_1"].progress == 100


class TestKivaLiveRendererSynthesisEvents:
    """Tests for synthesis event handling."""

    def test_handle_synthesis_start(self):
        """Test handling synthesis_start event."""
        renderer = KivaLiveRenderer("Test")
        event = StreamEvent(
            type=EventType.SYNTHESIS_START,
            data={"input_count": 3, "successful_count": 3, "failed_count": 0},
            execution_id="exec_1",
            timestamp=1000.0,
        )
        renderer.handle_event(event)
        assert renderer.phase == EventPhase.SYNTHESIZING
        assert renderer.synthesis_buffer == ""
        assert renderer.phase_start_time == 1000.0

    def test_handle_synthesis_progress(self):
        """Test handling synthesis_progress event."""
        renderer = KivaLiveRenderer("Test")
        event = StreamEvent(
            type=EventType.SYNTHESIS_PROGRESS,
            data={"content": "new", "accumulated_content": "Synthesized content"},
            execution_id="exec_1",
        )
        renderer.handle_event(event)
        assert renderer.synthesis_buffer == "Synthesized content"

    def test_handle_synthesis_complete(self):
        """Test handling synthesis_complete event."""
        renderer = KivaLiveRenderer("Test")
        event = StreamEvent(
            type=EventType.SYNTHESIS_COMPLETE,
            data={
                "result": "Final result",
                "citations": ["agent_1", "agent_2"],
                "is_partial": False,
            },
            execution_id="exec_1",
        )
        renderer.handle_event(event)
        assert renderer.final_result == "Final result"
        assert renderer.citations == ["agent_1", "agent_2"]
        assert renderer.phase == EventPhase.COMPLETE


class TestKivaLiveRendererTokenEvent:
    """Tests for token event handling."""

    def test_handle_token(self):
        """Test handling token event."""
        renderer = KivaLiveRenderer("Test")
        event = StreamEvent(
            type=EventType.TOKEN,
            data={"content": "Hello "},
            execution_id="exec_1",
        )
        renderer.handle_event(event)
        assert renderer.token_buffer == "Hello "

    def test_handle_token_transitions_phase(self):
        """Test token event transitions from initializing to analyzing."""
        renderer = KivaLiveRenderer("Test")
        assert renderer.phase == EventPhase.INITIALIZING
        event = StreamEvent(
            type=EventType.TOKEN,
            data={"content": "Starting"},
            execution_id="exec_1",
        )
        renderer.handle_event(event)
        assert renderer.phase == EventPhase.ANALYZING
