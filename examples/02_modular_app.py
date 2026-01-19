"""Modular Application Example - Using AgentRouter.

Two ways to use Kiva:
1. kiva.run(prompt) - Rich console output, returns final result
2. kiva.stream(prompt) - Returns async event stream
"""

import asyncio

from kiva import AgentRouter, Kiva

API_BASE = ""
API_KEY = ""
MODEL = ""

# Weather module
weather_router = AgentRouter(prefix="weather")


@weather_router.agent("forecast", "Gets weather forecasts")
def get_forecast(city: str) -> str:
    """Get weather forecast."""
    return f"{city}: Sunny, 25°C"


# Math module
math_router = AgentRouter(prefix="math")


@math_router.agent("calculator", "Performs calculations")
class Calculator:
    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b


def create_app() -> Kiva:
    kiva = Kiva(base_url=API_BASE, api_key=API_KEY, model=MODEL)
    kiva.include_router(weather_router)
    kiva.include_router(math_router)
    return kiva


async def main():
    app = create_app()

    # Method 1: Rich console output
    result = await app.run("What's the weather in Beijing?")
    print(f"Result: {result}")

    # Method 2: Stream events
    async for event in app.stream("Calculate 15 + 8"):
        print(f"Event: {event.type.value}")


if __name__ == "__main__":
    asyncio.run(main())
