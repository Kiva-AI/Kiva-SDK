"""E2E test for High-Level API (Kiva client).

Tests the Kiva class which provides the simplest interface for users.
"""

import pytest

from kiva import Kiva
from kiva.events import EventType


class TestHighLevelAPIE2E:
    """E2E tests for the high-level Kiva client API."""

    @pytest.mark.asyncio
    async def test_kiva_single_function_agent(self, api_config):
        """Test Kiva with a single function decorated as agent."""
        kiva = Kiva(
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model=api_config["model"],
        )

        @kiva.agent("weather", "Gets weather information")
        def get_weather(city: str) -> str:
            """Get weather for a city."""
            return f"{city}: Sunny, 25°C"

        result = None
        async for event in kiva.stream("What's the weather in Beijing?"):
            if event.type == EventType.SYNTHESIS_COMPLETE:
                result = event.data.get("result", "")

        assert result is not None
        print(f"\nSingle Function Agent Result: {result}")

    @pytest.mark.asyncio
    async def test_kiva_class_agent_multi_tools(self, api_config):
        """Test Kiva with a class decorated as multi-tool agent."""
        kiva = Kiva(
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model=api_config["model"],
        )

        @kiva.agent("math", "Mathematical operations")
        class MathTools:
            def add(self, a: int, b: int) -> int:
                """Add two numbers."""
                return a + b

            def multiply(self, a: int, b: int) -> int:
                """Multiply two numbers."""
                return a * b

        result = None
        async for event in kiva.stream("Calculate 5 + 3"):
            if event.type == EventType.SYNTHESIS_COMPLETE:
                result = event.data.get("result", "")

        assert result is not None
        print(f"\nClass Agent Result: {result}")

    @pytest.mark.asyncio
    async def test_kiva_multiple_agents(self, api_config):
        """Test Kiva with multiple agents."""
        kiva = Kiva(
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model=api_config["model"],
        )

        @kiva.agent("weather", "Gets weather information")
        def get_weather(city: str) -> str:
            """Get weather for a city."""
            return f"{city}: Sunny, 25°C"

        @kiva.agent("calculator", "Performs calculations")
        def calculate(expression: str) -> str:
            """Calculate expression."""
            try:
                return str(eval(expression))
            except Exception as e:
                return f"Error: {e}"

        result = None
        async for event in kiva.stream("What's the weather in Tokyo? Also calculate 20 * 5"):
            if event.type == EventType.SYNTHESIS_COMPLETE:
                result = event.data.get("result", "")

        assert result is not None
        print(f"\nMultiple Agents Result: {result}")

    @pytest.mark.asyncio
    async def test_kiva_add_agent_method(self, api_config):
        """Test Kiva.add_agent() method for programmatic registration."""
        kiva = Kiva(
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model=api_config["model"],
        )

        def search(query: str) -> str:
            """Search for information."""
            return f"Results for: {query}"

        kiva.add_agent("search", "Searches for information", [search])

        result = None
        async for event in kiva.stream("Search for Python tutorials"):
            if event.type == EventType.SYNTHESIS_COMPLETE:
                result = event.data.get("result", "")

        assert result is not None
        print(f"\nAdd Agent Method Result: {result}")

    def test_kiva_method_chaining(self, api_config):
        """Test method chaining with add_agent."""
        kiva = Kiva(
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model=api_config["model"],
        )

        def weather(city: str) -> str:
            """Get weather."""
            return f"{city}: Clear"

        def calc(expr: str) -> str:
            """Calculate."""
            return str(eval(expr))

        # Method chaining
        kiva.add_agent("weather", "Weather info", [weather]).add_agent(
            "calc", "Calculator", [calc]
        )

        assert len(kiva._agents) == 2
        print("\nMethod Chaining works correctly")

    @pytest.mark.asyncio
    async def test_kiva_temperature_setting(self, api_config):
        """Test Kiva with custom temperature."""
        kiva = Kiva(
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model=api_config["model"],
            temperature=0.1,  # Low temperature for more deterministic output
        )

        @kiva.agent("echo", "Echoes input")
        def echo(text: str) -> str:
            """Echo the text."""
            return f"Echo: {text}"

        result = None
        async for event in kiva.stream("Say hello"):
            if event.type == EventType.SYNTHESIS_COMPLETE:
                result = event.data.get("result", "")

        assert result is not None
        print(f"\nLow Temperature Result: {result}")

    @pytest.mark.asyncio
    async def test_kiva_empty_response_handling(self, api_config):
        """Test Kiva handles edge cases gracefully."""
        kiva = Kiva(
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model=api_config["model"],
        )

        @kiva.agent("simple", "Simple agent")
        def simple_func(input: str) -> str:
            """Simple function."""
            return input or "No input provided"

        result = None
        async for event in kiva.stream("Process this"):
            if event.type == EventType.SYNTHESIS_COMPLETE:
                result = event.data.get("result", "")

        # Should not crash, result can be None or a string
        print(f"\nEdge Case Result: {result}")
