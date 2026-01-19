"""E2E test for AgentRouter - modular multi-file applications.

Tests the AgentRouter pattern for organizing agents across modules.
"""

import pytest

from kiva import AgentRouter, Kiva
from kiva.events import EventType


class TestAgentRouterE2E:
    """E2E tests for AgentRouter modular organization."""

    @pytest.mark.asyncio
    async def test_router_basic_usage(self, api_config):
        """Test basic AgentRouter usage."""
        router = AgentRouter(prefix="weather")

        @router.agent("forecast", "Gets weather forecast")
        def get_forecast(city: str) -> str:
            """Get forecast for a city."""
            return f"{city}: Sunny tomorrow"

        kiva = Kiva(
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model=api_config["model"],
        )
        kiva.include_router(router)

        result = None
        async for event in kiva.stream("What's the forecast for Beijing?"):
            if event.type == EventType.SYNTHESIS_COMPLETE:
                result = event.data.get("result", "")

        assert result is not None
        print(f"\nBasic Router Result: {result}")

    @pytest.mark.asyncio
    async def test_router_multiple_agents(self, api_config):
        """Test router with multiple agents."""
        router = AgentRouter(prefix="tools")

        @router.agent("weather", "Weather info")
        def weather(city: str) -> str:
            """Get weather."""
            return f"{city}: Clear, 22°C"

        @router.agent("calc", "Calculator")
        def calc(expr: str) -> str:
            """Calculate."""
            return str(eval(expr))

        kiva = Kiva(
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model=api_config["model"],
        )
        kiva.include_router(router)

        result = None
        async for event in kiva.stream("Weather in Tokyo and calculate 30 + 20"):
            if event.type == EventType.SYNTHESIS_COMPLETE:
                result = event.data.get("result", "")

        assert result is not None
        print(f"\nMultiple Agents Router Result: {result}")

    def test_multiple_routers(self, api_config):
        """Test including multiple routers."""
        weather_router = AgentRouter(prefix="weather")
        math_router = AgentRouter(prefix="math")

        @weather_router.agent("forecast", "Forecast")
        def forecast(city: str) -> str:
            """Get forecast."""
            return f"{city}: Partly cloudy"

        @math_router.agent("add", "Addition")
        def add(a: int, b: int) -> int:
            """Add numbers."""
            return a + b

        kiva = Kiva(
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model=api_config["model"],
        )
        kiva.include_router(weather_router)
        kiva.include_router(math_router)

        # Verify agents are registered with correct names
        agent_names = [a.name for a in kiva._agents]
        assert "weather_forecast" in agent_names
        assert "math_add" in agent_names
        print("\nMultiple Routers registered correctly")

    def test_nested_routers(self, api_config):
        """Test nested router hierarchy."""
        # Create nested structure
        api_router = AgentRouter(prefix="api")
        v1_router = AgentRouter(prefix="v1")

        @v1_router.agent("search", "Search endpoint")
        def search(query: str) -> str:
            """Search."""
            return f"Results for: {query}"

        api_router.include_router(v1_router)

        kiva = Kiva(
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model=api_config["model"],
        )
        kiva.include_router(api_router)

        # Verify nested naming
        agent_names = [a.name for a in kiva._agents]
        assert "api_v1_search" in agent_names
        print("\nNested Routers registered correctly")

    def test_router_with_class_agent(self, api_config):
        """Test router with class-based multi-tool agent."""
        router = AgentRouter(prefix="math")

        @router.agent("calculator", "Math calculator")
        class Calculator:
            def add(self, a: int, b: int) -> int:
                """Add."""
                return a + b

            def multiply(self, a: int, b: int) -> int:
                """Multiply."""
                return a * b

        kiva = Kiva(
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model=api_config["model"],
        )
        kiva.include_router(router)

        assert len(kiva._agents) == 1
        print("\nClass Agent Router registered correctly")

    def test_router_prefix_override(self, api_config):
        """Test adding extra prefix when including router."""
        router = AgentRouter(prefix="weather")

        @router.agent("current", "Current weather")
        def current(city: str) -> str:
            """Get current weather."""
            return f"{city}: Now sunny"

        kiva = Kiva(
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model=api_config["model"],
        )
        kiva.include_router(router, prefix="v2")

        # Should be v2_weather_current
        agent_names = [a.name for a in kiva._agents]
        assert "v2_weather_current" in agent_names
        print("\nPrefix Override works correctly")

    def test_mixed_direct_and_router_agents(self, api_config):
        """Test mixing direct agent registration with router inclusion."""
        kiva = Kiva(
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model=api_config["model"],
        )

        # Direct registration
        @kiva.agent("direct_weather", "Direct weather agent")
        def direct_weather(city: str) -> str:
            """Get weather directly."""
            return f"{city}: Direct sunny"

        # Router registration
        router = AgentRouter(prefix="routed")

        @router.agent("calc", "Routed calculator")
        def calc(expr: str) -> str:
            """Calculate."""
            return str(eval(expr))

        kiva.include_router(router)

        # Both should be registered
        agent_names = [a.name for a in kiva._agents]
        assert "direct_weather" in agent_names
        assert "routed_calc" in agent_names
        print("\nMixed Registration works correctly")

    def test_router_method_chaining(self, api_config):
        """Test method chaining with include_router."""
        router1 = AgentRouter(prefix="r1")
        router2 = AgentRouter(prefix="r2")

        @router1.agent("a1", "Agent 1")
        def a1() -> str:
            """Agent 1."""
            return "1"

        @router2.agent("a2", "Agent 2")
        def a2() -> str:
            """Agent 2."""
            return "2"

        kiva = Kiva(
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model=api_config["model"],
        )

        # Method chaining
        result = kiva.include_router(router1).include_router(router2)

        assert result is kiva
        assert len(kiva._agents) == 2
        print("\nMethod chaining works correctly")
