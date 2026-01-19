# Kiva SDK

> ⚠️ **Important Notice**: This project is currently in a rapid iteration/experimental phase, and the provided API may undergo disruptive changes at any time.

A multi-agent orchestration SDK for building intelligent workflows.

## Features

- **Three Workflow Patterns**: Router (simple), Supervisor (parallel), Parliament (deliberative)
- **Automatic Complexity Analysis**: Intelligent workflow selection
- **Parallel Agent Instances**: Spawn multiple instances for parallel execution
- **Modular Architecture**: AgentRouter for organizing agents
- **Rich Console Output**: Beautiful terminal visualization
- **Streaming Events**: Real-time event stream for custom handling

## Installation

```bash
uv add kiva-sdk
```

## Quick Start

```python
import asyncio
from kiva import Kiva

kiva = Kiva(
    base_url="https://api.openai.com/v1",
    api_key="your-api-key",
    model="gpt-4o",
)

@kiva.agent("weather", "Gets weather information")
def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"Sunny, 25°C in {city}"

@kiva.agent("math", "Performs calculations")
class MathTools:
    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

async def main():
    # Method 1: Rich console output
    result = await kiva.run("What's the weather in Tokyo?")
    print(result)

    # Method 2: Stream events for custom handling
    async for event in kiva.stream("Calculate 15 + 8"):
        print(f"{event.type.value}: {event.data}")

asyncio.run(main())
```

## API

### `kiva.run(prompt)` - Rich Console Output

Returns final result with beautiful terminal visualization.

```python
result = await kiva.run("Your prompt here")
```

### `kiva.stream(prompt)` - Event Stream

Returns async iterator of `StreamEvent` objects for custom handling.

```python
async for event in kiva.stream("Your prompt here"):
    if event.type.value == "agent_end":
        print(f"Agent {event.data['agent_id']} finished")
```

### Streaming Output Formats

StreamEvent supports multiple output formats for different use cases:

```python
async for event in kiva.stream("Your prompt"):
    # SSE format for web frontends
    sse_string = event.to_sse()
    # Output: "event: agent_end\nid: {uuid}\ndata: {json}\n\n"
    
    # NDJSON format for CLI tools and logging
    ndjson_string = event.to_ndjson()
    # Output: "{json}\n"
    
    # JSON string
    json_string = event.to_json()
    
    # Dictionary
    event_dict = event.to_dict()
```

### Event Filtering

Filter events at the source to reduce overhead:

```python
from kiva.events import EventType

# Only receive specific event types
event_filter = {EventType.AGENT_START, EventType.AGENT_END}
async for event in kiva.stream("Your prompt", event_filter=event_filter):
    print(event.type.value)
```

## Modular Application with AgentRouter

```python
from kiva import AgentRouter, Kiva

# agents/weather.py
weather_router = AgentRouter(prefix="weather")

@weather_router.agent("forecast", "Gets forecasts")
def get_forecast(city: str) -> str:
    return f"Sunny in {city}"

# main.py
kiva = Kiva(base_url="...", api_key="...", model="gpt-4o")
kiva.include_router(weather_router)

await kiva.run("What's the weather?")
```

## Documentation

- [AgentRouter - Modular Applications](docs/agent-router.md)
- [Parallel Agent Instances](docs/parallel-instances.md)
- [SSE Integration Guide](docs/sse-integration.md)
- [NDJSON Streaming Guide](docs/ndjson-streaming.md)
- [Execution Outputs](docs/execution-outputs.md)
- [E2E Testing Guide](docs/e2e-testing-guide.md)

## Event Types Reference

| Event Type | Description |
|------------|-------------|
| `execution_start` | Execution begins |
| `agent_start` | Agent starts processing |
| `agent_end` | Agent completes with result |
| `token` | Streaming token from LLM |
| `execution_end` | Execution completes |
| `execution_error` | Error occurred |

See [Execution Outputs](docs/execution-outputs.md) for complete event documentation.

## License

MIT License
