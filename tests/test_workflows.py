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
