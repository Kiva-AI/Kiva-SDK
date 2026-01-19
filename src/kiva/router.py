"""Agent Router for modular multi-file applications.

This module provides the AgentRouter class, inspired by FastAPI's APIRouter,
enabling modular agent organization across multiple files.

Example:
    In agents/weather.py::

        from kiva import AgentRouter

        router = AgentRouter(prefix="weather", tags=["weather"])

        @router.agent("forecast", "Gets weather forecasts")
        def get_forecast(city: str) -> str:
            '''Get weather forecast for a city.'''
            return f"Sunny in {city}"

    In main.py::

        from kiva import Kiva
        from agents.weather import router as weather_router

        kiva = Kiva(base_url="...", api_key="...", model="gpt-4o")
        kiva.include_router(weather_router)
        kiva.run("What's the weather in Tokyo?")
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class AgentDefinition:
    """Internal representation of an agent definition.

    Attributes:
        name: Unique identifier for the agent.
        description: Human-readable description of the agent's capabilities.
        obj: The function or class that implements the agent's tools.
    """

    name: str
    description: str
    obj: Callable | type
    mcp_servers: dict[str, dict[str, Any]] | None = None


class AgentRouter:
    """Router for organizing agents in modular applications.

    Enables splitting agent definitions across multiple files while
    maintaining a clean, declarative API. Routers can be nested and
    combined with prefixes for namespace management.

    Args:
        prefix: Optional prefix for all agent names in this router.
        tags: Optional list of tags for categorization.

    Example:
        >>> router = AgentRouter(prefix="math")
        >>> @router.agent("calculator", "Performs calculations")
        ... def calculate(expr: str) -> str:
        ...     '''Evaluate a math expression.'''
        ...     return str(eval(expr))
    """

    def __init__(
        self,
        prefix: str = "",
        tags: list[str] | None = None,
    ):
        """Initialize the AgentRouter."""
        self.prefix = prefix
        self.tags = tags or []
        self._agents: list[AgentDefinition] = []
        self._routers: list[tuple[AgentRouter, str]] = []

    def _resolve_name(self, name: str) -> str:
        """Resolve the full agent name with prefix."""
        if self.prefix:
            return f"{self.prefix}_{name}"
        return name

    def agent(
        self,
        name: str,
        description: str,
        *,
        mcp_servers: dict[str, dict[str, Any]] | None = None,
    ) -> Callable:
        """Decorator to register an agent with this router.

        Can decorate either a single function (becomes a single-tool agent)
        or a class with methods (each method becomes a tool).

        Args:
            name: Unique identifier for the agent (will be prefixed).
            description: Human-readable description of the agent's purpose.
            mcp_servers: MCP 服务器配置，会合并进该 agent 的工具源。

        Returns:
            Decorator function that registers the agent.

        Example:
            >>> @router.agent("search", "Searches for information")
            ... def search(query: str) -> str:
            ...     '''Search for information.'''
            ...     return f"Results for {query}"
        """

        def decorator(obj: Callable | type) -> Callable | type:
            resolved_name = self._resolve_name(name)
            self._agents.append(
                AgentDefinition(
                    name=resolved_name,
                    description=description,
                    obj=obj,
                    mcp_servers=mcp_servers,
                )
            )
            return obj

        return decorator

    def include_router(self, router: "AgentRouter", prefix: str = "") -> None:
        """Include another router's agents in this router.

        Enables hierarchical organization of agents across modules.

        Args:
            router: The AgentRouter to include.
            prefix: Additional prefix to apply to included agents.

        Example:
            >>> main_router = AgentRouter()
            >>> sub_router = AgentRouter(prefix="sub")
            >>> main_router.include_router(sub_router, prefix="module")
        """
        self._routers.append((router, prefix))

    def get_agents(self) -> list[AgentDefinition]:
        """Get all agent definitions from this router and nested routers.

        Returns:
            List of AgentDefinition objects with resolved names.
        """
        agents = list(self._agents)

        for router, extra_prefix in self._routers:
            for agent_def in router.get_agents():
                # Build the full prefix: extra_prefix + self.prefix (if any)
                prefixes = [p for p in [extra_prefix, self.prefix] if p]
                if prefixes:
                    resolved_name = "_".join(prefixes) + "_" + agent_def.name
                else:
                    resolved_name = agent_def.name
                agents.append(
                    AgentDefinition(
                        name=resolved_name,
                        description=agent_def.description,
                        obj=agent_def.obj,
                        mcp_servers=agent_def.mcp_servers,
                    )
                )

        return agents
