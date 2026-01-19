# NDJSON (Newline Delimited JSON) Streaming Guide

This guide shows how to use Kiva SDK's NDJSON streaming format for incremental event processing.

## Overview

NDJSON (Newline Delimited JSON) is a format where each line is a valid JSON object, making it ideal for streaming data processing. Kiva SDK provides built-in NDJSON support through the `StreamEvent.to_ndjson()` method.

## NDJSON Format

Each event is a single-line JSON object followed by a newline:

```
{"event_id":"...","type":"execution_start","data":{"prompt":"What's the weather?"},"timestamp":1234567890.123}
{"event_id":"...","type":"agent_start","data":{"agent_id":"weather"},"timestamp":1234567890.124}
{"event_id":"...","type":"agent_end","data":{"agent_id":"weather","result":"Sunny, 25°C"},"timestamp":1234567890.500}
{"event_id":"...","type":"execution_end","data":{"success":true},"timestamp":1234567890.501}
```

## Basic Usage

### Streaming to Console

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
    return f"Sunny, 25°C in {city}"


async def main():
    async for event in kiva.stream("What's the weather in Tokyo?"):
        print(event.to_ndjson(), end="")  # Already includes newline


asyncio.run(main())
```

### Writing to File

```python
async def stream_to_file(prompt: str, output_path: str):
    """Stream events to an NDJSON file."""
    with open(output_path, "w") as f:
        async for event in kiva.stream(prompt):
            f.write(event.to_ndjson())
            f.flush()  # Ensure immediate write


# Usage
await stream_to_file("Calculate 15 + 8", "events.ndjson")
```

### Reading NDJSON File

```python
from kiva.events import StreamEvent

def read_ndjson_events(file_path: str):
    """Read events from an NDJSON file."""
    events = []
    with open(file_path, "r") as f:
        for line in f:
            if line.strip():
                event = StreamEvent.from_json(line)
                events.append(event)
    return events


# Usage
events = read_ndjson_events("events.ndjson")
for event in events:
    print(f"{event.type.value}: {event.data}")
```

## FastAPI NDJSON Endpoint

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from kiva import Kiva

app = FastAPI()

kiva = Kiva(base_url="...", api_key="...", model="gpt-4o")

@kiva.agent("weather", "Gets weather")
def get_weather(city: str) -> str:
    return f"Sunny in {city}"


async def ndjson_generator(prompt: str):
    """Generate NDJSON events from Kiva stream."""
    async for event in kiva.stream(prompt):
        yield event.to_ndjson()


@app.get("/stream/ndjson")
async def stream_ndjson(prompt: str):
    """NDJSON streaming endpoint."""
    return StreamingResponse(
        ndjson_generator(prompt),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
```

## Processing NDJSON Streams

### Python Client

```python
import httpx

async def consume_ndjson_stream(url: str):
    """Consume NDJSON stream from HTTP endpoint."""
    async with httpx.AsyncClient() as client:
        async with client.stream("GET", url) as response:
            async for line in response.aiter_lines():
                if line:
                    event = StreamEvent.from_json(line)
                    process_event(event)


def process_event(event):
    """Process a single event."""
    if event.type.value == "agent_end":
        print(f"Agent {event.data['agent_id']}: {event.data['result']}")
    elif event.type.value == "execution_end":
        print(f"Done in {event.data['duration_ms']}ms")
```

### Node.js Client

```javascript
const readline = require('readline');
const https = require('https');

function consumeNdjsonStream(url) {
    return new Promise((resolve, reject) => {
        https.get(url, (response) => {
            const rl = readline.createInterface({
                input: response,
                crlfDelay: Infinity
            });

            const events = [];
            
            rl.on('line', (line) => {
                if (line.trim()) {
                    const event = JSON.parse(line);
                    events.push(event);
                    console.log(`${event.type}: ${JSON.stringify(event.data)}`);
                }
            });

            rl.on('close', () => resolve(events));
            rl.on('error', reject);
        });
    });
}
```

### Using jq for Command Line Processing

```bash
# Stream and filter events
curl -N "http://localhost:8000/stream/ndjson?prompt=Hello" | \
    jq -c 'select(.type == "agent_end")'

# Extract just the results
curl -N "http://localhost:8000/stream/ndjson?prompt=Hello" | \
    jq -r 'select(.type == "agent_end") | .data.result'

# Count events by type
curl "http://localhost:8000/stream/ndjson?prompt=Hello" | \
    jq -s 'group_by(.type) | map({type: .[0].type, count: length})'
```

## Event Filtering

Filter events at the source to reduce data transfer:

```python
from kiva.events import EventType

async def filtered_ndjson_stream(prompt: str):
    """Stream only key events as NDJSON."""
    event_filter = {
        EventType.EXECUTION_START,
        EventType.AGENT_START,
        EventType.AGENT_END,
        EventType.EXECUTION_END,
    }
    
    async for event in kiva.stream(prompt, event_filter=event_filter):
        yield event.to_ndjson()
```

## Batch Processing

Process NDJSON events in batches for efficiency:

```python
async def batch_process_events(prompt: str, batch_size: int = 10):
    """Process events in batches."""
    batch = []
    
    async for event in kiva.stream(prompt):
        batch.append(event)
        
        if len(batch) >= batch_size:
            await process_batch(batch)
            batch = []
    
    # Process remaining events
    if batch:
        await process_batch(batch)


async def process_batch(events):
    """Process a batch of events."""
    for event in events:
        # Your processing logic
        pass
```

## Logging and Debugging

Use NDJSON for structured logging:

```python
import sys

async def stream_with_logging(prompt: str):
    """Stream events with NDJSON logging to stderr."""
    async for event in kiva.stream(prompt):
        # Log to stderr in NDJSON format
        sys.stderr.write(event.to_ndjson())
        
        # Process event
        if event.type.value == "agent_end":
            yield event.data["result"]
```

## Comparison: SSE vs NDJSON

| Feature | SSE | NDJSON |
|---------|-----|--------|
| Browser support | Native EventSource API | Requires manual parsing |
| Event types | Built-in event field | Part of JSON payload |
| Reconnection | Automatic with `id` | Manual implementation |
| Parsing | Requires SSE parser | Simple line-by-line JSON |
| File storage | Needs conversion | Direct storage |
| CLI tools | Limited | Works with jq, grep |

**Use SSE when**: Building web frontends with browser EventSource API

**Use NDJSON when**: Building CLI tools, logging, file storage, or non-browser clients

## Best Practices

1. **Flush buffers**: Call `flush()` when writing to files for real-time output
2. **Handle partial lines**: Buffer incomplete lines when reading streams
3. **Validate JSON**: Wrap `json.loads()` in try/except for robustness
4. **Use streaming HTTP clients**: Use `httpx` or `aiohttp` with streaming support
5. **Filter at source**: Use `event_filter` to reduce bandwidth
