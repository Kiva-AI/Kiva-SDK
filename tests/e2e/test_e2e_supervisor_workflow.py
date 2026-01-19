"""E2E test for Supervisor workflow - parallel multi-agent tasks.

Tests the supervisor workflow which coordinates multiple agents in parallel.
"""

import pytest

from kiva import Kiva
from kiva.events import EventType


class TestSupervisorWorkflowE2E:
    """E2E tests for supervisor workflow with parallel agent execution."""

    @pytest.mark.asyncio
    async def test_supervisor_multi_agent_task(
        self, api_config, weather_func, calculate_func
    ):
        """Test task requiring multiple agents executed in parallel."""
        kiva = Kiva(
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model=api_config["model"],
        )

        @kiva.agent("weather", "Gets weather information for cities")
        def get_weather(city: str) -> str:
            """Get weather for a city."""
            return weather_func(city)

        @kiva.agent("calculator", "Performs mathematical calculations")
        def calculate(expression: str) -> str:
            """Calculate expression."""
            return calculate_func(expression)

        result = None
        async for event in kiva.stream(
            "What's the weather in Beijing? Also calculate 100 / 4"
        ):
            if event.type == EventType.SYNTHESIS_COMPLETE:
                result = event.data.get("result", "")

        assert result is not None
        print(f"\nMulti-Agent Result: {result}")

    @pytest.mark.asyncio
    async def test_supervisor_three_agents(
        self, api_config, weather_func, calculate_func, search_func
    ):
        """Test supervisor with three different agents."""
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
            "What's the weather in Paris? Calculate 25 * 4. Search for Python info."
        ):
            if event.type == EventType.SYNTHESIS_COMPLETE:
                result = event.data.get("result", "")

        assert result is not None
        print(f"\nThree Agents Result: {result}")
