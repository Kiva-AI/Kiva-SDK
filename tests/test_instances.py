"""Tests for agent instance spawning and parallel execution.

These tests validate the new instance-level parallelization capabilities.
"""

import asyncio

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from kiva.state import AgentInstanceState, OrchestratorState, PlanningResult, TaskAssignment
from kiva.workflows.utils import (
    create_instance_context,
    generate_instance_id,
)


class MockAgent:
    """Mock agent for testing instance execution."""

    def __init__(self, name: str, response: str = "Mock response"):
        self.name = name
        self.response = response
        self.call_count = 0

    async def ainvoke(self, input_data: dict, **kwargs) -> dict:
        """Mock invoke that returns a predefined response."""
        self.call_count += 1
        return {"messages": [type("Message", (), {"content": self.response})()]}


class TestAgentInstanceState:
    """Tests for AgentInstanceState TypedDict."""

    def test_create_instance_state(self):
        """Test creating an AgentInstanceState."""
        state = AgentInstanceState(
            instance_id="test-instance-001",
            agent_id="search_agent",
            task="Search for Python tutorials",
            context={"scratchpad": []},
            execution_id="exec-123",
            model_name="gpt-4o",
            api_key=None,
            base_url=None,
        )
        assert state["instance_id"] == "test-instance-001"
        assert state["agent_id"] == "search_agent"
        assert state["task"] == "Search for Python tutorials"

    def test_instance_state_has_isolated_context(self):
        """Test that each instance state has its own context."""
        state1 = AgentInstanceState(
            instance_id="inst-1",
            agent_id="agent",
            task="task1",
            context={"scratchpad": ["item1"]},
            execution_id="exec",
            model_name="gpt-4o",
            api_key=None,
            base_url=None,
        )
        state2 = AgentInstanceState(
            instance_id="inst-2",
            agent_id="agent",
            task="task2",
            context={"scratchpad": ["item2"]},
            execution_id="exec",
            model_name="gpt-4o",
            api_key=None,
            base_url=None,
        )
        # Contexts should be independent
        assert state1["context"]["scratchpad"] != state2["context"]["scratchpad"]


class TestTaskAssignment:
    """Tests for TaskAssignment TypedDict."""

    def test_create_task_assignment_minimal(self):
        """Test creating a minimal TaskAssignment."""
        assignment = TaskAssignment(
            agent_id="search_agent",
            task="Search for info",
        )
        assert assignment["agent_id"] == "search_agent"
        assert assignment["task"] == "Search for info"

    def test_create_task_assignment_with_instances(self):
        """Test creating a TaskAssignment with multiple instances."""
        assignment = TaskAssignment(
            agent_id="search_agent",
            task="Search for info",
            instances=3,
            instance_context={"topic": "Python"},
        )
        assert assignment["instances"] == 3
        assert assignment["instance_context"]["topic"] == "Python"


class TestPlanningResult:
    """Tests for PlanningResult TypedDict."""

    def test_create_planning_result(self):
        """Test creating a PlanningResult."""
        result = PlanningResult(
            complexity="medium",
            workflow="supervisor",
            reasoning="Multiple independent tasks",
            task_assignments=[
                TaskAssignment(agent_id="agent1", task="task1", instances=2),
                TaskAssignment(agent_id="agent2", task="task2", instances=1),
            ],
            parallel_strategy="fan_out",
            total_instances=3,
        )
        assert result["complexity"] == "medium"
        assert result["parallel_strategy"] == "fan_out"
        assert result["total_instances"] == 3


class TestGenerateInstanceId:
    """Tests for generate_instance_id function."""

    @given(
        execution_id=st.text(min_size=8, max_size=36),
        agent_id=st.text(min_size=1, max_size=20).filter(lambda x: x.strip()),
        instance_num=st.integers(min_value=0, max_value=100),
    )
    @settings(max_examples=100)
    def test_instance_id_contains_components(
        self, execution_id: str, agent_id: str, instance_num: int
    ):
        """Test that instance ID contains all components."""
        instance_id = generate_instance_id(execution_id, agent_id, instance_num)
        
        # Should contain execution prefix
        assert execution_id[:8] in instance_id
        # Should contain agent_id
        assert agent_id in instance_id
        # Should contain instance number marker
        assert f"i{instance_num}" in instance_id

    @given(
        num_instances=st.integers(min_value=2, max_value=10),
    )
    @settings(max_examples=100)
    def test_instance_ids_are_unique(self, num_instances: int):
        """Test that generated instance IDs are unique."""
        execution_id = "test-exec-12345678"
        agent_id = "test_agent"
        
        instance_ids = [
            generate_instance_id(execution_id, agent_id, i)
            for i in range(num_instances)
        ]
        
        # All IDs should be unique
        assert len(set(instance_ids)) == num_instances


class TestCreateInstanceContext:
    """Tests for create_instance_context function."""

    def test_creates_basic_context(self):
        """Test creating a basic instance context."""
        context = create_instance_context(
            instance_id="inst-001",
            agent_id="search_agent",
            task="Search for Python",
        )
        
        assert context["instance_id"] == "inst-001"
        assert context["agent_id"] == "search_agent"
        assert context["task"] == "Search for Python"
        assert context["scratchpad"] == []
        assert context["memory"] == {}
        assert "created_at" in context

    def test_extends_base_context(self):
        """Test that base context is extended."""
        base = {"custom_key": "custom_value", "topic": "Python"}
        context = create_instance_context(
            instance_id="inst-001",
            agent_id="agent",
            task="task",
            base_context=base,
        )
        
        assert context["custom_key"] == "custom_value"
        assert context["topic"] == "Python"
        # Standard fields should still be present
        assert context["instance_id"] == "inst-001"
        assert context["scratchpad"] == []

    @given(
        num_contexts=st.integers(min_value=2, max_value=5),
    )
    @settings(max_examples=100)
    def test_contexts_are_independent(self, num_contexts: int):
        """Test that created contexts are independent."""
        contexts = [
            create_instance_context(
                instance_id=f"inst-{i}",
                agent_id="agent",
                task=f"task-{i}",
            )
            for i in range(num_contexts)
        ]
        
        # Modify one context's scratchpad
        contexts[0]["scratchpad"].append("item")
        
        # Other contexts should not be affected
        for i in range(1, num_contexts):
            assert contexts[i]["scratchpad"] == []


class TestOrchestratorStateWithInstances:
    """Tests for OrchestratorState with instance-related fields."""

    def test_state_has_parallel_strategy_field(self):
        """Test that OrchestratorState includes parallel_strategy."""
        state: OrchestratorState = {
            "messages": [],
            "prompt": "test",
            "complexity": "medium",
            "workflow": "supervisor",
            "agents": [],
            "task_assignments": [],
            "agent_results": [],
            "final_result": None,
            "execution_id": "exec-123",
            "conflicts": [],
            "iteration": 0,
            "model_name": "gpt-4o",
            "api_key": None,
            "base_url": None,
            "workflow_override": None,
            "max_iterations": 10,
            "max_parallel_agents": 5,
            "parallel_strategy": "fan_out",
            "total_instances": 3,
            "instance_contexts": [],
        }
        assert state["parallel_strategy"] == "fan_out"
        assert state["total_instances"] == 3

    def test_instance_contexts_accumulate(self):
        """Test that instance_contexts field uses operator.add."""
        # This is verified by the Annotated type in the state definition
        # Here we just verify the field exists and is a list
        state: OrchestratorState = {
            "messages": [],
            "prompt": "test",
            "complexity": "simple",
            "workflow": "router",
            "agents": [],
            "task_assignments": [],
            "agent_results": [],
            "final_result": None,
            "execution_id": "exec-123",
            "conflicts": [],
            "iteration": 0,
            "model_name": "gpt-4o",
            "api_key": None,
            "base_url": None,
            "workflow_override": None,
            "max_iterations": 10,
            "max_parallel_agents": 5,
            "parallel_strategy": "none",
            "total_instances": 1,
            "instance_contexts": [{"ctx": 1}, {"ctx": 2}],
        }
        assert len(state["instance_contexts"]) == 2


class TestSupervisorWithInstances:
    """Tests for supervisor workflow with multi-instance support."""

    @given(
        num_instances=st.integers(min_value=2, max_value=4),
    )
    @settings(max_examples=100)
    def test_supervisor_spawns_multiple_instances(self, num_instances: int):
        """Test that supervisor can spawn multiple instances of same agent."""
        from kiva.workflows.supervisor import supervisor_workflow
        
        agent = MockAgent("search_agent", "Search result")
        
        state: OrchestratorState = {
            "messages": [],
            "prompt": "Search for multiple topics",
            "complexity": "medium",
            "workflow": "supervisor",
            "agents": [agent],
            "task_assignments": [
                TaskAssignment(
                    agent_id="search_agent",
                    task="Search task",
                    instances=num_instances,
                )
            ],
            "agent_results": [],
            "final_result": None,
            "execution_id": "exec-123",
            "conflicts": [],
            "iteration": 0,
            "model_name": "gpt-4o",
            "api_key": None,
            "base_url": None,
            "workflow_override": None,
            "max_iterations": 10,
            "max_parallel_agents": 10,
            "parallel_strategy": "fan_out",
            "total_instances": num_instances,
            "instance_contexts": [],
        }
        
        result = asyncio.run(supervisor_workflow(state))
        
        # Should have results for all instances
        assert len(result["agent_results"]) == num_instances
        # Agent should have been called num_instances times
        assert agent.call_count == num_instances

    def test_supervisor_respects_max_parallel(self):
        """Test that supervisor respects max_parallel_agents limit."""
        from kiva.workflows.supervisor import supervisor_workflow
        
        agent = MockAgent("agent", "Result")
        max_parallel = 3
        requested_instances = 10
        
        state: OrchestratorState = {
            "messages": [],
            "prompt": "test",
            "complexity": "medium",
            "workflow": "supervisor",
            "agents": [agent],
            "task_assignments": [
                TaskAssignment(
                    agent_id="agent",
                    task="task",
                    instances=requested_instances,
                )
            ],
            "agent_results": [],
            "final_result": None,
            "execution_id": "exec-123",
            "conflicts": [],
            "iteration": 0,
            "model_name": "gpt-4o",
            "api_key": None,
            "base_url": None,
            "workflow_override": None,
            "max_iterations": 10,
            "max_parallel_agents": max_parallel,
            "parallel_strategy": "fan_out",
            "total_instances": requested_instances,
            "instance_contexts": [],
        }
        
        result = asyncio.run(supervisor_workflow(state))
        
        # Should be limited to max_parallel
        assert len(result["agent_results"]) <= max_parallel


class TestAnalyzeAndPlanWithInstances:
    """Tests for analyze_and_plan with instance planning."""

    def test_parse_json_with_instances(self):
        """Test parsing JSON response with instance configuration."""
        from kiva.nodes.analyze import _parse_json_response
        
        content = '''{
            "complexity": "medium",
            "workflow": "supervisor",
            "parallel_strategy": "fan_out",
            "reasoning": "Multiple independent searches needed",
            "task_assignments": [
                {"agent_id": "search", "task": "Search topic 1", "instances": 3},
                {"agent_id": "analyze", "task": "Analyze results", "instances": 1}
            ],
            "total_instances": 4
        }'''
        
        result = _parse_json_response(content)
        
        assert result["parallel_strategy"] == "fan_out"
        assert result["total_instances"] == 4
        assert len(result["task_assignments"]) == 2
        assert result["task_assignments"][0]["instances"] == 3

    def test_normalize_task_assignments_with_instances(self):
        """Test normalizing task assignments with instance counts."""
        from kiva.nodes.analyze import _normalize_task_assignments
        
        agents = [MockAgent("search"), MockAgent("analyze")]
        assignments = [
            {"agent_id": "search", "task": "Search", "instances": 3},
            {"agent_id": "analyze", "task": "Analyze", "instances": 2},
        ]
        
        normalized, total = _normalize_task_assignments(
            assignments, agents, "fallback prompt", max_parallel=10
        )
        
        assert total == 5  # 3 + 2
        assert normalized[0]["instances"] == 3
        assert normalized[1]["instances"] == 2

    def test_normalize_respects_max_parallel(self):
        """Test that normalization respects max_parallel limit."""
        from kiva.nodes.analyze import _normalize_task_assignments
        
        agents = [MockAgent("agent")]
        assignments = [
            {"agent_id": "agent", "task": "Task", "instances": 10},
        ]
        
        normalized, total = _normalize_task_assignments(
            assignments, agents, "fallback", max_parallel=3
        )
        
        assert total <= 3
        assert normalized[0]["instances"] <= 3
