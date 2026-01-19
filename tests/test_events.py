"""Property-based tests for event definitions.

This module contains property-based tests using Hypothesis to verify
the correctness of event type enums and StreamEvent serialization.
"""

import re

from hypothesis import given, settings, strategies as st

from kiva.events import EventPhase, EventSeverity, EventType, StreamEvent


# Custom strategies for StreamEvent generation
def stream_event_strategy():
    """Strategy for generating valid StreamEvent instances."""
    return st.builds(
        StreamEvent,
        type=st.sampled_from(list(EventType)),
        phase=st.sampled_from(list(EventPhase)),
        severity=st.sampled_from(list(EventSeverity)),
        execution_id=st.text(min_size=1, max_size=36),
        data=st.dictionaries(
            st.text(min_size=1, max_size=20).filter(lambda x: x.isidentifier()),
            st.one_of(st.text(max_size=100), st.integers(), st.floats(allow_nan=False), st.booleans()),
            max_size=5,
        ),
        metadata=st.dictionaries(
            st.text(min_size=1, max_size=20).filter(lambda x: x.isidentifier()),
            st.one_of(st.text(max_size=100), st.integers(), st.floats(allow_nan=False), st.booleans()),
            max_size=3,
        ),
        agent_id=st.one_of(st.none(), st.text(min_size=1, max_size=36)),
        instance_id=st.one_of(st.none(), st.text(min_size=1, max_size=36)),
    )


class TestEventEnums:
    """Property-based tests for event enums.

    Feature: stream-event-refactor, Property 3: Event Enums Contain Expected Values
    Validates: Requirements 1.1, 1.2, 1.3
    """

    # Expected EventType values from Requirements 1.1
    EXPECTED_EVENT_TYPES = {
        # Lifecycle events
        "execution_start",
        "execution_end",
        "execution_error",
        # Phase events
        "phase_change",
        # Planning events
        "planning_start",
        "planning_progress",
        "planning_complete",
        # Workflow events
        "workflow_selected",
        "workflow_start",
        "workflow_end",
        # Agent events
        "agent_start",
        "agent_progress",
        "agent_end",
        "agent_error",
        "agent_retry",
        # Instance events
        "instance_spawn",
        "instance_start",
        "instance_progress",
        "instance_end",
        "instance_error",
        "instance_retry",
        # Parallel events
        "parallel_start",
        "parallel_progress",
        "parallel_complete",
        # Synthesis events
        "synthesis_start",
        "synthesis_progress",
        "synthesis_complete",
        # Token events
        "token",
        # Tool events
        "tool_call_start",
        "tool_call_end",
        # Debug events
        "debug",
    }

    # Expected EventPhase values from Requirements 1.2
    EXPECTED_PHASES = {
        "initializing",
        "analyzing",
        "executing",
        "synthesizing",
        "complete",
        "error",
    }

    # Expected EventSeverity values from Requirements 1.3
    EXPECTED_SEVERITIES = {
        "debug",
        "info",
        "warning",
        "error",
    }

    @given(st.sampled_from(list(EventType)))
    @settings(max_examples=100)
    def test_event_type_values_are_expected(self, event_type: EventType):
        """Property 3: All EventType enum values are in the expected set.

        Feature: stream-event-refactor, Property 3: Event Enums Contain Expected Values
        Validates: Requirements 1.1
        """
        assert event_type.value in self.EXPECTED_EVENT_TYPES

    @given(st.sampled_from(list(EventPhase)))
    @settings(max_examples=100)
    def test_event_phase_values_are_expected(self, phase: EventPhase):
        """Property 3: All EventPhase enum values are in the expected set.

        Feature: stream-event-refactor, Property 3: Event Enums Contain Expected Values
        Validates: Requirements 1.2
        """
        assert phase.value in self.EXPECTED_PHASES

    @given(st.sampled_from(list(EventSeverity)))
    @settings(max_examples=100)
    def test_event_severity_values_are_expected(self, severity: EventSeverity):
        """Property 3: All EventSeverity enum values are in the expected set.

        Feature: stream-event-refactor, Property 3: Event Enums Contain Expected Values
        Validates: Requirements 1.3
        """
        assert severity.value in self.EXPECTED_SEVERITIES

    def test_event_type_contains_all_expected_values(self):
        """Verify EventType enum contains all expected values from requirements.

        Feature: stream-event-refactor, Property 3: Event Enums Contain Expected Values
        Validates: Requirements 1.1
        """
        actual_values = {e.value for e in EventType}
        assert self.EXPECTED_EVENT_TYPES == actual_values

    def test_event_phase_contains_all_expected_values(self):
        """Verify EventPhase enum contains all expected values from requirements.

        Feature: stream-event-refactor, Property 3: Event Enums Contain Expected Values
        Validates: Requirements 1.2
        """
        actual_values = {e.value for e in EventPhase}
        assert self.EXPECTED_PHASES == actual_values

    def test_event_severity_contains_all_expected_values(self):
        """Verify EventSeverity enum contains all expected values from requirements.

        Feature: stream-event-refactor, Property 3: Event Enums Contain Expected Values
        Validates: Requirements 1.3
        """
        actual_values = {e.value for e in EventSeverity}
        assert self.EXPECTED_SEVERITIES == actual_values

    @given(st.sampled_from(list(EventType)))
    @settings(max_examples=100)
    def test_event_type_is_string_enum(self, event_type: EventType):
        """Property: EventType values are strings and can be used as strings.

        Feature: stream-event-refactor, Property 3: Event Enums Contain Expected Values
        Validates: Requirements 1.1
        """
        # EventType inherits from str, so it should be usable as a string
        assert isinstance(event_type.value, str)
        assert event_type == event_type.value

    @given(st.sampled_from(list(EventPhase)))
    @settings(max_examples=100)
    def test_event_phase_is_string_enum(self, phase: EventPhase):
        """Property: EventPhase values are strings and can be used as strings.

        Feature: stream-event-refactor, Property 3: Event Enums Contain Expected Values
        Validates: Requirements 1.2
        """
        assert isinstance(phase.value, str)
        assert phase == phase.value

    @given(st.sampled_from(list(EventSeverity)))
    @settings(max_examples=100)
    def test_event_severity_is_string_enum(self, severity: EventSeverity):
        """Property: EventSeverity values are strings and can be used as strings.

        Feature: stream-event-refactor, Property 3: Event Enums Contain Expected Values
        Validates: Requirements 1.3
        """
        assert isinstance(severity.value, str)
        assert severity == severity.value


class TestStreamEventProperties:
    """Property-based tests for StreamEvent serialization.

    Feature: stream-event-refactor
    Validates: Requirements 2.1, 2.2, 2.3, 2.4, 13.2, 13.3, 13.4, 14.1-14.5
    """

    @given(stream_event_strategy())
    @settings(max_examples=100)
    def test_stream_event_dict_round_trip(self, event: StreamEvent):
        """Property 1: StreamEvent Dict Serialization Round-Trip.

        For any valid StreamEvent instance, calling to_dict() followed by
        from_dict() on the result SHALL produce an equivalent StreamEvent
        with all fields preserved.

        Feature: stream-event-refactor, Property 1: StreamEvent Dict Serialization Round-Trip
        Validates: Requirements 2.2, 2.4, 14.3, 14.4, 14.5
        """
        serialized = event.to_dict()
        deserialized = StreamEvent.from_dict(serialized)

        assert deserialized.event_id == event.event_id
        assert deserialized.type == event.type
        assert deserialized.phase == event.phase
        assert deserialized.severity == event.severity
        assert deserialized.timestamp == event.timestamp
        assert deserialized.execution_id == event.execution_id
        assert deserialized.data == event.data
        assert deserialized.metadata == event.metadata
        assert deserialized.agent_id == event.agent_id
        assert deserialized.instance_id == event.instance_id

    @given(stream_event_strategy())
    @settings(max_examples=100)
    def test_stream_event_json_round_trip(self, event: StreamEvent):
        """Property 2: StreamEvent JSON Serialization Round-Trip.

        For any valid StreamEvent instance, calling to_json() followed by
        from_json() on the result SHALL produce an equivalent StreamEvent
        with all fields preserved.

        Feature: stream-event-refactor, Property 2: StreamEvent JSON Serialization Round-Trip
        Validates: Requirements 2.3, 13.2, 14.1, 14.2
        """
        json_str = event.to_json()
        deserialized = StreamEvent.from_json(json_str)

        assert deserialized.event_id == event.event_id
        assert deserialized.type == event.type
        assert deserialized.phase == event.phase
        assert deserialized.severity == event.severity
        assert deserialized.timestamp == event.timestamp
        assert deserialized.execution_id == event.execution_id
        assert deserialized.data == event.data
        assert deserialized.metadata == event.metadata
        assert deserialized.agent_id == event.agent_id
        assert deserialized.instance_id == event.instance_id

    @given(stream_event_strategy())
    @settings(max_examples=100)
    def test_stream_event_required_fields_present(self, event: StreamEvent):
        """Property 4: StreamEvent Required Fields Present.

        For any StreamEvent instance created via the constructor or factory,
        all required fields (event_id, type, phase, severity, timestamp,
        execution_id, data) SHALL be present and non-null.

        Feature: stream-event-refactor, Property 4: StreamEvent Required Fields Present
        Validates: Requirements 2.1
        """
        assert event.event_id is not None
        assert event.type is not None
        assert event.phase is not None
        assert event.severity is not None
        assert event.timestamp is not None
        assert event.execution_id is not None
        assert event.data is not None

        # Verify types
        assert isinstance(event.event_id, str)
        assert isinstance(event.type, EventType)
        assert isinstance(event.phase, EventPhase)
        assert isinstance(event.severity, EventSeverity)
        assert isinstance(event.timestamp, float)
        assert isinstance(event.execution_id, str)
        assert isinstance(event.data, dict)

    @given(stream_event_strategy())
    @settings(max_examples=100)
    def test_json_output_format_compliance(self, event: StreamEvent):
        """Property 5: JSON Output Format Compliance.

        For any StreamEvent serialized to dict, all dictionary keys SHALL be
        in snake_case format, and the output SHALL include a valid ISO 8601
        formatted timestamp_iso field.

        Feature: stream-event-refactor, Property 5: JSON Output Format Compliance
        Validates: Requirements 13.3, 13.4
        """
        serialized = event.to_dict()

        # Check all keys are snake_case
        snake_case_pattern = re.compile(r"^[a-z][a-z0-9_]*$")
        for key in serialized.keys():
            assert snake_case_pattern.match(key), f"Key '{key}' is not snake_case"

        # Check timestamp_iso is present and valid ISO 8601
        assert "timestamp_iso" in serialized
        timestamp_iso = serialized["timestamp_iso"]
        assert isinstance(timestamp_iso, str)
        # ISO 8601 format: YYYY-MM-DDTHH:MM:SS.ffffff+HH:MM or similar
        iso_pattern = re.compile(
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(\+\d{2}:\d{2}|Z)?$"
        )
        assert iso_pattern.match(timestamp_iso), f"timestamp_iso '{timestamp_iso}' is not valid ISO 8601"


class TestEventFactory:
    """Unit tests for EventFactory.

    Tests all convenience methods to ensure they generate correct events.
    Validates: Requirements 3.1-11.2
    """

    def test_factory_initialization(self):
        """Test EventFactory initializes with correct defaults.

        Validates: Requirements 3.1, 4.1
        """
        from kiva.events import EventFactory

        factory = EventFactory("exec-123")

        assert factory.execution_id == "exec-123"
        assert factory.current_phase == EventPhase.INITIALIZING
        assert factory.start_time > 0

    def test_set_phase(self):
        """Test set_phase updates current_phase.

        Validates: Requirements 4.1
        """
        from kiva.events import EventFactory

        factory = EventFactory("exec-123")
        factory.set_phase(EventPhase.ANALYZING)

        assert factory.current_phase == EventPhase.ANALYZING

    def test_create_method(self):
        """Test generic create() method produces correct StreamEvent.

        Validates: Requirements 2.1
        """
        from kiva.events import EventFactory

        factory = EventFactory("exec-123")
        event = factory.create(
            EventType.DEBUG,
            {"message": "test"},
            severity=EventSeverity.DEBUG,
            agent_id="agent-1",
            instance_id="instance-1",
            metadata={"key": "value"},
        )

        assert event.type == EventType.DEBUG
        assert event.phase == EventPhase.INITIALIZING
        assert event.severity == EventSeverity.DEBUG
        assert event.execution_id == "exec-123"
        assert event.data == {"message": "test"}
        assert event.agent_id == "agent-1"
        assert event.instance_id == "instance-1"
        assert event.metadata == {"key": "value"}

    # =========================================================================
    # Lifecycle Events Tests (Requirements 3.1, 3.2, 3.3)
    # =========================================================================

    def test_execution_start(self):
        """Test execution_start event creation.

        Validates: Requirements 3.1
        """
        from kiva.events import EventFactory

        class MockAgent:
            name = "test-agent"

        factory = EventFactory("exec-123")
        event = factory.execution_start(
            prompt="Test prompt",
            agents=[MockAgent(), MockAgent()],
            config={"model_name": "gpt-4o"},
        )

        assert event.type == EventType.EXECUTION_START
        assert event.data["prompt"] == "Test prompt"
        assert event.data["agent_count"] == 2
        assert event.data["agent_names"] == ["test-agent", "test-agent"]
        assert event.data["config"] == {"model_name": "gpt-4o"}

    def test_execution_start_with_unnamed_agents(self):
        """Test execution_start handles agents without name attribute.

        Validates: Requirements 3.1
        """
        from kiva.events import EventFactory

        factory = EventFactory("exec-123")
        event = factory.execution_start(
            prompt="Test",
            agents=[object(), object()],
            config={},
        )

        assert event.data["agent_names"] == ["agent_0", "agent_1"]

    def test_execution_end(self):
        """Test execution_end event creation.

        Validates: Requirements 3.2
        """
        from kiva.events import EventFactory

        factory = EventFactory("exec-123")
        event = factory.execution_end(
            result="Final result",
            agent_results_count=3,
            success=True,
        )

        assert event.type == EventType.EXECUTION_END
        assert event.data["result"] == "Final result"
        assert event.data["agent_results_count"] == 3
        assert event.data["success"] is True
        assert "duration_ms" in event.data
        assert event.data["duration_ms"] >= 0

    def test_execution_end_truncates_long_result(self):
        """Test execution_end truncates result to 500 chars.

        Validates: Requirements 3.2
        """
        from kiva.events import EventFactory

        factory = EventFactory("exec-123")
        long_result = "x" * 1000
        event = factory.execution_end(
            result=long_result,
            agent_results_count=1,
        )

        assert len(event.data["result"]) == 500

    def test_execution_error(self):
        """Test execution_error event creation.

        Validates: Requirements 3.3
        """
        from kiva.events import EventFactory

        factory = EventFactory("exec-123")
        event = factory.execution_error(
            error_type="ValueError",
            error_message="Something went wrong",
            stack_trace="Traceback...",
            recovery_suggestion="Try again",
        )

        assert event.type == EventType.EXECUTION_ERROR
        assert event.severity == EventSeverity.ERROR
        assert event.data["error_type"] == "ValueError"
        assert event.data["error_message"] == "Something went wrong"
        assert event.data["stack_trace"] == "Traceback..."
        assert event.data["recovery_suggestion"] == "Try again"

    # =========================================================================
    # Phase Events Tests (Requirements 4.1, 4.2)
    # =========================================================================

    def test_phase_change(self):
        """Test phase_change event creation and phase update.

        Validates: Requirements 4.1, 4.2
        """
        from kiva.events import EventFactory

        factory = EventFactory("exec-123")
        event = factory.phase_change(
            previous_phase=EventPhase.INITIALIZING,
            current_phase=EventPhase.ANALYZING,
            progress_percent=25,
            message="Starting analysis",
        )

        assert event.type == EventType.PHASE_CHANGE
        assert event.data["previous_phase"] == "initializing"
        assert event.data["current_phase"] == "analyzing"
        assert event.data["progress_percent"] == 25
        assert event.data["message"] == "Starting analysis"
        # Verify factory phase was updated
        assert factory.current_phase == EventPhase.ANALYZING

    # =========================================================================
    # Planning Events Tests (Requirements 5.1, 5.2, 5.3)
    # =========================================================================

    def test_planning_start(self):
        """Test planning_start event creation.

        Validates: Requirements 5.1
        """
        from kiva.events import EventFactory

        factory = EventFactory("exec-123")
        event = factory.planning_start(
            prompt="Analyze this task",
            available_agents=[{"name": "agent1", "description": "desc1"}],
        )

        assert event.type == EventType.PLANNING_START
        assert event.data["prompt"] == "Analyze this task"
        assert event.data["available_agents"] == [{"name": "agent1", "description": "desc1"}]

    def test_planning_progress(self):
        """Test planning_progress event creation.

        Validates: Requirements 5.2
        """
        from kiva.events import EventFactory

        factory = EventFactory("exec-123")
        event = factory.planning_progress(
            content="new token",
            accumulated_content="all tokens so far",
        )

        assert event.type == EventType.PLANNING_PROGRESS
        assert event.data["content"] == "new token"
        assert event.data["accumulated_content"] == "all tokens so far"

    def test_planning_complete(self):
        """Test planning_complete event creation.

        Validates: Requirements 5.3
        """
        from kiva.events import EventFactory

        factory = EventFactory("exec-123")
        event = factory.planning_complete(
            complexity="medium",
            workflow="supervisor",
            reasoning="Task requires coordination",
            task_assignments=[{"agent": "agent1", "task": "subtask1"}],
            parallel_strategy="concurrent",
            total_instances=3,
            duration_ms=1500,
        )

        assert event.type == EventType.PLANNING_COMPLETE
        assert event.data["complexity"] == "medium"
        assert event.data["workflow"] == "supervisor"
        assert event.data["reasoning"] == "Task requires coordination"
        assert event.data["task_assignments"] == [{"agent": "agent1", "task": "subtask1"}]
        assert event.data["parallel_strategy"] == "concurrent"
        assert event.data["total_instances"] == 3
        assert event.data["duration_ms"] == 1500

    # =========================================================================
    # Workflow Events Tests (Requirements 6.1, 6.2, 6.3)
    # =========================================================================

    def test_workflow_selected(self):
        """Test workflow_selected event creation.

        Validates: Requirements 6.1
        """
        from kiva.events import EventFactory

        factory = EventFactory("exec-123")
        event = factory.workflow_selected(
            workflow="supervisor",
            complexity="high",
            task_assignments=[{"agent": "a1", "task": "t1"}],
            parallel_strategy="batch",
            total_instances=5,
        )

        assert event.type == EventType.WORKFLOW_SELECTED
        assert event.data["workflow"] == "supervisor"
        assert event.data["complexity"] == "high"
        assert event.data["task_assignments"] == [{"agent": "a1", "task": "t1"}]
        assert event.data["parallel_strategy"] == "batch"
        assert event.data["total_instances"] == 5

    def test_workflow_start(self):
        """Test workflow_start event creation.

        Validates: Requirements 6.2
        """
        from kiva.events import EventFactory

        factory = EventFactory("exec-123")
        event = factory.workflow_start(
            workflow="parliament",
            agent_ids=["agent1", "agent2"],
            iteration=2,
        )

        assert event.type == EventType.WORKFLOW_START
        assert event.data["workflow"] == "parliament"
        assert event.data["agent_ids"] == ["agent1", "agent2"]
        assert event.data["iteration"] == 2

    def test_workflow_end(self):
        """Test workflow_end event creation.

        Validates: Requirements 6.3
        """
        from kiva.events import EventFactory

        factory = EventFactory("exec-123")
        event = factory.workflow_end(
            workflow="parliament",
            success=True,
            results_count=3,
            duration_ms=5000,
            conflicts_found=1,
        )

        assert event.type == EventType.WORKFLOW_END
        assert event.data["workflow"] == "parliament"
        assert event.data["success"] is True
        assert event.data["results_count"] == 3
        assert event.data["duration_ms"] == 5000
        assert event.data["conflicts_found"] == 1

    # =========================================================================
    # Agent Events Tests (Requirements 7.1, 7.2, 7.3, 7.4, 7.5)
    # =========================================================================

    def test_agent_start(self):
        """Test agent_start event creation.

        Validates: Requirements 7.1
        """
        from kiva.events import EventFactory

        factory = EventFactory("exec-123")
        event = factory.agent_start(
            agent_id="agent-1",
            invocation_id="inv-123",
            task="Process data",
            iteration=1,
        )

        assert event.type == EventType.AGENT_START
        assert event.agent_id == "agent-1"
        assert event.data["agent_id"] == "agent-1"
        assert event.data["invocation_id"] == "inv-123"
        assert event.data["task"] == "Process data"
        assert event.data["iteration"] == 1

    def test_agent_progress(self):
        """Test agent_progress event creation.

        Validates: Requirements 7.2
        """
        from kiva.events import EventFactory

        factory = EventFactory("exec-123")
        event = factory.agent_progress(
            agent_id="agent-1",
            invocation_id="inv-123",
            message_type="ai",
            content="Processing...",
            tool_calls=[{"name": "search", "args": {}}],
        )

        assert event.type == EventType.AGENT_PROGRESS
        assert event.agent_id == "agent-1"
        assert event.data["message_type"] == "ai"
        assert event.data["content"] == "Processing..."
        assert event.data["tool_calls"] == [{"name": "search", "args": {}}]

    def test_agent_end(self):
        """Test agent_end event creation.

        Validates: Requirements 7.3
        """
        from kiva.events import EventFactory

        factory = EventFactory("exec-123")
        event = factory.agent_end(
            agent_id="agent-1",
            invocation_id="inv-123",
            result="Task completed",
            duration_ms=2000,
            success=True,
        )

        assert event.type == EventType.AGENT_END
        assert event.agent_id == "agent-1"
        assert event.data["result"] == "Task completed"
        assert event.data["duration_ms"] == 2000
        assert event.data["success"] is True

    def test_agent_error(self):
        """Test agent_error event creation.

        Validates: Requirements 7.4
        """
        from kiva.events import EventFactory

        factory = EventFactory("exec-123")
        event = factory.agent_error(
            agent_id="agent-1",
            invocation_id="inv-123",
            error_type="RuntimeError",
            error_message="Agent failed",
            recovery_suggestion="Retry with different params",
        )

        assert event.type == EventType.AGENT_ERROR
        assert event.severity == EventSeverity.ERROR
        assert event.agent_id == "agent-1"
        assert event.data["error_type"] == "RuntimeError"
        assert event.data["error_message"] == "Agent failed"
        assert event.data["recovery_suggestion"] == "Retry with different params"

    def test_agent_retry(self):
        """Test agent_retry event creation.

        Validates: Requirements 7.5
        """
        from kiva.events import EventFactory

        factory = EventFactory("exec-123")
        event = factory.agent_retry(
            agent_id="agent-1",
            invocation_id="inv-123",
            attempt=2,
            max_retries=3,
            reason="Timeout",
        )

        assert event.type == EventType.AGENT_RETRY
        assert event.severity == EventSeverity.WARNING
        assert event.agent_id == "agent-1"
        assert event.data["attempt"] == 2
        assert event.data["max_retries"] == 3
        assert event.data["reason"] == "Timeout"

    # =========================================================================
    # Instance Events Tests (Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6)
    # =========================================================================

    def test_instance_spawn(self):
        """Test instance_spawn event creation.

        Validates: Requirements 8.1
        """
        from kiva.events import EventFactory

        factory = EventFactory("exec-123")
        event = factory.instance_spawn(
            instance_id="inst-1",
            agent_id="agent-1",
            task="Subtask 1",
            instance_num=0,
            context={"key": "value"},
        )

        assert event.type == EventType.INSTANCE_SPAWN
        assert event.agent_id == "agent-1"
        assert event.instance_id == "inst-1"
        assert event.data["instance_id"] == "inst-1"
        assert event.data["agent_id"] == "agent-1"
        assert event.data["task"] == "Subtask 1"
        assert event.data["instance_num"] == 0
        assert event.data["context"] == {"key": "value"}

    def test_instance_start(self):
        """Test instance_start event creation.

        Validates: Requirements 8.2
        """
        from kiva.events import EventFactory

        factory = EventFactory("exec-123")
        event = factory.instance_start(
            instance_id="inst-1",
            agent_id="agent-1",
            task="Execute subtask",
        )

        assert event.type == EventType.INSTANCE_START
        assert event.agent_id == "agent-1"
        assert event.instance_id == "inst-1"
        assert event.data["task"] == "Execute subtask"

    def test_instance_progress(self):
        """Test instance_progress event creation.

        Validates: Requirements 8.3
        """
        from kiva.events import EventFactory

        factory = EventFactory("exec-123")
        event = factory.instance_progress(
            instance_id="inst-1",
            agent_id="agent-1",
            message_type="tool",
            content="Calling tool...",
            tool_calls=[{"name": "fetch", "args": {"url": "http://example.com"}}],
        )

        assert event.type == EventType.INSTANCE_PROGRESS
        assert event.agent_id == "agent-1"
        assert event.instance_id == "inst-1"
        assert event.data["message_type"] == "tool"
        assert event.data["content"] == "Calling tool..."
        assert len(event.data["tool_calls"]) == 1

    def test_instance_end(self):
        """Test instance_end event creation.

        Validates: Requirements 8.4
        """
        from kiva.events import EventFactory

        factory = EventFactory("exec-123")
        event = factory.instance_end(
            instance_id="inst-1",
            agent_id="agent-1",
            result="Instance completed",
            duration_ms=1500,
            success=True,
        )

        assert event.type == EventType.INSTANCE_END
        assert event.agent_id == "agent-1"
        assert event.instance_id == "inst-1"
        assert event.data["result"] == "Instance completed"
        assert event.data["duration_ms"] == 1500
        assert event.data["success"] is True

    def test_instance_error(self):
        """Test instance_error event creation.

        Validates: Requirements 8.5
        """
        from kiva.events import EventFactory

        factory = EventFactory("exec-123")
        event = factory.instance_error(
            instance_id="inst-1",
            agent_id="agent-1",
            error_type="TimeoutError",
            error_message="Instance timed out",
        )

        assert event.type == EventType.INSTANCE_ERROR
        assert event.severity == EventSeverity.ERROR
        assert event.agent_id == "agent-1"
        assert event.instance_id == "inst-1"
        assert event.data["error_type"] == "TimeoutError"
        assert event.data["error_message"] == "Instance timed out"

    def test_instance_retry(self):
        """Test instance_retry event creation.

        Validates: Requirements 8.6
        """
        from kiva.events import EventFactory

        factory = EventFactory("exec-123")
        event = factory.instance_retry(
            instance_id="inst-1",
            agent_id="agent-1",
            attempt=1,
            max_retries=3,
        )

        assert event.type == EventType.INSTANCE_RETRY
        assert event.severity == EventSeverity.WARNING
        assert event.agent_id == "agent-1"
        assert event.instance_id == "inst-1"
        assert event.data["attempt"] == 1
        assert event.data["max_retries"] == 3

    # =========================================================================
    # Parallel Events Tests (Requirements 9.1, 9.2, 9.3)
    # =========================================================================

    def test_parallel_start(self):
        """Test parallel_start event creation.

        Validates: Requirements 9.1
        """
        from kiva.events import EventFactory

        factory = EventFactory("exec-123")
        event = factory.parallel_start(
            batch_id="batch-1",
            agent_ids=["agent-1", "agent-2"],
            instance_count=4,
            strategy="concurrent",
        )

        assert event.type == EventType.PARALLEL_START
        assert event.data["batch_id"] == "batch-1"
        assert event.data["agent_ids"] == ["agent-1", "agent-2"]
        assert event.data["instance_count"] == 4
        assert event.data["strategy"] == "concurrent"

    def test_parallel_progress(self):
        """Test parallel_progress event creation.

        Validates: Requirements 9.2
        """
        from kiva.events import EventFactory

        factory = EventFactory("exec-123")
        event = factory.parallel_progress(
            batch_id="batch-1",
            completed_count=2,
            total_count=4,
            progress_percent=50,
        )

        assert event.type == EventType.PARALLEL_PROGRESS
        assert event.data["batch_id"] == "batch-1"
        assert event.data["completed_count"] == 2
        assert event.data["total_count"] == 4
        assert event.data["progress_percent"] == 50

    def test_parallel_complete(self):
        """Test parallel_complete event creation.

        Validates: Requirements 9.3
        """
        from kiva.events import EventFactory

        factory = EventFactory("exec-123")
        event = factory.parallel_complete(
            batch_id="batch-1",
            results=[{"agent": "a1", "status": "success"}],
            success_count=3,
            failure_count=1,
            duration_ms=10000,
        )

        assert event.type == EventType.PARALLEL_COMPLETE
        assert event.data["batch_id"] == "batch-1"
        assert event.data["results"] == [{"agent": "a1", "status": "success"}]
        assert event.data["success_count"] == 3
        assert event.data["failure_count"] == 1
        assert event.data["duration_ms"] == 10000

    # =========================================================================
    # Synthesis Events Tests (Requirements 10.1, 10.2, 10.3)
    # =========================================================================

    def test_synthesis_start(self):
        """Test synthesis_start event creation.

        Validates: Requirements 10.1
        """
        from kiva.events import EventFactory

        factory = EventFactory("exec-123")
        event = factory.synthesis_start(
            input_count=5,
            successful_count=4,
            failed_count=1,
        )

        assert event.type == EventType.SYNTHESIS_START
        assert event.data["input_count"] == 5
        assert event.data["successful_count"] == 4
        assert event.data["failed_count"] == 1

    def test_synthesis_progress(self):
        """Test synthesis_progress event creation.

        Validates: Requirements 10.2
        """
        from kiva.events import EventFactory

        factory = EventFactory("exec-123")
        event = factory.synthesis_progress(
            content="new content",
            accumulated_content="all content so far",
        )

        assert event.type == EventType.SYNTHESIS_PROGRESS
        assert event.data["content"] == "new content"
        assert event.data["accumulated_content"] == "all content so far"

    def test_synthesis_complete(self):
        """Test synthesis_complete event creation.

        Validates: Requirements 10.3
        """
        from kiva.events import EventFactory

        factory = EventFactory("exec-123")
        event = factory.synthesis_complete(
            result="Final synthesized result",
            citations=["source1", "source2"],
            is_partial=False,
            duration_ms=3000,
        )

        assert event.type == EventType.SYNTHESIS_COMPLETE
        assert event.data["result"] == "Final synthesized result"
        assert event.data["citations"] == ["source1", "source2"]
        assert event.data["is_partial"] is False
        assert event.data["duration_ms"] == 3000

    # =========================================================================
    # Tool Events Tests (Requirements 11.1, 11.2)
    # =========================================================================

    def test_tool_call_start(self):
        """Test tool_call_start event creation.

        Validates: Requirements 11.1
        """
        from kiva.events import EventFactory

        factory = EventFactory("exec-123")
        event = factory.tool_call_start(
            tool_name="search",
            tool_args={"query": "test"},
            call_id="call-123",
            agent_id="agent-1",
            instance_id="inst-1",
        )

        assert event.type == EventType.TOOL_CALL_START
        assert event.agent_id == "agent-1"
        assert event.instance_id == "inst-1"
        assert event.data["tool_name"] == "search"
        assert event.data["tool_args"] == {"query": "test"}
        assert event.data["call_id"] == "call-123"

    def test_tool_call_end(self):
        """Test tool_call_end event creation.

        Validates: Requirements 11.2
        """
        from kiva.events import EventFactory

        factory = EventFactory("exec-123")
        event = factory.tool_call_end(
            tool_name="search",
            call_id="call-123",
            result_preview="Found 10 results...",
            success=True,
            duration_ms=500,
            agent_id="agent-1",
            instance_id="inst-1",
        )

        assert event.type == EventType.TOOL_CALL_END
        assert event.agent_id == "agent-1"
        assert event.instance_id == "inst-1"
        assert event.data["tool_name"] == "search"
        assert event.data["call_id"] == "call-123"
        assert event.data["result_preview"] == "Found 10 results..."
        assert event.data["success"] is True
        assert event.data["duration_ms"] == 500

    # =========================================================================
    # Debug and Token Events Tests
    # =========================================================================

    def test_debug_event(self):
        """Test debug event creation."""
        from kiva.events import EventFactory

        factory = EventFactory("exec-123")
        event = factory.debug(
            message="Debug info",
            details={"key": "value"},
        )

        assert event.type == EventType.DEBUG
        assert event.severity == EventSeverity.DEBUG
        assert event.data["message"] == "Debug info"
        assert event.data["details"] == {"key": "value"}

    def test_token_event(self):
        """Test token event creation."""
        from kiva.events import EventFactory

        factory = EventFactory("exec-123")
        event = factory.token(
            content="Hello",
            agent_id="agent-1",
            instance_id="inst-1",
        )

        assert event.type == EventType.TOKEN
        assert event.agent_id == "agent-1"
        assert event.instance_id == "inst-1"
        assert event.data["content"] == "Hello"


class TestEventFiltering:
    """Property-based tests for event filtering.

    Feature: stream-event-refactor, Property 6: Event Filtering Correctness
    Validates: Requirements 13.5
    """

    def test_should_emit_with_none_filter_returns_true(self):
        """Test that _should_emit returns True when filter is None.

        Feature: stream-event-refactor, Property 6: Event Filtering Correctness
        Validates: Requirements 13.5
        """
        from kiva.run import _should_emit

        # All event types should be emitted when filter is None
        for event_type in EventType:
            assert _should_emit(event_type, None) is True

    def test_should_emit_with_empty_filter_returns_false(self):
        """Test that _should_emit returns False when filter is empty set.

        Feature: stream-event-refactor, Property 6: Event Filtering Correctness
        Validates: Requirements 13.5
        """
        from kiva.run import _should_emit

        empty_filter: set[EventType] = set()
        for event_type in EventType:
            assert _should_emit(event_type, empty_filter) is False

    @given(st.sets(st.sampled_from(list(EventType)), min_size=1, max_size=10))
    @settings(max_examples=100)
    def test_should_emit_returns_true_for_included_types(self, filter_set: set[EventType]):
        """Property 6: Event types in filter set should be emitted.

        For any set of event types used as a filter, _should_emit SHALL return
        True for event types that are in the filter set.

        Feature: stream-event-refactor, Property 6: Event Filtering Correctness
        Validates: Requirements 13.5
        """
        from kiva.run import _should_emit

        for event_type in filter_set:
            assert _should_emit(event_type, filter_set) is True

    @given(st.sets(st.sampled_from(list(EventType)), min_size=1, max_size=len(EventType) - 1))
    @settings(max_examples=100)
    def test_should_emit_returns_false_for_excluded_types(self, filter_set: set[EventType]):
        """Property 6: Event types not in filter set should not be emitted.

        For any set of event types used as a filter, _should_emit SHALL return
        False for event types that are NOT in the filter set.

        Feature: stream-event-refactor, Property 6: Event Filtering Correctness
        Validates: Requirements 13.5
        """
        from kiva.run import _should_emit

        all_types = set(EventType)
        excluded_types = all_types - filter_set

        for event_type in excluded_types:
            assert _should_emit(event_type, filter_set) is False

    @given(
        st.sampled_from(list(EventType)),
        st.sets(st.sampled_from(list(EventType)), min_size=0, max_size=len(EventType)),
    )
    @settings(max_examples=100)
    def test_should_emit_membership_consistency(
        self, event_type: EventType, filter_set: set[EventType]
    ):
        """Property 6: _should_emit result matches set membership.

        For any event type and filter set, _should_emit SHALL return True
        if and only if the event type is in the filter set.

        Feature: stream-event-refactor, Property 6: Event Filtering Correctness
        Validates: Requirements 13.5
        """
        from kiva.run import _should_emit

        expected = event_type in filter_set
        actual = _should_emit(event_type, filter_set)
        assert actual == expected

    def test_should_emit_with_single_type_filter(self):
        """Test filtering with a single event type.

        Feature: stream-event-refactor, Property 6: Event Filtering Correctness
        Validates: Requirements 13.5
        """
        from kiva.run import _should_emit

        single_filter = {EventType.EXECUTION_START}

        assert _should_emit(EventType.EXECUTION_START, single_filter) is True
        assert _should_emit(EventType.EXECUTION_END, single_filter) is False
        assert _should_emit(EventType.AGENT_START, single_filter) is False

    def test_should_emit_with_lifecycle_filter(self):
        """Test filtering with lifecycle event types only.

        Feature: stream-event-refactor, Property 6: Event Filtering Correctness
        Validates: Requirements 13.5
        """
        from kiva.run import _should_emit

        lifecycle_filter = {
            EventType.EXECUTION_START,
            EventType.EXECUTION_END,
            EventType.EXECUTION_ERROR,
        }

        # Lifecycle events should be emitted
        assert _should_emit(EventType.EXECUTION_START, lifecycle_filter) is True
        assert _should_emit(EventType.EXECUTION_END, lifecycle_filter) is True
        assert _should_emit(EventType.EXECUTION_ERROR, lifecycle_filter) is True

        # Non-lifecycle events should not be emitted
        assert _should_emit(EventType.AGENT_START, lifecycle_filter) is False
        assert _should_emit(EventType.TOKEN, lifecycle_filter) is False
        assert _should_emit(EventType.PHASE_CHANGE, lifecycle_filter) is False

    def test_should_emit_with_full_filter(self):
        """Test filtering with all event types included.

        Feature: stream-event-refactor, Property 6: Event Filtering Correctness
        Validates: Requirements 13.5
        """
        from kiva.run import _should_emit

        full_filter = set(EventType)

        # All event types should be emitted
        for event_type in EventType:
            assert _should_emit(event_type, full_filter) is True

    # =========================================================================
    # Property 4: Event Filtering Correctness (streaming-api-optimization)
    # =========================================================================

    @given(st.sets(st.sampled_from(list(EventType)), min_size=1, max_size=len(EventType)))
    @settings(max_examples=100)
    def test_event_filtering_only_yields_filtered_types(
        self, filter_set: set[EventType]
    ):
        """Property 4: Event Filtering Correctness.

        For any event filter set, the _should_emit function SHALL return True
        only for event types present in the filter set, ensuring that yielded
        events only contain event types present in the filter.

        Feature: streaming-api-optimization, Property 4: Event Filtering Correctness
        **Validates: Requirements 5.2, 5.3**
        """
        from kiva.run import _should_emit

        # For all event types, check that _should_emit correctly filters
        for event_type in EventType:
            result = _should_emit(event_type, filter_set)
            expected = event_type in filter_set
            assert result == expected, (
                f"Event type {event_type} should {'be' if expected else 'not be'} "
                f"emitted with filter {filter_set}"
            )

    @given(st.sets(st.sampled_from(list(EventType)), min_size=0, max_size=len(EventType)))
    @settings(max_examples=100)
    def test_event_filtering_no_false_positives(
        self, filter_set: set[EventType]
    ):
        """Property 4: Event Filtering - No False Positives.

        For any event filter set, _should_emit SHALL never return True for
        event types that are NOT in the filter set.

        Feature: streaming-api-optimization, Property 4: Event Filtering Correctness
        **Validates: Requirements 5.2, 5.3**
        """
        from kiva.run import _should_emit

        all_types = set(EventType)
        excluded_types = all_types - filter_set

        # Verify no false positives - excluded types should never be emitted
        for event_type in excluded_types:
            assert _should_emit(event_type, filter_set) is False, (
                f"Event type {event_type} should NOT be emitted when not in filter"
            )

    @given(st.sets(st.sampled_from(list(EventType)), min_size=1, max_size=len(EventType)))
    @settings(max_examples=100)
    def test_event_filtering_no_false_negatives(
        self, filter_set: set[EventType]
    ):
        """Property 4: Event Filtering - No False Negatives.

        For any event filter set, _should_emit SHALL always return True for
        event types that ARE in the filter set.

        Feature: streaming-api-optimization, Property 4: Event Filtering Correctness
        **Validates: Requirements 5.2, 5.3**
        """
        from kiva.run import _should_emit

        # Verify no false negatives - included types should always be emitted
        for event_type in filter_set:
            assert _should_emit(event_type, filter_set) is True, (
                f"Event type {event_type} SHOULD be emitted when in filter"
            )


class TestWorkflowEventLifecycle:
    """Property-based tests for workflow event lifecycle properties.

    Feature: stream-event-refactor
    Properties 8, 9, 10, 11
    Validates: Requirements 7.1-7.3, 8.1-8.4, 9.1-9.3, 11.1-11.2
    """

    # =========================================================================
    # Property 8: Agent Event Lifecycle
    # =========================================================================

    def test_agent_event_lifecycle_sequence(self):
        """Property 8: Agent Event Lifecycle.

        For any agent that executes, the system SHALL emit agent_start before
        any agent_progress events, and agent_end (or agent_error) after all
        progress events, with consistent agent_id across all events.

        Feature: stream-event-refactor, Property 8: Agent Event Lifecycle
        Validates: Requirements 7.1, 7.2, 7.3
        """
        from kiva.events import EventFactory, EventType

        factory = EventFactory("exec-123")
        agent_id = "test-agent"
        invocation_id = "inv-123"

        # Simulate agent lifecycle
        events = []

        # Start event
        events.append(
            factory.agent_start(
                agent_id=agent_id,
                invocation_id=invocation_id,
                task="Test task",
                iteration=1,
            )
        )

        # Progress events
        for i in range(3):
            events.append(
                factory.agent_progress(
                    agent_id=agent_id,
                    invocation_id=invocation_id,
                    message_type="ai",
                    content=f"Progress {i}",
                )
            )

        # End event
        events.append(
            factory.agent_end(
                agent_id=agent_id,
                invocation_id=invocation_id,
                result="Completed",
                duration_ms=1000,
                success=True,
            )
        )

        # Verify lifecycle order
        assert events[0].type == EventType.AGENT_START
        for event in events[1:-1]:
            assert event.type == EventType.AGENT_PROGRESS
        assert events[-1].type == EventType.AGENT_END

        # Verify consistent agent_id
        for event in events:
            assert event.agent_id == agent_id

    @given(st.integers(min_value=0, max_value=10))
    @settings(max_examples=100)
    def test_agent_lifecycle_with_variable_progress(self, num_progress: int):
        """Property 8: Agent lifecycle with variable number of progress events.

        Feature: stream-event-refactor, Property 8: Agent Event Lifecycle
        Validates: Requirements 7.1, 7.2, 7.3
        """
        from kiva.events import EventFactory, EventType

        factory = EventFactory("exec-123")
        agent_id = f"agent-{num_progress}"
        invocation_id = f"inv-{num_progress}"

        events = []

        # Start
        events.append(
            factory.agent_start(
                agent_id=agent_id,
                invocation_id=invocation_id,
                task="Task",
                iteration=1,
            )
        )

        # Variable progress events
        for i in range(num_progress):
            events.append(
                factory.agent_progress(
                    agent_id=agent_id,
                    invocation_id=invocation_id,
                    message_type="ai",
                    content=f"Progress {i}",
                )
            )

        # End
        events.append(
            factory.agent_end(
                agent_id=agent_id,
                invocation_id=invocation_id,
                result="Done",
                duration_ms=100,
                success=True,
            )
        )

        # Verify structure
        assert len(events) == num_progress + 2
        assert events[0].type == EventType.AGENT_START
        assert events[-1].type == EventType.AGENT_END

        # All events have consistent agent_id
        for event in events:
            assert event.agent_id == agent_id

    def test_agent_lifecycle_with_error(self):
        """Property 8: Agent lifecycle ending with error.

        Feature: stream-event-refactor, Property 8: Agent Event Lifecycle
        Validates: Requirements 7.1, 7.2, 7.4
        """
        from kiva.events import EventFactory, EventType

        factory = EventFactory("exec-123")
        agent_id = "error-agent"
        invocation_id = "inv-error"

        events = []

        # Start
        events.append(
            factory.agent_start(
                agent_id=agent_id,
                invocation_id=invocation_id,
                task="Failing task",
                iteration=1,
            )
        )

        # Some progress
        events.append(
            factory.agent_progress(
                agent_id=agent_id,
                invocation_id=invocation_id,
                message_type="ai",
                content="Working...",
            )
        )

        # Error instead of end
        events.append(
            factory.agent_error(
                agent_id=agent_id,
                invocation_id=invocation_id,
                error_type="RuntimeError",
                error_message="Something failed",
            )
        )

        # Verify lifecycle
        assert events[0].type == EventType.AGENT_START
        assert events[1].type == EventType.AGENT_PROGRESS
        assert events[-1].type == EventType.AGENT_ERROR

        # Consistent agent_id
        for event in events:
            assert event.agent_id == agent_id

    # =========================================================================
    # Property 9: Instance Event Lifecycle
    # =========================================================================

    def test_instance_event_lifecycle_sequence(self):
        """Property 9: Instance Event Lifecycle.

        For any instance that executes, the system SHALL emit instance_spawn,
        then instance_start, then any instance_progress events, then
        instance_end (or instance_error), with consistent instance_id.

        Feature: stream-event-refactor, Property 9: Instance Event Lifecycle
        Validates: Requirements 8.1, 8.2, 8.3, 8.4
        """
        from kiva.events import EventFactory, EventType

        factory = EventFactory("exec-123")
        instance_id = "inst-123"
        agent_id = "agent-1"

        events = []

        # Spawn
        events.append(
            factory.instance_spawn(
                instance_id=instance_id,
                agent_id=agent_id,
                task="Instance task",
                instance_num=0,
            )
        )

        # Start
        events.append(
            factory.instance_start(
                instance_id=instance_id,
                agent_id=agent_id,
                task="Instance task",
            )
        )

        # Progress
        for i in range(2):
            events.append(
                factory.instance_progress(
                    instance_id=instance_id,
                    agent_id=agent_id,
                    message_type="ai",
                    content=f"Progress {i}",
                )
            )

        # End
        events.append(
            factory.instance_end(
                instance_id=instance_id,
                agent_id=agent_id,
                result="Instance completed",
                duration_ms=500,
                success=True,
            )
        )

        # Verify lifecycle order
        assert events[0].type == EventType.INSTANCE_SPAWN
        assert events[1].type == EventType.INSTANCE_START
        for event in events[2:-1]:
            assert event.type == EventType.INSTANCE_PROGRESS
        assert events[-1].type == EventType.INSTANCE_END

        # Verify consistent instance_id
        for event in events:
            assert event.instance_id == instance_id

    @given(st.integers(min_value=0, max_value=10))
    @settings(max_examples=100)
    def test_instance_lifecycle_with_variable_progress(self, num_progress: int):
        """Property 9: Instance lifecycle with variable progress events.

        Feature: stream-event-refactor, Property 9: Instance Event Lifecycle
        Validates: Requirements 8.1, 8.2, 8.3, 8.4
        """
        from kiva.events import EventFactory, EventType

        factory = EventFactory("exec-123")
        instance_id = f"inst-{num_progress}"
        agent_id = "agent-1"

        events = []

        # Spawn
        events.append(
            factory.instance_spawn(
                instance_id=instance_id,
                agent_id=agent_id,
                task="Task",
                instance_num=num_progress,
            )
        )

        # Start
        events.append(
            factory.instance_start(
                instance_id=instance_id,
                agent_id=agent_id,
                task="Task",
            )
        )

        # Variable progress
        for i in range(num_progress):
            events.append(
                factory.instance_progress(
                    instance_id=instance_id,
                    agent_id=agent_id,
                    message_type="ai",
                    content=f"Progress {i}",
                )
            )

        # End
        events.append(
            factory.instance_end(
                instance_id=instance_id,
                agent_id=agent_id,
                result="Done",
                duration_ms=100,
                success=True,
            )
        )

        # Verify structure: spawn + start + progress + end
        assert len(events) == num_progress + 3
        assert events[0].type == EventType.INSTANCE_SPAWN
        assert events[1].type == EventType.INSTANCE_START
        assert events[-1].type == EventType.INSTANCE_END

        # All events have consistent instance_id
        for event in events:
            assert event.instance_id == instance_id

    def test_instance_lifecycle_with_error(self):
        """Property 9: Instance lifecycle ending with error.

        Feature: stream-event-refactor, Property 9: Instance Event Lifecycle
        Validates: Requirements 8.1, 8.2, 8.5
        """
        from kiva.events import EventFactory, EventType

        factory = EventFactory("exec-123")
        instance_id = "inst-error"
        agent_id = "agent-1"

        events = []

        # Spawn
        events.append(
            factory.instance_spawn(
                instance_id=instance_id,
                agent_id=agent_id,
                task="Failing task",
                instance_num=0,
            )
        )

        # Start
        events.append(
            factory.instance_start(
                instance_id=instance_id,
                agent_id=agent_id,
                task="Failing task",
            )
        )

        # Error
        events.append(
            factory.instance_error(
                instance_id=instance_id,
                agent_id=agent_id,
                error_type="TimeoutError",
                error_message="Instance timed out",
            )
        )

        # Verify lifecycle
        assert events[0].type == EventType.INSTANCE_SPAWN
        assert events[1].type == EventType.INSTANCE_START
        assert events[-1].type == EventType.INSTANCE_ERROR

        # Consistent instance_id
        for event in events:
            assert event.instance_id == instance_id

    # =========================================================================
    # Property 10: Parallel Execution Event Sequence
    # =========================================================================

    def test_parallel_execution_event_sequence(self):
        """Property 10: Parallel Execution Event Sequence.

        For any parallel execution batch, the system SHALL emit parallel_start,
        then zero or more parallel_progress events with increasing
        completed_count, then parallel_complete, with consistent batch_id.

        Feature: stream-event-refactor, Property 10: Parallel Execution Event Sequence
        Validates: Requirements 9.1, 9.2, 9.3
        """
        from kiva.events import EventFactory, EventType

        factory = EventFactory("exec-123")
        batch_id = "batch-123"
        total_count = 5

        events = []

        # Start
        events.append(
            factory.parallel_start(
                batch_id=batch_id,
                agent_ids=["agent-1", "agent-2"],
                instance_count=total_count,
                strategy="concurrent",
            )
        )

        # Progress events with increasing completed_count
        for completed in range(1, total_count):
            events.append(
                factory.parallel_progress(
                    batch_id=batch_id,
                    completed_count=completed,
                    total_count=total_count,
                    progress_percent=int(completed / total_count * 100),
                )
            )

        # Complete
        events.append(
            factory.parallel_complete(
                batch_id=batch_id,
                results=[{"agent": f"a{i}", "success": True} for i in range(total_count)],
                success_count=total_count,
                failure_count=0,
                duration_ms=5000,
            )
        )

        # Verify sequence
        assert events[0].type == EventType.PARALLEL_START
        for event in events[1:-1]:
            assert event.type == EventType.PARALLEL_PROGRESS
        assert events[-1].type == EventType.PARALLEL_COMPLETE

        # Verify consistent batch_id
        for event in events:
            assert event.data["batch_id"] == batch_id

        # Verify increasing completed_count in progress events
        progress_events = [e for e in events if e.type == EventType.PARALLEL_PROGRESS]
        completed_counts = [e.data["completed_count"] for e in progress_events]
        assert completed_counts == sorted(completed_counts)

    @given(st.integers(min_value=1, max_value=20))
    @settings(max_examples=100)
    def test_parallel_sequence_with_variable_instances(self, total_count: int):
        """Property 10: Parallel sequence with variable instance count.

        Feature: stream-event-refactor, Property 10: Parallel Execution Event Sequence
        Validates: Requirements 9.1, 9.2, 9.3
        """
        from kiva.events import EventFactory, EventType

        factory = EventFactory("exec-123")
        batch_id = f"batch-{total_count}"

        events = []

        # Start
        events.append(
            factory.parallel_start(
                batch_id=batch_id,
                agent_ids=["agent-1"],
                instance_count=total_count,
                strategy="batch",
            )
        )

        # Progress events
        for completed in range(1, total_count + 1):
            events.append(
                factory.parallel_progress(
                    batch_id=batch_id,
                    completed_count=completed,
                    total_count=total_count,
                    progress_percent=int(completed / total_count * 100),
                )
            )

        # Complete
        events.append(
            factory.parallel_complete(
                batch_id=batch_id,
                results=[],
                success_count=total_count,
                failure_count=0,
                duration_ms=1000,
            )
        )

        # Verify structure
        assert events[0].type == EventType.PARALLEL_START
        assert events[-1].type == EventType.PARALLEL_COMPLETE

        # Verify batch_id consistency
        for event in events:
            assert event.data["batch_id"] == batch_id

        # Verify monotonically increasing completed_count
        progress_events = [e for e in events if e.type == EventType.PARALLEL_PROGRESS]
        for i in range(1, len(progress_events)):
            prev_count = progress_events[i - 1].data["completed_count"]
            curr_count = progress_events[i].data["completed_count"]
            assert curr_count >= prev_count

    def test_parallel_sequence_without_progress(self):
        """Property 10: Parallel sequence with zero progress events.

        Feature: stream-event-refactor, Property 10: Parallel Execution Event Sequence
        Validates: Requirements 9.1, 9.3
        """
        from kiva.events import EventFactory, EventType

        factory = EventFactory("exec-123")
        batch_id = "batch-fast"

        events = []

        # Start
        events.append(
            factory.parallel_start(
                batch_id=batch_id,
                agent_ids=["agent-1"],
                instance_count=1,
                strategy="single",
            )
        )

        # Complete immediately (no progress events)
        events.append(
            factory.parallel_complete(
                batch_id=batch_id,
                results=[{"success": True}],
                success_count=1,
                failure_count=0,
                duration_ms=100,
            )
        )

        # Verify sequence
        assert len(events) == 2
        assert events[0].type == EventType.PARALLEL_START
        assert events[1].type == EventType.PARALLEL_COMPLETE

        # Consistent batch_id
        for event in events:
            assert event.data["batch_id"] == batch_id

    # =========================================================================
    # Property 11: Tool Call Event Pairing
    # =========================================================================

    def test_tool_call_event_pairing(self):
        """Property 11: Tool Call Event Pairing.

        For any tool call, if a tool_call_start event is emitted with a
        call_id, a corresponding tool_call_end event with the same call_id
        SHALL be emitted.

        Feature: stream-event-refactor, Property 11: Tool Call Event Pairing
        Validates: Requirements 11.1, 11.2
        """
        from kiva.events import EventFactory, EventType

        factory = EventFactory("exec-123")
        call_id = "call-123"
        tool_name = "search"

        events = []

        # Start
        events.append(
            factory.tool_call_start(
                tool_name=tool_name,
                tool_args={"query": "test"},
                call_id=call_id,
                agent_id="agent-1",
            )
        )

        # End
        events.append(
            factory.tool_call_end(
                tool_name=tool_name,
                call_id=call_id,
                result_preview="Results found",
                success=True,
                duration_ms=200,
                agent_id="agent-1",
            )
        )

        # Verify pairing
        assert events[0].type == EventType.TOOL_CALL_START
        assert events[1].type == EventType.TOOL_CALL_END
        assert events[0].data["call_id"] == events[1].data["call_id"]
        assert events[0].data["tool_name"] == events[1].data["tool_name"]

    @given(st.integers(min_value=1, max_value=10))
    @settings(max_examples=100)
    def test_multiple_tool_calls_pairing(self, num_calls: int):
        """Property 11: Multiple tool calls maintain proper pairing.

        Feature: stream-event-refactor, Property 11: Tool Call Event Pairing
        Validates: Requirements 11.1, 11.2
        """
        from kiva.events import EventFactory, EventType

        factory = EventFactory("exec-123")

        events = []
        call_ids = [f"call-{i}" for i in range(num_calls)]

        # Emit all starts
        for i, call_id in enumerate(call_ids):
            events.append(
                factory.tool_call_start(
                    tool_name=f"tool-{i}",
                    tool_args={"arg": i},
                    call_id=call_id,
                    agent_id="agent-1",
                )
            )

        # Emit all ends (in reverse order to test pairing)
        for i, call_id in enumerate(reversed(call_ids)):
            events.append(
                factory.tool_call_end(
                    tool_name=f"tool-{num_calls - 1 - i}",
                    call_id=call_id,
                    result_preview="Done",
                    success=True,
                    duration_ms=100,
                    agent_id="agent-1",
                )
            )

        # Verify all starts have matching ends
        start_events = [e for e in events if e.type == EventType.TOOL_CALL_START]
        end_events = [e for e in events if e.type == EventType.TOOL_CALL_END]

        assert len(start_events) == num_calls
        assert len(end_events) == num_calls

        # Each start call_id has a matching end call_id
        start_call_ids = {e.data["call_id"] for e in start_events}
        end_call_ids = {e.data["call_id"] for e in end_events}
        assert start_call_ids == end_call_ids

    def test_tool_call_with_failure(self):
        """Property 11: Tool call pairing with failure.

        Feature: stream-event-refactor, Property 11: Tool Call Event Pairing
        Validates: Requirements 11.1, 11.2
        """
        from kiva.events import EventFactory, EventType

        factory = EventFactory("exec-123")
        call_id = "call-fail"

        events = []

        # Start
        events.append(
            factory.tool_call_start(
                tool_name="failing_tool",
                tool_args={},
                call_id=call_id,
            )
        )

        # End with failure
        events.append(
            factory.tool_call_end(
                tool_name="failing_tool",
                call_id=call_id,
                result_preview="Error occurred",
                success=False,
                duration_ms=50,
            )
        )

        # Verify pairing even with failure
        assert events[0].type == EventType.TOOL_CALL_START
        assert events[1].type == EventType.TOOL_CALL_END
        assert events[0].data["call_id"] == events[1].data["call_id"]
        assert events[1].data["success"] is False

    def test_nested_tool_calls_pairing(self):
        """Property 11: Nested tool calls maintain proper pairing.

        Feature: stream-event-refactor, Property 11: Tool Call Event Pairing
        Validates: Requirements 11.1, 11.2
        """
        from kiva.events import EventFactory, EventType

        factory = EventFactory("exec-123")

        events = []

        # Nested calls: start A, start B, end B, end A
        events.append(
            factory.tool_call_start(
                tool_name="outer",
                tool_args={},
                call_id="call-outer",
            )
        )
        events.append(
            factory.tool_call_start(
                tool_name="inner",
                tool_args={},
                call_id="call-inner",
            )
        )
        events.append(
            factory.tool_call_end(
                tool_name="inner",
                call_id="call-inner",
                result_preview="Inner done",
                success=True,
                duration_ms=50,
            )
        )
        events.append(
            factory.tool_call_end(
                tool_name="outer",
                call_id="call-outer",
                result_preview="Outer done",
                success=True,
                duration_ms=100,
            )
        )

        # Verify all call_ids are paired
        start_ids = {
            e.data["call_id"] for e in events if e.type == EventType.TOOL_CALL_START
        }
        end_ids = {
            e.data["call_id"] for e in events if e.type == EventType.TOOL_CALL_END
        }
        assert start_ids == end_ids
        assert start_ids == {"call-outer", "call-inner"}



class TestPlanningAndSynthesisProperties:
    """Property-based tests for planning and synthesis event properties.

    Feature: stream-event-refactor
    Properties 7, 12, 13
    Validates: Requirements 4.1, 4.2, 5.2, 10.2
    """

    # =========================================================================
    # Property 7: Phase Transition Sequence
    # =========================================================================

    def test_phase_transition_sequence_success(self):
        """Property 7: Phase Transition Sequence.

        For any successful execution, phase_change events SHALL follow the
        sequence: initializing → analyzing → executing → synthesizing → complete,
        with each transition having correct previous_phase and current_phase values.

        Feature: stream-event-refactor, Property 7: Phase Transition Sequence
        Validates: Requirements 4.1, 4.2
        """
        from kiva.events import EventFactory, EventPhase, EventType

        factory = EventFactory("exec-123")

        # Expected phase transitions for successful execution
        expected_transitions = [
            (EventPhase.INITIALIZING, EventPhase.ANALYZING, 10, "Starting analysis"),
            (EventPhase.ANALYZING, EventPhase.EXECUTING, 25, "Starting execution"),
            (EventPhase.EXECUTING, EventPhase.SYNTHESIZING, 75, "Starting synthesis"),
            (EventPhase.SYNTHESIZING, EventPhase.COMPLETE, 100, "Execution complete"),
        ]

        events = []
        for prev, curr, progress, message in expected_transitions:
            events.append(
                factory.phase_change(
                    previous_phase=prev,
                    current_phase=curr,
                    progress_percent=progress,
                    message=message,
                )
            )

        # Verify all events are phase_change type
        for event in events:
            assert event.type == EventType.PHASE_CHANGE

        # Verify sequence
        assert events[0].data["previous_phase"] == "initializing"
        assert events[0].data["current_phase"] == "analyzing"

        assert events[1].data["previous_phase"] == "analyzing"
        assert events[1].data["current_phase"] == "executing"

        assert events[2].data["previous_phase"] == "executing"
        assert events[2].data["current_phase"] == "synthesizing"

        assert events[3].data["previous_phase"] == "synthesizing"
        assert events[3].data["current_phase"] == "complete"

        # Verify progress is monotonically increasing
        progress_values = [e.data["progress_percent"] for e in events]
        assert progress_values == sorted(progress_values)

    def test_phase_transition_sequence_error(self):
        """Property 7: Phase transition to error state.

        Any phase can transition to error state on failure.

        Feature: stream-event-refactor, Property 7: Phase Transition Sequence
        Validates: Requirements 4.1, 4.2
        """
        from kiva.events import EventFactory, EventPhase, EventType

        factory = EventFactory("exec-123")

        # Simulate error during execution phase
        events = []

        # Normal transitions up to executing
        events.append(
            factory.phase_change(
                previous_phase=EventPhase.INITIALIZING,
                current_phase=EventPhase.ANALYZING,
                progress_percent=10,
                message="Starting analysis",
            )
        )
        events.append(
            factory.phase_change(
                previous_phase=EventPhase.ANALYZING,
                current_phase=EventPhase.EXECUTING,
                progress_percent=25,
                message="Starting execution",
            )
        )

        # Error transition
        events.append(
            factory.phase_change(
                previous_phase=EventPhase.EXECUTING,
                current_phase=EventPhase.ERROR,
                progress_percent=-1,
                message="Execution failed",
            )
        )

        # Verify error transition
        assert events[-1].data["current_phase"] == "error"
        assert events[-1].data["previous_phase"] == "executing"

    @given(st.sampled_from([
        EventPhase.INITIALIZING,
        EventPhase.ANALYZING,
        EventPhase.EXECUTING,
        EventPhase.SYNTHESIZING,
    ]))
    @settings(max_examples=100)
    def test_any_phase_can_transition_to_error(self, phase: EventPhase):
        """Property 7: Any phase can transition to error.

        Feature: stream-event-refactor, Property 7: Phase Transition Sequence
        Validates: Requirements 4.1, 4.2
        """
        from kiva.events import EventFactory, EventPhase, EventType

        factory = EventFactory("exec-123")
        factory.set_phase(phase)

        event = factory.phase_change(
            previous_phase=phase,
            current_phase=EventPhase.ERROR,
            progress_percent=-1,
            message="Error occurred",
        )

        assert event.type == EventType.PHASE_CHANGE
        assert event.data["previous_phase"] == phase.value
        assert event.data["current_phase"] == "error"

    @given(st.lists(st.integers(min_value=0, max_value=100), min_size=4, max_size=4, unique=True))
    @settings(max_examples=100)
    def test_phase_transition_progress_values(self, progress_values: list[int]):
        """Property 7: Phase transitions with various progress values.

        Feature: stream-event-refactor, Property 7: Phase Transition Sequence
        Validates: Requirements 4.1, 4.2
        """
        from kiva.events import EventFactory, EventPhase, EventType

        factory = EventFactory("exec-123")

        # Sort progress values to ensure monotonic increase
        sorted_progress = sorted(progress_values)

        transitions = [
            (EventPhase.INITIALIZING, EventPhase.ANALYZING),
            (EventPhase.ANALYZING, EventPhase.EXECUTING),
            (EventPhase.EXECUTING, EventPhase.SYNTHESIZING),
            (EventPhase.SYNTHESIZING, EventPhase.COMPLETE),
        ]

        events = []
        for (prev, curr), progress in zip(transitions, sorted_progress):
            events.append(
                factory.phase_change(
                    previous_phase=prev,
                    current_phase=curr,
                    progress_percent=progress,
                    message=f"Transition to {curr.value}",
                )
            )

        # Verify all events created successfully
        assert len(events) == 4
        for event in events:
            assert event.type == EventType.PHASE_CHANGE

        # Verify progress is monotonically increasing
        actual_progress = [e.data["progress_percent"] for e in events]
        assert actual_progress == sorted(actual_progress)

    # =========================================================================
    # Property 12: Planning Progress Accumulation
    # =========================================================================

    def test_planning_progress_accumulation(self):
        """Property 12: Planning Progress Accumulation.

        For any sequence of planning_progress events, the accumulated_content
        field SHALL be monotonically increasing in length.

        Feature: stream-event-refactor, Property 12: Planning Progress Accumulation
        Validates: Requirements 5.2
        """
        from kiva.events import EventFactory, EventType

        factory = EventFactory("exec-123")

        # Simulate streaming tokens during planning
        tokens = ["Hello", " ", "world", "!", " How", " are", " you", "?"]
        accumulated = ""
        events = []

        for token in tokens:
            accumulated += token
            events.append(
                factory.planning_progress(
                    content=token,
                    accumulated_content=accumulated,
                )
            )

        # Verify all events are planning_progress type
        for event in events:
            assert event.type == EventType.PLANNING_PROGRESS

        # Verify accumulated_content is monotonically increasing in length
        lengths = [len(e.data["accumulated_content"]) for e in events]
        for i in range(1, len(lengths)):
            assert lengths[i] >= lengths[i - 1], (
                f"accumulated_content length decreased: {lengths[i-1]} -> {lengths[i]}"
            )

        # Verify final accumulated content
        assert events[-1].data["accumulated_content"] == "Hello world! How are you?"

    @given(st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=20))
    @settings(max_examples=100)
    def test_planning_progress_accumulation_property(self, tokens: list[str]):
        """Property 12: Planning progress accumulation with random tokens.

        For any sequence of planning_progress events, the accumulated_content
        field SHALL be monotonically increasing in length.

        Feature: stream-event-refactor, Property 12: Planning Progress Accumulation
        Validates: Requirements 5.2
        """
        from kiva.events import EventFactory, EventType

        factory = EventFactory("exec-123")

        accumulated = ""
        events = []

        for token in tokens:
            accumulated += token
            events.append(
                factory.planning_progress(
                    content=token,
                    accumulated_content=accumulated,
                )
            )

        # Verify accumulated_content is monotonically increasing in length
        lengths = [len(e.data["accumulated_content"]) for e in events]
        for i in range(1, len(lengths)):
            assert lengths[i] >= lengths[i - 1], (
                f"accumulated_content length decreased: {lengths[i-1]} -> {lengths[i]}"
            )

        # Verify each event has correct type
        for event in events:
            assert event.type == EventType.PLANNING_PROGRESS

    def test_planning_progress_content_matches_accumulation(self):
        """Property 12: Each content token contributes to accumulation.

        Feature: stream-event-refactor, Property 12: Planning Progress Accumulation
        Validates: Requirements 5.2
        """
        from kiva.events import EventFactory

        factory = EventFactory("exec-123")

        tokens = ["The", " quick", " brown", " fox"]
        accumulated = ""
        events = []

        for token in tokens:
            prev_accumulated = accumulated
            accumulated += token
            events.append(
                factory.planning_progress(
                    content=token,
                    accumulated_content=accumulated,
                )
            )

            # Verify the new accumulated content contains the previous plus new token
            assert events[-1].data["accumulated_content"] == prev_accumulated + token

    @given(st.integers(min_value=1, max_value=50))
    @settings(max_examples=100)
    def test_planning_progress_with_variable_token_count(self, num_tokens: int):
        """Property 12: Planning progress with variable number of tokens.

        Feature: stream-event-refactor, Property 12: Planning Progress Accumulation
        Validates: Requirements 5.2
        """
        from kiva.events import EventFactory, EventType

        factory = EventFactory("exec-123")

        accumulated = ""
        events = []

        for i in range(num_tokens):
            token = f"token{i} "
            accumulated += token
            events.append(
                factory.planning_progress(
                    content=token,
                    accumulated_content=accumulated,
                )
            )

        # Verify count
        assert len(events) == num_tokens

        # Verify monotonic increase
        lengths = [len(e.data["accumulated_content"]) for e in events]
        assert lengths == sorted(lengths)

        # Verify all events are planning_progress
        for event in events:
            assert event.type == EventType.PLANNING_PROGRESS

    # =========================================================================
    # Property 13: Synthesis Progress Accumulation
    # =========================================================================

    def test_synthesis_progress_accumulation(self):
        """Property 13: Synthesis Progress Accumulation.

        For any sequence of synthesis_progress events, the accumulated_content
        field SHALL be monotonically increasing in length.

        Feature: stream-event-refactor, Property 13: Synthesis Progress Accumulation
        Validates: Requirements 10.2
        """
        from kiva.events import EventFactory, EventType

        factory = EventFactory("exec-123")

        # Simulate streaming tokens during synthesis
        tokens = ["Based", " on", " the", " results", ",", " here", " is", " the", " summary", "."]
        accumulated = ""
        events = []

        for token in tokens:
            accumulated += token
            events.append(
                factory.synthesis_progress(
                    content=token,
                    accumulated_content=accumulated,
                )
            )

        # Verify all events are synthesis_progress type
        for event in events:
            assert event.type == EventType.SYNTHESIS_PROGRESS

        # Verify accumulated_content is monotonically increasing in length
        lengths = [len(e.data["accumulated_content"]) for e in events]
        for i in range(1, len(lengths)):
            assert lengths[i] >= lengths[i - 1], (
                f"accumulated_content length decreased: {lengths[i-1]} -> {lengths[i]}"
            )

        # Verify final accumulated content
        assert events[-1].data["accumulated_content"] == "Based on the results, here is the summary."

    @given(st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=20))
    @settings(max_examples=100)
    def test_synthesis_progress_accumulation_property(self, tokens: list[str]):
        """Property 13: Synthesis progress accumulation with random tokens.

        For any sequence of synthesis_progress events, the accumulated_content
        field SHALL be monotonically increasing in length.

        Feature: stream-event-refactor, Property 13: Synthesis Progress Accumulation
        Validates: Requirements 10.2
        """
        from kiva.events import EventFactory, EventType

        factory = EventFactory("exec-123")

        accumulated = ""
        events = []

        for token in tokens:
            accumulated += token
            events.append(
                factory.synthesis_progress(
                    content=token,
                    accumulated_content=accumulated,
                )
            )

        # Verify accumulated_content is monotonically increasing in length
        lengths = [len(e.data["accumulated_content"]) for e in events]
        for i in range(1, len(lengths)):
            assert lengths[i] >= lengths[i - 1], (
                f"accumulated_content length decreased: {lengths[i-1]} -> {lengths[i]}"
            )

        # Verify each event has correct type
        for event in events:
            assert event.type == EventType.SYNTHESIS_PROGRESS

    def test_synthesis_progress_content_matches_accumulation(self):
        """Property 13: Each content token contributes to accumulation.

        Feature: stream-event-refactor, Property 13: Synthesis Progress Accumulation
        Validates: Requirements 10.2
        """
        from kiva.events import EventFactory

        factory = EventFactory("exec-123")

        tokens = ["Summary", ":", " Agent", " 1", " found", " X"]
        accumulated = ""
        events = []

        for token in tokens:
            prev_accumulated = accumulated
            accumulated += token
            events.append(
                factory.synthesis_progress(
                    content=token,
                    accumulated_content=accumulated,
                )
            )

            # Verify the new accumulated content contains the previous plus new token
            assert events[-1].data["accumulated_content"] == prev_accumulated + token

    @given(st.integers(min_value=1, max_value=50))
    @settings(max_examples=100)
    def test_synthesis_progress_with_variable_token_count(self, num_tokens: int):
        """Property 13: Synthesis progress with variable number of tokens.

        Feature: stream-event-refactor, Property 13: Synthesis Progress Accumulation
        Validates: Requirements 10.2
        """
        from kiva.events import EventFactory, EventType

        factory = EventFactory("exec-123")

        accumulated = ""
        events = []

        for i in range(num_tokens):
            token = f"word{i} "
            accumulated += token
            events.append(
                factory.synthesis_progress(
                    content=token,
                    accumulated_content=accumulated,
                )
            )

        # Verify count
        assert len(events) == num_tokens

        # Verify monotonic increase
        lengths = [len(e.data["accumulated_content"]) for e in events]
        assert lengths == sorted(lengths)

        # Verify all events are synthesis_progress
        for event in events:
            assert event.type == EventType.SYNTHESIS_PROGRESS

    def test_synthesis_and_planning_progress_similarity(self):
        """Verify planning and synthesis progress events have similar structure.

        Both planning_progress and synthesis_progress should have the same
        data structure with content and accumulated_content fields.

        Feature: stream-event-refactor, Properties 12 & 13
        Validates: Requirements 5.2, 10.2
        """
        from kiva.events import EventFactory, EventType

        factory = EventFactory("exec-123")

        # Create planning progress event
        planning_event = factory.planning_progress(
            content="test",
            accumulated_content="test content",
        )

        # Create synthesis progress event
        synthesis_event = factory.synthesis_progress(
            content="test",
            accumulated_content="test content",
        )

        # Both should have same data structure
        assert "content" in planning_event.data
        assert "accumulated_content" in planning_event.data
        assert "content" in synthesis_event.data
        assert "accumulated_content" in synthesis_event.data

        # But different types
        assert planning_event.type == EventType.PLANNING_PROGRESS
        assert synthesis_event.type == EventType.SYNTHESIS_PROGRESS


class TestStreamEventSerializationProperties:
    """Property-based tests for StreamEvent serialization methods.

    Feature: streaming-api-optimization
    Properties 1, 2, 3, 6
    Validates: Requirements 2.1, 2.2, 2.3, 3.1, 3.2, 3.3
    """

    @given(stream_event_strategy())
    @settings(max_examples=100)
    def test_sse_format_validity(self, event: StreamEvent):
        """Property 1: SSE Format Validity.

        For any StreamEvent, calling to_sse() SHALL return a string that:
        - Contains `event: {type.value}` line
        - Contains `id: {event_id}` line
        - Contains `data: {valid_json}` line
        - Ends with double newline
        - Has no unescaped newlines within the data JSON

        Feature: streaming-api-optimization, Property 1: SSE Format Validity
        Validates: Requirements 2.1, 2.2, 2.3
        """
        import json

        sse_output = event.to_sse()

        # Must end with double newline
        assert sse_output.endswith("\n\n"), "SSE output must end with double newline"

        # Parse the SSE format
        lines = sse_output.rstrip("\n").split("\n")
        assert len(lines) == 3, f"SSE output must have exactly 3 lines, got {len(lines)}"

        # Check event line
        assert lines[0].startswith("event: "), "First line must start with 'event: '"
        assert lines[0] == f"event: {event.type.value}"

        # Check id line
        assert lines[1].startswith("id: "), "Second line must start with 'id: '"
        assert lines[1] == f"id: {event.event_id}"

        # Check data line
        assert lines[2].startswith("data: "), "Third line must start with 'data: '"
        data_json = lines[2][6:]  # Remove "data: " prefix

        # The data JSON should be valid JSON (json.dumps already escapes newlines)
        parsed = json.loads(data_json)
        assert isinstance(parsed, dict)
        assert parsed["type"] == event.type.value
        assert parsed["event_id"] == event.event_id

    @given(stream_event_strategy())
    @settings(max_examples=100)
    def test_ndjson_format_validity(self, event: StreamEvent):
        """Property 3: NDJSON Format Validity.

        For any StreamEvent, calling to_ndjson() SHALL return a string that:
        - Is valid JSON (parseable by json.loads())
        - Contains exactly one newline at the end
        - Contains no other newlines

        Feature: streaming-api-optimization, Property 3: NDJSON Format Validity
        Validates: Requirements 3.1
        """
        import json

        ndjson_output = event.to_ndjson()

        # Must end with exactly one newline
        assert ndjson_output.endswith("\n"), "NDJSON output must end with newline"

        # Remove trailing newline and check no other newlines
        json_part = ndjson_output[:-1]
        assert "\n" not in json_part, "NDJSON must not contain newlines except at end"

        # Must be valid JSON
        parsed = json.loads(json_part)
        assert isinstance(parsed, dict)
        assert parsed["type"] == event.type.value
        assert parsed["event_id"] == event.event_id

    @given(stream_event_strategy())
    @settings(max_examples=100)
    def test_json_serialization_round_trip_with_new_methods(self, event: StreamEvent):
        """Property 2: JSON Serialization Round-Trip.

        For any StreamEvent, calling to_json() then from_json() SHALL produce
        an equivalent StreamEvent with same type, event_id, data, and execution_id.

        Feature: streaming-api-optimization, Property 2: JSON Serialization Round-Trip
        Validates: Requirements 3.1, 3.2, 3.3
        """
        json_str = event.to_json()
        deserialized = StreamEvent.from_json(json_str)

        assert deserialized.type == event.type
        assert deserialized.event_id == event.event_id
        assert deserialized.data == event.data
        assert deserialized.execution_id == event.execution_id

    def test_non_serializable_object_handling(self):
        """Property 6: Non-Serializable Object Handling.

        For any StreamEvent with non-JSON-serializable objects in data,
        calling to_json() SHALL not raise an exception and SHALL convert
        non-serializable objects to their string representation.

        Feature: streaming-api-optimization, Property 6: Non-Serializable Object Handling
        Validates: Requirements 3.3
        """
        import json
        from datetime import datetime

        # Create a custom non-serializable object
        class CustomObject:
            def __str__(self):
                return "CustomObject()"

        # Create event with non-serializable data
        event = StreamEvent(
            type=EventType.DEBUG,
            data={
                "custom_obj": CustomObject(),
                "datetime_obj": datetime.now(),
                "set_obj": {1, 2, 3},  # Sets are not JSON serializable
                "normal_str": "hello",
                "normal_int": 42,
            },
            execution_id="exec-123",
        )

        # Should not raise an exception
        json_str = event.to_json()

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)

        # Non-serializable objects should be converted to strings
        assert parsed["data"]["custom_obj"] == "CustomObject()"
        assert isinstance(parsed["data"]["datetime_obj"], str)
        assert isinstance(parsed["data"]["set_obj"], str)

        # Normal serializable objects should remain unchanged
        assert parsed["data"]["normal_str"] == "hello"
        assert parsed["data"]["normal_int"] == 42

    def test_sse_escapes_newlines_in_data(self):
        """Test that SSE format properly handles newlines in JSON data.

        Feature: streaming-api-optimization, Property 1: SSE Format Validity
        Validates: Requirements 2.3
        """
        import json

        # Create event with newlines in data
        event = StreamEvent(
            type=EventType.DEBUG,
            data={
                "message": "Line 1\nLine 2\nLine 3",
                "multiline": "First\nSecond",
            },
            execution_id="exec-123",
        )

        sse_output = event.to_sse()

        # The SSE output should have exactly 3 lines (event, id, data) plus 2 empty lines
        lines = sse_output.split("\n")
        # Should be: event, id, data, empty, empty
        assert len(lines) == 5, f"Expected 5 lines, got {len(lines)}: {lines}"

        # The data line should be valid JSON (json.dumps escapes newlines as \n)
        data_line = lines[2]
        assert data_line.startswith("data: ")
        data_json = data_line[6:]

        # Should be valid JSON that can be parsed directly
        parsed = json.loads(data_json)
        assert parsed["data"]["message"] == "Line 1\nLine 2\nLine 3"
        assert parsed["data"]["multiline"] == "First\nSecond"

    def test_ndjson_with_special_characters(self):
        """Test NDJSON format with special characters in data.

        Feature: streaming-api-optimization, Property 3: NDJSON Format Validity
        Validates: Requirements 3.1
        """
        import json

        event = StreamEvent(
            type=EventType.DEBUG,
            data={
                "unicode": "Hello 世界 🌍",
                "quotes": 'He said "hello"',
                "backslash": "path\\to\\file",
            },
            execution_id="exec-123",
        )

        ndjson_output = event.to_ndjson()

        # Should end with single newline
        assert ndjson_output.endswith("\n")
        assert ndjson_output.count("\n") == 1

        # Should be valid JSON
        parsed = json.loads(ndjson_output.strip())
        assert parsed["data"]["unicode"] == "Hello 世界 🌍"
        assert parsed["data"]["quotes"] == 'He said "hello"'
        assert parsed["data"]["backslash"] == "path\\to\\file"


class TestMonotonicTimestamps:
    """Property-based tests for EventFactory monotonic timestamps.

    Feature: streaming-api-optimization, Property 5: Monotonic Timestamps
    Validates: Requirements 7.1, 7.2, 7.3, 7.4
    """

    @given(st.integers(min_value=2, max_value=100))
    @settings(max_examples=100)
    def test_timestamps_are_strictly_monotonically_increasing(self, num_events: int):
        """Property 5: Monotonic Timestamps.

        For any sequence of events created by the same EventFactory,
        the timestamps SHALL be strictly monotonically increasing:
        event[i].timestamp < event[i+1].timestamp for all i.

        Feature: streaming-api-optimization, Property 5: Monotonic Timestamps
        Validates: Requirements 7.1, 7.2, 7.3, 7.4
        """
        from kiva.events import EventFactory

        factory = EventFactory("exec-test")
        events = []

        for i in range(num_events):
            event = factory.create(
                EventType.DEBUG,
                {"index": i},
            )
            events.append(event)

        # Verify strict monotonic increase
        for i in range(1, len(events)):
            assert events[i].timestamp > events[i - 1].timestamp, (
                f"Timestamp not strictly increasing at index {i}: "
                f"{events[i - 1].timestamp} >= {events[i].timestamp}"
            )

    def test_monotonic_timestamp_handles_clock_regression(self):
        """Test that monotonic timestamps handle system clock regression.

        Feature: streaming-api-optimization, Property 5: Monotonic Timestamps
        Validates: Requirements 7.2, 7.3
        """
        from unittest.mock import patch
        from kiva.events import EventFactory

        factory = EventFactory("exec-test")

        # Create first event
        event1 = factory.create(EventType.DEBUG, {"index": 1})

        # Simulate clock going backwards by patching time.time
        with patch('kiva.events.time.time', return_value=event1.timestamp - 1.0):
            event2 = factory.create(EventType.DEBUG, {"index": 2})

        # Second event should still have a larger timestamp
        assert event2.timestamp > event1.timestamp, (
            f"Timestamp should increase even with clock regression: "
            f"{event1.timestamp} >= {event2.timestamp}"
        )

    def test_monotonic_timestamp_handles_same_time(self):
        """Test that monotonic timestamps handle same time.time() values.

        Feature: streaming-api-optimization, Property 5: Monotonic Timestamps
        Validates: Requirements 7.2, 7.3
        """
        from unittest.mock import patch
        from kiva.events import EventFactory

        fixed_time = 1000000.0
        factory = EventFactory("exec-test")

        # Patch time.time to return the same value
        with patch('kiva.events.time.time', return_value=fixed_time):
            # Override start_time and _last_timestamp to use fixed time
            factory._last_timestamp = fixed_time

            events = []
            for i in range(5):
                event = factory.create(EventType.DEBUG, {"index": i})
                events.append(event)

        # All timestamps should be strictly increasing
        for i in range(1, len(events)):
            assert events[i].timestamp > events[i - 1].timestamp, (
                f"Timestamp not strictly increasing at index {i}: "
                f"{events[i - 1].timestamp} >= {events[i].timestamp}"
            )

    def test_event_factory_has_slots(self):
        """Test that EventFactory uses __slots__ for memory optimization.

        Feature: streaming-api-optimization
        Validates: Requirements 4.1
        """
        from kiva.events import EventFactory

        factory = EventFactory("exec-test")

        # Verify __slots__ is defined
        assert hasattr(EventFactory, '__slots__')
        assert 'execution_id' in EventFactory.__slots__
        assert 'current_phase' in EventFactory.__slots__
        assert 'start_time' in EventFactory.__slots__
        assert '_last_timestamp' in EventFactory.__slots__

        # Verify we cannot add arbitrary attributes (slots restriction)
        try:
            factory.arbitrary_attribute = "test"
            has_dict = True
        except AttributeError:
            has_dict = False

        assert not has_dict, "EventFactory should not allow arbitrary attributes with __slots__"
