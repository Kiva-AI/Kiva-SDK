"""E2E test for Parallel Agent Instances.

Tests the parallel instance spawning feature for fan_out and map_reduce strategies.
"""

import pytest

from kiva import Kiva
from kiva.events import EventType


class TestParallelInstancesE2E:
    """E2E tests for parallel agent instance execution."""

    @pytest.mark.asyncio
    async def test_parallel_instances_basic(self, api_config, weather_func):
        """Test basic parallel instance execution."""
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
        async for event in kiva.stream("Get weather for Beijing, Tokyo, and London"):
            if event.type == EventType.SYNTHESIS_COMPLETE:
                result = event.data.get("result", "")

        assert result is not None
        print(f"\nParallel Instances Result: {result}")

    @pytest.mark.asyncio
    async def test_parallel_instances_with_multiple_agents(
        self, api_config, weather_func, search_func
    ):
        """Test parallel instances with multiple agent types."""
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
            "Get weather for 3 cities and search for travel tips"
        ):
            if event.type == EventType.SYNTHESIS_COMPLETE:
                result = event.data.get("result", "")

        assert result is not None
        print(f"\nMultiple Agents with Instances Result: {result}")

    @pytest.mark.asyncio
    async def test_parallel_instances_calculations(self, api_config, calculate_func):
        """Test parallel instances for calculations."""
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
        async for event in kiva.stream("Calculate these: 10*10, 20*20, 30*30"):
            if event.type == EventType.SYNTHESIS_COMPLETE:
                result = event.data.get("result", "")

        assert result is not None
        print(f"\nParallel Calculations Result: {result}")

    @pytest.mark.asyncio
    async def test_parallel_instances_search(self, api_config, search_func):
        """Test parallel instances for search queries."""
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
        async for event in kiva.stream(
            "Search for information about Python, AI, and Machine Learning"
        ):
            if event.type == EventType.SYNTHESIS_COMPLETE:
                result = event.data.get("result", "")

        assert result is not None
        print(f"\nParallel Search Result: {result}")
