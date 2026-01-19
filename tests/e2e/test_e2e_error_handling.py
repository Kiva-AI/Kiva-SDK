"""E2E test for Error Handling.

Tests error handling, edge cases, and boundary conditions.
"""

import pytest

from kiva import Kiva
from kiva.events import EventType


class TestErrorHandlingE2E:
    """E2E tests for error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_kiva_no_agents_registered(self, api_config):
        """Test Kiva with no agents registered."""
        kiva = Kiva(
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model=api_config["model"],
        )

        # Running without any agents should raise an error
        with pytest.raises(Exception):
            async for _ in kiva.stream("Test prompt"):
                pass

        print("\nNo agents error handled correctly")

    @pytest.mark.asyncio
    async def test_empty_prompt_handling(self, api_config, weather_func):
        """Test handling of empty or whitespace prompt."""
        kiva = Kiva(
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model=api_config["model"],
        )

        @kiva.agent("weather", "Gets weather information")
        def get_weather(city: str) -> str:
            """Get weather for a city."""
            return weather_func(city)

        # Empty prompt should still work (LLM will handle it)
        result = None
        async for event in kiva.stream(""):
            if event.type == EventType.SYNTHESIS_COMPLETE:
                result = event.data.get("result", "")
        print(f"\nEmpty prompt result: {result}")

    @pytest.mark.asyncio
    async def test_very_long_prompt(self, api_config, weather_func):
        """Test handling of very long prompts."""
        kiva = Kiva(
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model=api_config["model"],
        )

        @kiva.agent("weather", "Gets weather information")
        def get_weather(city: str) -> str:
            """Get weather for a city."""
            return weather_func(city)

        # Create a long prompt
        long_prompt = "What's the weather? " * 100

        result = None
        async for event in kiva.stream(long_prompt):
            if event.type == EventType.SYNTHESIS_COMPLETE:
                result = event.data.get("result", "")

        assert result is not None
        print("\nLong prompt handled successfully")

    @pytest.mark.asyncio
    async def test_special_characters_in_prompt(self, api_config, weather_func):
        """Test handling of special characters in prompt."""
        kiva = Kiva(
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model=api_config["model"],
        )

        @kiva.agent("weather", "Gets weather information")
        def get_weather(city: str) -> str:
            """Get weather for a city."""
            return weather_func(city)

        special_prompt = "Weather in 北京? <script>alert('test')</script> 🌤️"

        result = None
        async for event in kiva.stream(special_prompt):
            if event.type == EventType.SYNTHESIS_COMPLETE:
                result = event.data.get("result", "")

        assert result is not None
        print("\nSpecial characters handled successfully")

    @pytest.mark.asyncio
    async def test_unicode_agent_names(self, api_config):
        """Test handling of unicode in agent names."""
        kiva = Kiva(
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model=api_config["model"],
        )

        @kiva.agent("天气助手", "获取天气信息")
        def weather(city: str) -> str:
            """Get weather."""
            return f"{city}: 晴天"

        result = None
        async for event in kiva.stream("北京天气如何？"):
            if event.type == EventType.SYNTHESIS_COMPLETE:
                result = event.data.get("result", "")
        print(f"\nUnicode agent result: {result}")

    @pytest.mark.asyncio
    async def test_agent_with_failing_tool(self, api_config):
        """Test handling of agent execution errors."""
        kiva = Kiva(
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model=api_config["model"],
        )

        @kiva.agent("failing", "An agent that might fail")
        def failing_tool(input: str) -> str:
            """A tool that always fails."""
            raise RuntimeError("Tool execution failed!")

        # Should handle gracefully
        try:
            result = None
            async for event in kiva.stream("Use the failing tool"):
                if event.type == EventType.SYNTHESIS_COMPLETE:
                    result = event.data.get("result", "")
            print(f"\nFailing tool result: {result}")
        except Exception as e:
            print(f"\nFailing tool error handled: {e}")

    @pytest.mark.asyncio
    async def test_multiple_agents_partial_failure(self, api_config, weather_func):
        """Test handling when some agents fail but others succeed."""
        kiva = Kiva(
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model=api_config["model"],
        )

        @kiva.agent("weather", "Gets weather information")
        def get_weather(city: str) -> str:
            """Get weather for a city."""
            return weather_func(city)

        @kiva.agent("unreliable", "An unreliable agent")
        def unreliable_tool(input: str) -> str:
            """An unreliable tool."""
            if "fail" in input.lower():
                raise RuntimeError("Intentional failure")
            return f"Success: {input}"

        result = None
        async for event in kiva.stream("Get weather in Beijing and process some data"):
            if event.type == EventType.SYNTHESIS_COMPLETE:
                result = event.data.get("result", "")

        # Should complete with partial results
        print(f"\nPartial failure result: {result}")

    def test_class_agent_with_no_methods(self, api_config):
        """Test class agent with no public methods."""
        kiva = Kiva(
            base_url=api_config["base_url"],
            api_key=api_config["api_key"],
            model=api_config["model"],
        )

        @kiva.agent("empty", "An empty agent")
        class EmptyAgent:
            def _private_method(self) -> str:
                """Private method."""
                return "private"

        # Should handle gracefully (no tools)
        assert len(kiva._agents) == 1
        print("\nEmpty agent registered (no public methods)")
