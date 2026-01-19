"""E2E test for Parliament workflow - iterative conflict resolution.

Tests the parliament workflow which handles complex reasoning with
potential conflicts between agents.
"""

import pytest

from kiva import Kiva
from kiva.events import EventType


class TestParliamentWorkflowE2E:
    """E2E tests for parliament workflow with conflict resolution."""

    @pytest.mark.asyncio
    async def test_parliament_basic_execution(self, api_config, weather_func, search_func):
        """Test basic parliament workflow execution."""
        kiva = Kiva(
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model=api_config["model"],
        )

        @kiva.agent("weather", "Gets weather information")
        def get_weather(city: str) -> str:
            """Get weather for a city."""
            return weather_func(city)

        @kiva.agent("search", "Searches for information")
        def search(query: str) -> str:
            """Search for information."""
            return search_func(query)

        result = None
        async for event in kiva.stream(
            "Is it a good day for outdoor activities in Beijing? Consider weather and general advice."
        ):
            if event.type == EventType.SYNTHESIS_COMPLETE:
                result = event.data.get("result", "")

        assert result is not None
        print(f"\nParliament Result: {result}")

    @pytest.mark.asyncio
    async def test_parliament_with_three_agents(
        self, api_config, weather_func, calculate_func, search_func
    ):
        """Test parliament with three agents for complex reasoning."""
        kiva = Kiva(
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model=api_config["model"],
        )

        @kiva.agent("weather", "Gets weather information")
        def get_weather(city: str) -> str:
            """Get weather for a city."""
            return weather_func(city)

        @kiva.agent("calculator", "Performs calculations")
        def calculate(expression: str) -> str:
            """Calculate expression."""
            return calculate_func(expression)

        @kiva.agent("search", "Searches for information")
        def search(query: str) -> str:
            """Search for information."""
            return search_func(query)

        result = None
        async for event in kiva.stream(
            "Plan a trip: check weather in Tokyo, calculate budget (1000 * 7 days), and search for travel tips"
        ):
            if event.type == EventType.SYNTHESIS_COMPLETE:
                result = event.data.get("result", "")

        assert result is not None
        print(f"\nThree Agents Parliament Result: {result}")
