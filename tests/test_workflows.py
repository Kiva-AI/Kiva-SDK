"""Property-based tests for workflow implementations.

These tests validate the correctness properties defined in the design document.
"""

import asyncio

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from kiva.workflows.parliament import (
    parliament_workflow,
    should_continue_parliament,
)
from kiva.workflows.router import router_workflow
from kiva.workflows.supervisor import supervisor_workflow


class MockAgent:
    """Mock agent for testing workflows."""

    def __init__(self, name: str, response: str = "Mock response"):
        self.name = name
        self.response = response
        self.call_count = 0

    async def ainvoke(self, input_data: dict, **kwargs) -> dict:
        """Mock invoke that returns a predefined response."""
        self.call_count += 1
        return {"messages": [type("Message", (), {"content": self.response})()]}


class FailingAgent:
    """Mock agent that always fails."""

    def __init__(self, name: str, error_msg: str = "Agent failed"):
        self.name = name
        self.error_msg = error_msg
        self.call_count = 0

    async def ainvoke(self, input_data: dict, **kwargs) -> dict:
        """Mock invoke that raises an exception."""
        self.call_count += 1
        raise RuntimeError(self.error_msg)


# Strategies for generating test data
agent_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_"),
    min_size=1,
    max_size=20,
).filter(lambda x: x and not x[0].isdigit())

task_strategy = st.text(min_size=1, max_size=100)


class TestRouterWorkflowProperty:
    """Property 8: Router Workflow Single Agent

    *For any* execution using Router workflow, the SDK SHALL call exactly one Worker Agent.

    """

    @given(
        num_agents=st.integers(min_value=1, max_value=5),
        num_assignments=st.integers(min_value=1, max_value=5),
    )
    @settings(max_examples=100)
    def test_router_calls_exactly_one_agent(
        self, num_agents: int, num_assignments: int
    ):
        """Feature: multi-agent-sdk, Property 8: Router Workflow Single Agent

        For any number of agents and task assignments, router workflow
        should only call exactly one agent.

        """
        # Create mock agents
        agents = [
            MockAgent(f"agent_{i}", f"Response from agent_{i}")
            for i in range(num_agents)
        ]

        # Create task assignments (router should only use the first one)
        task_assignments = [
            {"agent_id": f"agent_{i % num_agents}", "task": f"Task {i}"}
            for i in range(num_assignments)
        ]

        state = {
            "agents": agents,
            "task_assignments": task_assignments,
            "prompt": "Test prompt",
        }

        # Run the router workflow
        result = asyncio.run(router_workflow(state))

        # Property: Router should return exactly one result
        assert "agent_results" in result
        assert len(result["agent_results"]) == 1

        # Property: Only one agent should have been called
        total_calls = sum(agent.call_count for agent in agents)
        assert total_calls == 1, f"Expected 1 agent call, got {total_calls}"

    @given(
        agent_response=st.text(min_size=1, max_size=200),
    )
    @settings(max_examples=100)
    def test_router_returns_single_agent_result_directly(self, agent_response: str):
        """Feature: multi-agent-sdk, Property 8: Router Workflow Single Agent

        For any agent response, router workflow should return that result directly.

        """
        agent = MockAgent("test_agent", agent_response)

        state = {
            "agents": [agent],
            "task_assignments": [{"agent_id": "test_agent", "task": "Test task"}],
            "prompt": "Test prompt",
        }

        result = asyncio.run(router_workflow(state))

        # Property: Result should contain the agent's response
        assert len(result["agent_results"]) == 1
        assert result["agent_results"][0]["result"] == agent_response
        assert result["agent_results"][0]["agent_id"] == "test_agent"


class TestSupervisorWorkflowProperty:
    """Property 9: Supervisor Workflow Parallel Execution

    *For any* execution using Supervisor workflow, the SDK SHALL call 2 or more Worker Agents in parallel.

    """

    @given(
        num_agents=st.integers(min_value=2, max_value=5),
    )
    @settings(max_examples=100)
    def test_supervisor_calls_multiple_agents(self, num_agents: int):
        """Feature: multi-agent-sdk, Property 9: Supervisor Workflow Parallel Execution

        For any number of agents >= 2, supervisor workflow should call all assigned agents.

        """
        # Create mock agents
        agents = [
            MockAgent(f"agent_{i}", f"Response from agent_{i}")
            for i in range(num_agents)
        ]

        # Create task assignments for all agents
        task_assignments = [
            {"agent_id": f"agent_{i}", "task": f"Task for agent_{i}"}
            for i in range(num_agents)
        ]

        state = {
            "agents": agents,
            "task_assignments": task_assignments,
            "prompt": "Test prompt",
            "max_parallel_agents": 10,
        }

        # Run the supervisor workflow
        result = asyncio.run(supervisor_workflow(state))

        # Property: Supervisor should return results for all agents
        assert "agent_results" in result
        assert len(result["agent_results"]) == num_agents

        # Property: All agents should have been called
        total_calls = sum(agent.call_count for agent in agents)
        assert total_calls == num_agents, (
            f"Expected {num_agents} agent calls, got {total_calls}"
        )

    @given(
        num_agents=st.integers(min_value=2, max_value=4),
    )
    @settings(max_examples=100)
    def test_supervisor_collects_all_results(self, num_agents: int):
        """Feature: multi-agent-sdk, Property 9: Supervisor Workflow Parallel Execution

        For any execution, supervisor should collect results from all agents.

        """
        # Create agents with unique responses
        agents = [
            MockAgent(f"agent_{i}", f"Unique response {i}") for i in range(num_agents)
        ]

        task_assignments = [
            {"agent_id": f"agent_{i}", "task": f"Task {i}"} for i in range(num_agents)
        ]

        state = {
            "agents": agents,
            "task_assignments": task_assignments,
            "prompt": "Test prompt",
        }

        result = asyncio.run(supervisor_workflow(state))

        # Property: All results should be collected
        result_agent_ids = {r["agent_id"] for r in result["agent_results"]}
        expected_agent_ids = {f"agent_{i}" for i in range(num_agents)}
        assert result_agent_ids == expected_agent_ids


class TestParliamentWorkflowProperty:
    """Property 10: Parliament Workflow Iteration Limit

    *For any* execution using Parliament workflow, the number of iterations SHALL NOT exceed max_iterations.

    """

    @given(
        max_iterations=st.integers(min_value=1, max_value=5),
    )
    @settings(max_examples=100)
    def test_parliament_respects_max_iterations(self, max_iterations: int):
        """Feature: multi-agent-sdk, Property 10: Parliament Workflow Iteration Limit

        For any max_iterations value, parliament workflow should not exceed that limit.

        """
        # Create agents that produce conflicting results to force iterations
        agents = [
            MockAgent("agent_0", "Yes, this is correct"),
            MockAgent("agent_1", "No, this is incorrect"),
        ]

        task_assignments = [
            {"agent_id": "agent_0", "task": "Verify claim"},
            {"agent_id": "agent_1", "task": "Verify claim"},
        ]

        state = {
            "agents": agents,
            "task_assignments": task_assignments,
            "prompt": "Test prompt",
            "max_iterations": max_iterations,
            "iteration": 0,
            "conflicts": [],
            "agent_results": [],
        }

        # Run parliament workflow multiple times to simulate iterations
        current_state = state.copy()
        iterations_run = 0

        for _ in range(max_iterations + 2):  # Run more than max to test limit
            result = asyncio.run(parliament_workflow(current_state))
            iterations_run = result.get("iteration", iterations_run)

            # Check if we should stop
            if result.get("workflow") == "synthesize":
                break

            # Update state for next iteration
            current_state.update(result)

        # Property: Iterations should not exceed max_iterations
        assert iterations_run <= max_iterations, (
            f"Iterations {iterations_run} exceeded max {max_iterations}"
        )

    @given(
        max_iterations=st.integers(min_value=1, max_value=3),
    )
    @settings(max_examples=100)
    def test_parliament_signals_synthesis_at_limit(self, max_iterations: int):
        """Feature: multi-agent-sdk, Property 10: Parliament Workflow Iteration Limit

        When max iterations is reached, parliament should signal synthesis.

        """
        agents = [MockAgent("agent_0", "Response")]

        # Start at max iterations
        state = {
            "agents": agents,
            "task_assignments": [{"agent_id": "agent_0", "task": "Task"}],
            "prompt": "Test prompt",
            "max_iterations": max_iterations,
            "iteration": max_iterations,  # Already at limit
            "conflicts": [{"agents": ["agent_0"], "type": "test"}],  # Has conflicts
            "agent_results": [],
        }

        result = asyncio.run(parliament_workflow(state))

        # Property: Should signal synthesis when at max iterations
        assert result.get("workflow") == "synthesize"


class TestShouldContinueParliament:
    """Tests for the parliament continuation logic."""

    @given(
        iteration=st.integers(min_value=0, max_value=10),
        max_iterations=st.integers(min_value=1, max_value=5),
    )
    @settings(max_examples=100)
    def test_continues_when_under_limit_with_conflicts(
        self, iteration: int, max_iterations: int
    ):
        """Test that parliament continues when under limit and has conflicts."""
        state = {
            "iteration": iteration,
            "max_iterations": max_iterations,
            "conflicts": [{"type": "test"}] if iteration < max_iterations else [],
        }

        result = should_continue_parliament(state)

        if iteration >= max_iterations:
            assert result == "synthesize"
        elif state["conflicts"]:
            assert result == "parliament_workflow"
        else:
            assert result == "synthesize"

    def test_synthesize_when_workflow_flag_set(self):
        """Test that synthesis is triggered when workflow flag is set."""
        state = {
            "workflow": "synthesize",
            "iteration": 0,
            "max_iterations": 3,
            "conflicts": [{"type": "test"}],
        }

        result = should_continue_parliament(state)
        assert result == "synthesize"

    def test_synthesize_when_no_conflicts(self):
        """Test that synthesis is triggered when no conflicts remain."""
        state = {
            "iteration": 1,
            "max_iterations": 3,
            "conflicts": [],
        }

        result = should_continue_parliament(state)
        assert result == "synthesize"


class TestWorkflowEventEmission:
    """Tests for workflow event emission.

    Validates: Requirements 6.1-6.3, 7.1-7.5, 8.1-8.6
    """

    def test_router_workflow_emits_workflow_events(self):
        """Test that router workflow emits workflow_start and workflow_end events.

        Validates: Requirements 6.2, 6.3
        """
        from unittest.mock import MagicMock, patch

        from kiva.events import EventType

        emitted_events = []

        def capture_event(event):
            if isinstance(event, dict):
                emitted_events.append(event)

        with patch("kiva.workflows.utils.get_stream_writer") as mock_writer:
            mock_writer.return_value = capture_event

            agent = MockAgent("test_agent", "Test response")
            state = {
                "agents": [agent],
                "task_assignments": [{"agent_id": "test_agent", "task": "Test task"}],
                "prompt": "Test prompt",
                "execution_id": "exec-123",
            }

            asyncio.run(router_workflow(state))

        # Verify workflow events were emitted
        event_types = [e.get("type") for e in emitted_events]
        assert EventType.WORKFLOW_START.value in event_types
        assert EventType.WORKFLOW_END.value in event_types

        # Verify workflow_start event data
        workflow_start = next(
            e for e in emitted_events if e.get("type") == EventType.WORKFLOW_START.value
        )
        assert workflow_start["data"]["workflow"] == "router"
        assert "test_agent" in workflow_start["data"]["agent_ids"]

        # Verify workflow_end event data
        workflow_end = next(
            e for e in emitted_events if e.get("type") == EventType.WORKFLOW_END.value
        )
        assert workflow_end["data"]["workflow"] == "router"
        assert workflow_end["data"]["success"] is True

    def test_router_workflow_emits_agent_events(self):
        """Test that router workflow emits agent_start and agent_end events.

        Validates: Requirements 7.1, 7.3
        """
        from unittest.mock import patch

        from kiva.events import EventType

        emitted_events = []

        def capture_event(event):
            if isinstance(event, dict):
                emitted_events.append(event)

        with patch("kiva.workflows.utils.get_stream_writer") as mock_writer:
            mock_writer.return_value = capture_event

            agent = MockAgent("test_agent", "Test response")
            state = {
                "agents": [agent],
                "task_assignments": [{"agent_id": "test_agent", "task": "Test task"}],
                "prompt": "Test prompt",
                "execution_id": "exec-123",
            }

            asyncio.run(router_workflow(state))

        # Verify agent events were emitted
        event_types = [e.get("type") for e in emitted_events]
        assert EventType.AGENT_START.value in event_types
        assert EventType.AGENT_END.value in event_types

        # Verify agent_start event data
        agent_start = next(
            e for e in emitted_events if e.get("type") == EventType.AGENT_START.value
        )
        assert agent_start["data"]["agent_id"] == "test_agent"
        assert agent_start["data"]["task"] == "Test task"
        assert "invocation_id" in agent_start["data"]

        # Verify agent_end event data
        agent_end = next(
            e for e in emitted_events if e.get("type") == EventType.AGENT_END.value
        )
        assert agent_end["data"]["agent_id"] == "test_agent"
        assert agent_end["data"]["success"] is True
        assert "duration_ms" in agent_end["data"]

    def test_router_workflow_emits_agent_error_on_failure(self):
        """Test that router workflow emits agent_error event on failure.

        Validates: Requirements 7.4
        """
        from unittest.mock import patch

        from kiva.events import EventType

        emitted_events = []

        def capture_event(event):
            if isinstance(event, dict):
                emitted_events.append(event)

        with patch("kiva.workflows.utils.get_stream_writer") as mock_writer:
            mock_writer.return_value = capture_event

            agent = FailingAgent("failing_agent", "Test error")
            state = {
                "agents": [agent],
                "task_assignments": [{"agent_id": "failing_agent", "task": "Test task"}],
                "prompt": "Test prompt",
                "execution_id": "exec-123",
            }

            asyncio.run(router_workflow(state))

        # Verify agent_error event was emitted
        event_types = [e.get("type") for e in emitted_events]
        assert EventType.AGENT_ERROR.value in event_types

        # Verify agent_error event data
        agent_error = next(
            e for e in emitted_events if e.get("type") == EventType.AGENT_ERROR.value
        )
        assert agent_error["data"]["agent_id"] == "failing_agent"
        assert agent_error["data"]["error_type"] == "RuntimeError"
        assert "error_message" in agent_error["data"]

    def test_supervisor_workflow_emits_parallel_events(self):
        """Test that supervisor workflow emits parallel_start and parallel_complete events.

        Validates: Requirements 9.1, 9.3
        """
        from unittest.mock import patch

        from kiva.events import EventType

        emitted_events = []

        def capture_event(event):
            if isinstance(event, dict):
                emitted_events.append(event)

        with patch("kiva.workflows.utils.get_stream_writer") as mock_writer:
            mock_writer.return_value = capture_event

            agents = [
                MockAgent("agent_0", "Response 0"),
                MockAgent("agent_1", "Response 1"),
            ]
            state = {
                "agents": agents,
                "task_assignments": [
                    {"agent_id": "agent_0", "task": "Task 0"},
                    {"agent_id": "agent_1", "task": "Task 1"},
                ],
                "prompt": "Test prompt",
                "execution_id": "exec-123",
                "max_parallel_agents": 5,
            }

            asyncio.run(supervisor_workflow(state))

        # Verify parallel events were emitted
        event_types = [e.get("type") for e in emitted_events]
        assert EventType.PARALLEL_START.value in event_types
        assert EventType.PARALLEL_COMPLETE.value in event_types

        # Verify parallel_start event data
        parallel_start = next(
            e for e in emitted_events if e.get("type") == EventType.PARALLEL_START.value
        )
        assert "batch_id" in parallel_start["data"]
        assert len(parallel_start["data"]["agent_ids"]) == 2

        # Verify parallel_complete event data
        parallel_complete = next(
            e for e in emitted_events if e.get("type") == EventType.PARALLEL_COMPLETE.value
        )
        assert parallel_complete["data"]["success_count"] == 2
        assert parallel_complete["data"]["failure_count"] == 0
        assert "duration_ms" in parallel_complete["data"]

    def test_supervisor_workflow_emits_agent_events_for_each_agent(self):
        """Test that supervisor workflow emits agent events for each agent.

        Validates: Requirements 7.1, 7.3
        """
        from unittest.mock import patch

        from kiva.events import EventType

        emitted_events = []

        def capture_event(event):
            if isinstance(event, dict):
                emitted_events.append(event)

        with patch("kiva.workflows.utils.get_stream_writer") as mock_writer:
            mock_writer.return_value = capture_event

            agents = [
                MockAgent("agent_0", "Response 0"),
                MockAgent("agent_1", "Response 1"),
            ]
            state = {
                "agents": agents,
                "task_assignments": [
                    {"agent_id": "agent_0", "task": "Task 0"},
                    {"agent_id": "agent_1", "task": "Task 1"},
                ],
                "prompt": "Test prompt",
                "execution_id": "exec-123",
            }

            asyncio.run(supervisor_workflow(state))

        # Count agent events
        agent_starts = [
            e for e in emitted_events if e.get("type") == EventType.AGENT_START.value
        ]
        agent_ends = [
            e for e in emitted_events if e.get("type") == EventType.AGENT_END.value
        ]

        # Should have 2 agent_start and 2 agent_end events
        assert len(agent_starts) == 2
        assert len(agent_ends) == 2

        # Verify both agents have events
        start_agent_ids = {e["data"]["agent_id"] for e in agent_starts}
        end_agent_ids = {e["data"]["agent_id"] for e in agent_ends}
        assert start_agent_ids == {"agent_0", "agent_1"}
        assert end_agent_ids == {"agent_0", "agent_1"}

    @given(st.integers(min_value=2, max_value=4))
    @settings(max_examples=50)
    def test_supervisor_emits_correct_event_count(self, num_agents: int):
        """Property: Supervisor emits correct number of agent events.

        Validates: Requirements 7.1, 7.3
        """
        from unittest.mock import patch

        from kiva.events import EventType

        emitted_events = []

        def capture_event(event):
            if isinstance(event, dict):
                emitted_events.append(event)

        with patch("kiva.workflows.utils.get_stream_writer") as mock_writer:
            mock_writer.return_value = capture_event

            agents = [
                MockAgent(f"agent_{i}", f"Response {i}") for i in range(num_agents)
            ]
            state = {
                "agents": agents,
                "task_assignments": [
                    {"agent_id": f"agent_{i}", "task": f"Task {i}"}
                    for i in range(num_agents)
                ],
                "prompt": "Test prompt",
                "execution_id": "exec-123",
            }

            asyncio.run(supervisor_workflow(state))

        # Count agent events
        agent_starts = [
            e for e in emitted_events if e.get("type") == EventType.AGENT_START.value
        ]
        agent_ends = [
            e for e in emitted_events if e.get("type") == EventType.AGENT_END.value
        ]

        # Should have num_agents agent_start and agent_end events
        assert len(agent_starts) == num_agents
        assert len(agent_ends) == num_agents

        # Clear for next iteration
        emitted_events.clear()


class TestInstanceEventEmission:
    """Tests for instance event emission in workflows.

    Validates: Requirements 8.1-8.6
    """

    def test_supervisor_with_instances_emits_instance_events(self):
        """Test that supervisor with instances emits instance events.

        Validates: Requirements 8.1, 8.2, 8.4
        """
        from unittest.mock import patch

        from kiva.events import EventType

        emitted_events = []

        def capture_event(event):
            if isinstance(event, dict):
                emitted_events.append(event)

        with patch("kiva.workflows.utils.get_stream_writer") as mock_writer:
            mock_writer.return_value = capture_event

            agent = MockAgent("agent_0", "Response")
            state = {
                "agents": [agent],
                "task_assignments": [
                    {"agent_id": "agent_0", "task": "Task", "instances": 2}
                ],
                "prompt": "Test prompt",
                "execution_id": "exec-123",
                "parallel_strategy": "fan_out",
                "max_parallel_agents": 5,
            }

            asyncio.run(supervisor_workflow(state))

        # Verify instance events were emitted
        event_types = [e.get("type") for e in emitted_events]

        # Should have instance_spawn, instance_start, instance_end events
        assert EventType.INSTANCE_SPAWN.value in event_types
        assert EventType.INSTANCE_START.value in event_types
        assert EventType.INSTANCE_END.value in event_types

        # Count instance events
        instance_spawns = [
            e for e in emitted_events if e.get("type") == EventType.INSTANCE_SPAWN.value
        ]
        instance_starts = [
            e for e in emitted_events if e.get("type") == EventType.INSTANCE_START.value
        ]
        instance_ends = [
            e for e in emitted_events if e.get("type") == EventType.INSTANCE_END.value
        ]

        # Should have 2 of each (2 instances)
        assert len(instance_spawns) == 2
        assert len(instance_starts) == 2
        assert len(instance_ends) == 2

    def test_instance_events_have_correct_ids(self):
        """Test that instance events have correct instance_id and agent_id.

        Validates: Requirements 8.1, 8.2, 8.4
        """
        from unittest.mock import patch

        from kiva.events import EventType

        emitted_events = []

        def capture_event(event):
            if isinstance(event, dict):
                emitted_events.append(event)

        with patch("kiva.workflows.utils.get_stream_writer") as mock_writer:
            mock_writer.return_value = capture_event

            agent = MockAgent("agent_0", "Response")
            state = {
                "agents": [agent],
                "task_assignments": [
                    {"agent_id": "agent_0", "task": "Task", "instances": 1}
                ],
                "prompt": "Test prompt",
                "execution_id": "exec-123",
                "parallel_strategy": "fan_out",
            }

            asyncio.run(supervisor_workflow(state))

        # Get instance events
        instance_events = [
            e for e in emitted_events
            if e.get("type") in [
                EventType.INSTANCE_SPAWN.value,
                EventType.INSTANCE_START.value,
                EventType.INSTANCE_END.value,
            ]
        ]

        # All instance events should have instance_id and agent_id
        for event in instance_events:
            assert event.get("instance_id") is not None or event["data"].get("instance_id") is not None
            assert event.get("agent_id") is not None or event["data"].get("agent_id") is not None

    @given(st.integers(min_value=1, max_value=3))
    @settings(max_examples=30)
    def test_instance_count_matches_configuration(self, num_instances: int):
        """Property: Number of instance events matches configured instances.

        Validates: Requirements 8.1, 8.2, 8.4
        """
        from unittest.mock import patch

        from kiva.events import EventType

        emitted_events = []

        def capture_event(event):
            if isinstance(event, dict):
                emitted_events.append(event)

        with patch("kiva.workflows.utils.get_stream_writer") as mock_writer:
            mock_writer.return_value = capture_event

            agent = MockAgent("agent_0", "Response")
            state = {
                "agents": [agent],
                "task_assignments": [
                    {"agent_id": "agent_0", "task": "Task", "instances": num_instances}
                ],
                "prompt": "Test prompt",
                "execution_id": "exec-123",
                "parallel_strategy": "fan_out",
                "max_parallel_agents": 10,
            }

            asyncio.run(supervisor_workflow(state))

        # Count instance events
        instance_spawns = [
            e for e in emitted_events if e.get("type") == EventType.INSTANCE_SPAWN.value
        ]
        instance_ends = [
            e for e in emitted_events if e.get("type") == EventType.INSTANCE_END.value
        ]

        # Should match configured instance count
        assert len(instance_spawns) == num_instances
        assert len(instance_ends) == num_instances

        # Clear for next iteration
        emitted_events.clear()
