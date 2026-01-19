"""E2E test for Router workflow - simple single-agent tasks.

Tests the router workflow which routes tasks to a single agent.
"""

import pytest

from kiva import Kiva
from kiva.events import EventType


class TestRouterWorkflowE2E:
    """E2E tests for router workflow with single agent execution."""

    @pytest.mark.asyncio
    async def test_router_simple_weather_query(self, api_config, weather_func):
        """Test simple weather query routed to single agent."""
        kiva = Kiva(
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model=api_config["model"],
        )

        @kiva.agent("weather", "Gets weather information for cities")
        def get_weather(city: str) -> str:
            """Get weather for a city."""
            return weather_func(city)

        result = None
        async for event in kiva.stream("What's the weather in Beijing?"):
            if event.type == EventType.SYNTHESIS_COMPLETE:
                result = event.data.get("result", "")

        assert result is not None
        assert len(result) > 0
        print(f"\nSimple Weather Result: {result}")

    @pytest.mark.asyncio
    async def test_router_simple_calculation(self, api_config, calculate_func):
        """Test simple calculation routed to calculator agent."""
        kiva = Kiva(
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model=api_config["model"],
        )

        @kiva.agent("calculator", "Performs mathematical calculations")
        def calculate(expression: str) -> str:
            """Calculate expression."""
            return calculate_func(expression)

        result = None
        async for event in kiva.stream("Calculate 15 * 8"):
            if event.type == EventType.SYNTHESIS_COMPLETE:
                result = event.data.get("result", "")

        assert result is not None
        print(f"\nCalculation Result: {result}")

    @pytest.mark.asyncio
    async def test_router_search_query(self, api_config, search_func):
        """Test search query routed to search agent."""
        kiva = Kiva(
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model=api_config["model"],
        )

        @kiva.agent("search", "Searches for information")
        def search(query: str) -> str:
            """Search for information."""
            return search_func(query)

        result = None
        async for event in kiva.stream("Search for information about Python"):
            if event.type == EventType.SYNTHESIS_COMPLETE:
                result = event.data.get("result", "")

        assert result is not None
        print(f"\nSearch Result: {result}")
