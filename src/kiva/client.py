"""Kiva Client - High-level API for multi-agent orchestration.

Example:
    Basic usage::

        kiva = Kiva(base_url="...", api_key="...", model="gpt-4o")

        @kiva.agent("calculator", "Performs math calculations")
        def calculate(expression: str) -> str:
            return str(eval(expression))

        result = await kiva.run("What is 15 * 8?")

    Streaming events::

        async for event in kiva.stream("What is 15 * 8?"):
            print(event.type)
"""

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from langchain.agents import create_agent
from langchain_core.tools import tool as lc_tool
from langchain_openai import ChatOpenAI

if TYPE_CHECKING:
    from kiva.events import StreamEvent
    from kiva.router import AgentRouter


@dataclass
class Agent:
    """Internal agent wrapper for storing agent metadata."""

    name: str
    description: str
    tools: list
    _compiled: object = field(default=None, repr=False)


class Kiva:
    """High-level client for multi-agent orchestration.

    Args:
        base_url: API endpoint URL for the LLM provider.
        api_key: Authentication key for the API.
        model: Model identifier (e.g., "gpt-4o").
        temperature: Sampling temperature. Defaults to 0.7.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float = 0.7,
    ):
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self._agents: list[Agent] = []

    def _create_model(self) -> ChatOpenAI:
        return ChatOpenAI(
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=self.temperature,
        )

    def _to_tools(self, obj) -> list:
        """Convert a function, class, or list to LangChain tools."""
        if callable(obj) and not isinstance(obj, type):
            return [lc_tool(obj)]
        elif isinstance(obj, type):
            instance = obj()
            tools = []
            for name in dir(instance):
                if name.startswith("_"):
                    continue
                method = getattr(instance, name)
                if callable(method) and method.__doc__:
                    tools.append(lc_tool(method))
            return tools
        elif isinstance(obj, list):
            return [lc_tool(f) if not hasattr(f, "invoke") else f for f in obj]
        else:
            raise ValueError(f"Cannot convert {type(obj)} to tools")

    def agent(self, name: str, description: str) -> Callable:
        """Decorator to register an agent."""

        def decorator(obj):
            tools = self._to_tools(obj)
            self._agents.append(Agent(name=name, description=description, tools=tools))
            return obj

        return decorator

    def add_agent(self, name: str, description: str, tools: list) -> "Kiva":
        """Add an agent with an explicit tools list."""
        converted = self._to_tools(tools)
        self._agents.append(Agent(name=name, description=description, tools=converted))
        return self

    def include_router(self, router: "AgentRouter", prefix: str = "") -> "Kiva":
        """Include agents from an AgentRouter."""
        for agent_def in router.get_agents():
            name = f"{prefix}_{agent_def.name}" if prefix else agent_def.name
            tools = self._to_tools(agent_def.obj)
            self._agents.append(
                Agent(name=name, description=agent_def.description, tools=tools)
            )
        return self

    def _build_agents(self) -> list:
        """Build LangChain agents from registered agent definitions."""
        built = []
        for agent_def in self._agents:
            agent = create_agent(model=self._create_model(), tools=agent_def.tools)
            agent.name = agent_def.name
            agent.description = agent_def.description
            built.append(agent)
        return built

    async def run(self, prompt: str, worker_max_iterations: int = 100) -> str | None:
        """Run orchestration with rich console visualization.

        Args:
            prompt: The task or question to process.
            worker_max_iterations: Maximum iterations for worker agents.

        Returns:
            Final result string, or None if no result was produced.
        """
        from kiva.console import run_with_console

        return await run_with_console(prompt, self, worker_max_iterations)

    async def stream(
        self, prompt: str, worker_max_iterations: int = 100
    ) -> AsyncIterator["StreamEvent"]:
        """Stream orchestration events.

        Args:
            prompt: The task or question to process.
            worker_max_iterations: Maximum iterations for worker agents.

        Yields:
            StreamEvent objects as they are produced.
        """
        from kiva.run import run

        async for event in run(
            prompt=prompt,
            agents=self._build_agents(),
            base_url=self.base_url,
            api_key=self.api_key,
            model_name=self.model,
            worker_max_iterations=worker_max_iterations,
        ):
            yield event
