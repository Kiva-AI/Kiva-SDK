"""Kiva SDK - Multi-Agent Orchestration Framework.

Kiva provides a flexible framework for orchestrating multiple AI agents using
LangChain and LangGraph. It supports three workflow patterns:

- Router: Routes tasks to a single agent (simple tasks)
- Supervisor: Coordinates parallel agent execution (medium complexity)
- Parliament: Iterative conflict resolution (complex reasoning)

Example:
    High-level API::

        from kiva import Kiva

        kiva = Kiva(base_url="...", api_key="...", model="gpt-4o")

        @kiva.agent("weather", "Gets weather info")
        def get_weather(city: str) -> str:
            return f"Sunny in {city}"

        kiva.run("What's the weather in Tokyo?")

    Modular application with routers::

        from kiva import Kiva, AgentRouter

        # In agents/weather.py
        router = AgentRouter(prefix="weather")

        @router.agent("forecast", "Gets forecasts")
        def get_forecast(city: str) -> str:
            return f"Sunny in {city}"

        # In main.py
        kiva = Kiva(base_url="...", api_key="...", model="gpt-4o")
        kiva.include_router(router)
        kiva.run("What's the weather?")
"""

# High-level API (public)
from kiva.client import Kiva

# Events (public)
from kiva.events import (
    EventFactory,
    EventPhase,
    EventSeverity,
    EventType,
    StreamEvent,
)

# Exceptions (public)
from kiva.exceptions import (
    AgentError,
    ConfigurationError,
    SDKError,
    WorkflowError,
)
from kiva.router import AgentRouter

__all__ = [
    # High-level API
    "Kiva",
    "AgentRouter",
    # Events
    "EventFactory",
    "EventPhase",
    "EventSeverity",
    "EventType",
    "StreamEvent",
    # Exceptions
    "SDKError",
    "ConfigurationError",
    "AgentError",
    "WorkflowError",
]
