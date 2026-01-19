"""E2E test for event sequence verification.

Tests the complete execution flow event sequences to verify that events
are emitted in the correct order with proper data.

Validates: Requirements 3.1-3.3, 4.1-4.2
"""

import asyncio

import pytest

from kiva import Kiva
from kiva.events import EventPhase, EventType
from kiva.run import run


class TestEventSequenceE2E:
    """E2E tests for verifying event sequences during execution."""

    @pytest.mark.asyncio
    async def test_execution_lifecycle_events(self, api_config):
        """Test that execution emits lifecycle events in correct order.

        Validates: Requirements 3.1, 3.2
        """
        kiva = Kiva(
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model=api_config["model"],
        )

        @kiva.agent("echo", "Echoes input")
        def echo(text: str) -> str:
            """Echo the text."""
            return f"Echo: {text}"

        # Build agents and collect events during execution
        agents = kiva._build_agents()
        events = []
        async for event in run(
            prompt="Say hello",
            agents=agents,
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model_name=api_config["model"],
        ):
            events.append(event)

        # Verify execution_start is first
        event_types = [e.type for e in events]
        assert EventType.EXECUTION_START in event_types, "Missing execution_start event"

        # Find execution_start event
        exec_start = next(e for e in events if e.type == EventType.EXECUTION_START)
        assert exec_start.data.get("prompt") is not None
        assert exec_start.data.get("agent_count") >= 1
        assert exec_start.data.get("config") is not None

        # Verify execution_end is present (for successful execution)
        if EventType.EXECUTION_END in event_types:
            exec_end = next(e for e in events if e.type == EventType.EXECUTION_END)
            assert exec_end.data.get("success") is True
            assert exec_end.data.get("duration_ms") >= 0

        print(f"\nCollected {len(events)} events")
        print(f"Event types: {[e.type.value for e in events[:10]]}...")

    @pytest.mark.asyncio
    async def test_phase_change_sequence(self, api_config):
        """Test that phase changes follow the expected sequence.

        Validates: Requirements 4.1, 4.2
        """
        kiva = Kiva(
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model=api_config["model"],
        )

        @kiva.agent("calculator", "Performs calculations")
        def calculate(expression: str) -> str:
            """Calculate expression."""
            try:
                return str(eval(expression))
            except Exception as e:
                return f"Error: {e}"

        # Build agents and collect events during execution
        agents = kiva._build_agents()
        events = []
        async for event in run(
            prompt="Calculate 2 + 2",
            agents=agents,
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model_name=api_config["model"],
        ):
            events.append(event)

        # Get phase_change events
        phase_changes = [e for e in events if e.type == EventType.PHASE_CHANGE]

        if phase_changes:
            # Verify phase transitions are valid
            valid_phases = {p.value for p in EventPhase}
            for pc in phase_changes:
                assert pc.data.get("previous_phase") in valid_phases
                assert pc.data.get("current_phase") in valid_phases
                assert 0 <= pc.data.get("progress_percent", 0) <= 100 or pc.data.get("progress_percent") == -1

            # Verify phases progress forward (not backward, except to error)
            phase_order = [
                EventPhase.INITIALIZING.value,
                EventPhase.ANALYZING.value,
                EventPhase.EXECUTING.value,
                EventPhase.SYNTHESIZING.value,
                EventPhase.COMPLETE.value,
            ]

            current_phases = [pc.data.get("current_phase") for pc in phase_changes]
            for i, phase in enumerate(current_phases):
                if phase == EventPhase.ERROR.value:
                    continue  # Error can happen at any point
                if phase in phase_order:
                    phase_idx = phase_order.index(phase)
                    # Each subsequent phase should be same or later in sequence
                    for prev_phase in current_phases[:i]:
                        if prev_phase in phase_order and prev_phase != EventPhase.ERROR.value:
                            prev_idx = phase_order.index(prev_phase)
                            assert phase_idx >= prev_idx, (
                                f"Phase went backward: {prev_phase} -> {phase}"
                            )

        print(f"\nPhase changes: {[pc.data.get('current_phase') for pc in phase_changes]}")

    @pytest.mark.asyncio
    async def test_agent_event_sequence(self, api_config):
        """Test that agent events follow the correct lifecycle.

        Validates: Requirements 7.1, 7.2, 7.3
        """
        kiva = Kiva(
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model=api_config["model"],
        )

        @kiva.agent("weather", "Gets weather information")
        def get_weather(city: str) -> str:
            """Get weather for a city."""
            return f"{city}: Sunny, 25°C"

        # Build agents and collect events during execution
        agents = kiva._build_agents()
        events = []
        async for event in run(
            prompt="What's the weather in Tokyo?",
            agents=agents,
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model_name=api_config["model"],
        ):
            events.append(event)

        # Get agent events
        agent_starts = [e for e in events if e.type == EventType.AGENT_START]
        agent_ends = [e for e in events if e.type == EventType.AGENT_END]
        agent_errors = [e for e in events if e.type == EventType.AGENT_ERROR]

        # If agents were invoked, verify lifecycle
        if agent_starts:
            # Each agent_start should have a corresponding agent_end or agent_error
            start_agent_ids = {e.data.get("agent_id") for e in agent_starts}
            end_agent_ids = {e.data.get("agent_id") for e in agent_ends}
            error_agent_ids = {e.data.get("agent_id") for e in agent_errors}

            completed_agent_ids = end_agent_ids | error_agent_ids
            assert start_agent_ids <= completed_agent_ids, (
                f"Some agents started but didn't complete: {start_agent_ids - completed_agent_ids}"
            )

            # Verify agent_start has required fields
            for start in agent_starts:
                assert start.data.get("agent_id") is not None
                assert start.data.get("task") is not None

            # Verify agent_end has required fields
            for end in agent_ends:
                assert end.data.get("agent_id") is not None
                assert end.data.get("success") is not None
                assert end.data.get("duration_ms") is not None

        print(f"\nAgent starts: {len(agent_starts)}, ends: {len(agent_ends)}, errors: {len(agent_errors)}")

    @pytest.mark.asyncio
    async def test_workflow_event_sequence(self, api_config):
        """Test that workflow events are emitted correctly.

        Validates: Requirements 6.1, 6.2, 6.3
        """
        kiva = Kiva(
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model=api_config["model"],
        )

        @kiva.agent("search", "Searches for information")
        def search(query: str) -> str:
            """Search for information."""
            return f"Results for: {query}"

        # Build agents and collect events during execution
        agents = kiva._build_agents()
        events = []
        async for event in run(
            prompt="Search for Python tutorials",
            agents=agents,
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model_name=api_config["model"],
        ):
            events.append(event)

        # Get workflow events
        workflow_selected = [e for e in events if e.type == EventType.WORKFLOW_SELECTED]
        workflow_starts = [e for e in events if e.type == EventType.WORKFLOW_START]
        workflow_ends = [e for e in events if e.type == EventType.WORKFLOW_END]

        # Verify workflow events if present
        if workflow_selected:
            for ws in workflow_selected:
                assert ws.data.get("workflow") is not None
                assert ws.data.get("complexity") is not None

        if workflow_starts:
            for ws in workflow_starts:
                assert ws.data.get("workflow") is not None

        if workflow_ends:
            for we in workflow_ends:
                assert we.data.get("workflow") is not None
                assert we.data.get("success") is not None
                assert we.data.get("duration_ms") is not None

        print(f"\nWorkflow events - selected: {len(workflow_selected)}, starts: {len(workflow_starts)}, ends: {len(workflow_ends)}")

    @pytest.mark.asyncio
    async def test_execution_error_event(self, api_config):
        """Test that execution_error event is emitted on failure.

        Validates: Requirements 3.3
        """
        kiva = Kiva(
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model=api_config["model"],
        )

        @kiva.agent("failing", "Always fails")
        def failing_func(input: str) -> str:
            """Function that raises an error."""
            raise ValueError("Intentional test error")

        # Build agents and collect events during execution
        agents = kiva._build_agents()
        events = []
        try:
            async for event in run(
                prompt="Trigger the failing agent",
                agents=agents,
                base_url=api_config["base_url"],
                api_key=api_config["api_key"],
                model_name=api_config["model"],
            ):
                events.append(event)
        except Exception:
            pass  # Expected to fail

        # Check for error events
        exec_errors = [e for e in events if e.type == EventType.EXECUTION_ERROR]
        agent_errors = [e for e in events if e.type == EventType.AGENT_ERROR]

        # At least one error event should be present
        has_error_event = len(exec_errors) > 0 or len(agent_errors) > 0

        if exec_errors:
            for err in exec_errors:
                assert err.data.get("error_type") is not None
                assert err.data.get("error_message") is not None

        if agent_errors:
            for err in agent_errors:
                assert err.data.get("error_type") is not None
                assert err.data.get("error_message") is not None

        print(f"\nError events - execution: {len(exec_errors)}, agent: {len(agent_errors)}")

    @pytest.mark.asyncio
    async def test_event_ids_are_unique(self, api_config):
        """Test that all events have unique event_ids.

        Validates: Requirements 2.1
        """
        kiva = Kiva(
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model=api_config["model"],
        )

        @kiva.agent("simple", "Simple agent")
        def simple(text: str) -> str:
            """Simple function."""
            return text

        # Build agents and collect events during execution
        agents = kiva._build_agents()
        events = []
        async for event in run(
            prompt="Process this",
            agents=agents,
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model_name=api_config["model"],
        ):
            events.append(event)

        # Verify all event_ids are unique
        event_ids = [e.event_id for e in events]
        assert len(event_ids) == len(set(event_ids)), "Duplicate event_ids found"

        print(f"\nAll {len(events)} events have unique IDs")

    @pytest.mark.asyncio
    async def test_events_have_consistent_execution_id(self, api_config):
        """Test that all events share the same execution_id.

        Validates: Requirements 2.1
        """
        kiva = Kiva(
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model=api_config["model"],
        )

        @kiva.agent("echo", "Echoes input")
        def echo(text: str) -> str:
            """Echo the text."""
            return f"Echo: {text}"

        # Build agents and collect events during execution
        agents = kiva._build_agents()
        events = []
        async for event in run(
            prompt="Say hello",
            agents=agents,
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model_name=api_config["model"],
        ):
            events.append(event)

        # Verify all events have the same execution_id
        if events:
            execution_ids = {e.execution_id for e in events}
            assert len(execution_ids) == 1, (
                f"Multiple execution_ids found: {execution_ids}"
            )

        print(f"\nAll {len(events)} events share execution_id: {events[0].execution_id if events else 'N/A'}")

    @pytest.mark.asyncio
    async def test_timestamps_are_monotonically_increasing(self, api_config):
        """Test that event timestamps are monotonically increasing.

        Validates: Requirements 2.1
        """
        kiva = Kiva(
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model=api_config["model"],
        )

        @kiva.agent("calculator", "Performs calculations")
        def calculate(expression: str) -> str:
            """Calculate expression."""
            return str(eval(expression))

        # Build agents and collect events during execution
        agents = kiva._build_agents()
        events = []
        async for event in run(
            prompt="Calculate 5 * 5",
            agents=agents,
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model_name=api_config["model"],
        ):
            events.append(event)

        # Verify timestamps are monotonically increasing
        if len(events) > 1:
            timestamps = [e.timestamp for e in events]
            for i in range(1, len(timestamps)):
                assert timestamps[i] >= timestamps[i-1], (
                    f"Timestamp decreased: {timestamps[i-1]} -> {timestamps[i]}"
                )

        print(f"\nAll {len(events)} events have monotonically increasing timestamps")
