"""Unit tests for data models: StreamEvent and exceptions."""

from kiva.events import EventPhase, EventSeverity, EventType, StreamEvent
from kiva.exceptions import (
    AgentError,
    ConfigurationError,
    SDKError,
    WorkflowError,
)


class TestStreamEvent:
    """Tests for StreamEvent dataclass."""

    def test_create_stream_event_with_all_fields(self):
        """Test creating StreamEvent with all fields."""
        event = StreamEvent(
            type=EventType.TOKEN,
            data={"content": "hello"},
            execution_id="exec-123",
            timestamp=1234567890.0,
            agent_id="agent_1",
        )
        assert event.type == EventType.TOKEN
        assert event.data == {"content": "hello"}
        assert event.timestamp == 1234567890.0
        assert event.agent_id == "agent_1"
        assert event.execution_id == "exec-123"

    def test_create_stream_event_without_agent_id(self):
        """Test creating StreamEvent without agent_id (defaults to None)."""
        event = StreamEvent(
            type=EventType.WORKFLOW_SELECTED,
            data={"workflow": "router"},
            execution_id="exec-123",
            timestamp=1234567890.0,
        )
        assert event.type == EventType.WORKFLOW_SELECTED
        assert event.agent_id is None

    def test_to_dict_method(self):
        """Test StreamEvent.to_dict() serialization."""
        event = StreamEvent(
            type=EventType.AGENT_END,
            data={"result": "success"},
            execution_id="exec-123",
            timestamp=1234567890.0,
            agent_id="worker_1",
        )
        result = event.to_dict()
        assert result["type"] == "agent_end"
        assert result["data"] == {"result": "success"}
        assert result["timestamp"] == 1234567890.0
        assert result["agent_id"] == "worker_1"
        assert result["execution_id"] == "exec-123"
        assert "timestamp_iso" in result
        assert result["phase"] == "initializing"
        assert result["severity"] == "info"

    def test_to_dict_with_none_agent_id(self):
        """Test to_dict() when agent_id is None."""
        event = StreamEvent(
            type=EventType.SYNTHESIS_COMPLETE,
            data={"result": "done"},
            execution_id="exec-123",
            timestamp=1234567890.0,
        )
        result = event.to_dict()
        assert result["agent_id"] is None


class TestExceptions:
    """Tests for exception hierarchy."""

    def test_sdk_error_is_base_exception(self):
        """Test SDKError is the base class."""
        error = SDKError("base error")
        assert isinstance(error, Exception)
        assert str(error) == "base error"

    def test_configuration_error_inherits_sdk_error(self):
        """Test ConfigurationError inherits from SDKError."""
        error = ConfigurationError("config error")
        assert isinstance(error, SDKError)
        assert isinstance(error, Exception)
        assert str(error) == "config error"

    def test_agent_error_with_all_fields(self):
        """Test AgentError with agent_id and original_error."""
        original = ValueError("original error")
        error = AgentError(
            message="Agent failed",
            agent_id="worker_1",
            original_error=original,
        )
        assert isinstance(error, SDKError)
        assert error.agent_id == "worker_1"
        assert error.original_error is original
        assert "Agent failed" in str(error)
        assert "Recovery:" in str(error)

    def test_agent_error_without_original_error(self):
        """Test AgentError without original_error."""
        error = AgentError(
            message="Agent timeout",
            agent_id="worker_2",
        )
        assert error.agent_id == "worker_2"
        assert error.original_error is None

    def test_workflow_error_with_all_fields(self):
        """Test WorkflowError with workflow and execution_id."""
        error = WorkflowError(
            message="Workflow failed",
            workflow="supervisor",
            execution_id="exec_123",
        )
        assert isinstance(error, SDKError)
        assert error.workflow == "supervisor"
        assert error.execution_id == "exec_123"
        assert str(error) == "Workflow failed"

    def test_exception_hierarchy(self):
        """Test all exceptions inherit from SDKError."""
        assert issubclass(ConfigurationError, SDKError)
        assert issubclass(AgentError, SDKError)
        assert issubclass(WorkflowError, SDKError)
