"""High-Level API Example.

Two ways to use Kiva:
1. kiva.run(prompt) - Rich console output, returns final result
2. kiva.stream(prompt) - Returns async event stream
"""

import asyncio

from kiva import Kiva

API_BASE = ""
API_KEY = ""
MODEL = ""

kiva = Kiva(base_url=API_BASE, api_key=API_KEY, model=MODEL)


@kiva.agent("weather", "Gets weather information")
def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"{city}: Sunny, 25°C"


@kiva.agent("math", "Performs calculations")
class MathTools:
    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b


async def main():
    # Method 1: Rich console output
    await kiva.run("What's the weather in Beijing?")
    #print(f"Result: {result}")

    # Method 2: Stream events
    # async for event in kiva.stream("What is 2 + 2?"):
    #     print(f"Event: {event.type.value}")


if __name__ == "__main__":
    asyncio.run(main())
