# SSE (Server-Sent Events) Integration Guide

This guide shows how to integrate Kiva SDK's streaming API with web frameworks using Server-Sent Events (SSE).

## Overview

Kiva SDK provides built-in SSE support through the `StreamEvent.to_sse()` method, making it easy to stream events to web clients in real-time.

## SSE Format

Each event is formatted as:

```
event: {event_type}
id: {event_id}
data: {json_payload}

```

Example output:

```
event: execution_start
id: 550e8400-e29b-41d4-a716-446655440000
data: {"event_id":"550e8400-e29b-41d4-a716-446655440000","type":"execution_start","data":{"prompt":"What's the weather?"}}

event: agent_start
id: 550e8400-e29b-41d4-a716-446655440001
data: {"event_id":"550e8400-e29b-41d4-a716-446655440001","type":"agent_start","data":{"agent_id":"weather"}}

```

## FastAPI Integration

### Basic SSE Endpoint

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from kiva import Kiva

app = FastAPI()

kiva = Kiva(
    base_url="https://api.openai.com/v1",
    api_key="your-api-key",
    model="gpt-4o",
)

@kiva.agent("weather", "Gets weather information")
def get_weather(city: str) -> str:
    return f"Sunny, 25°C in {city}"


async def event_generator(prompt: str):
    """Generate SSE events from Kiva stream."""
    async for event in kiva.stream(prompt):
        yield event.to_sse()


@app.get("/stream")
async def stream_events(prompt: str):
    """SSE endpoint for streaming agent events."""
    return StreamingResponse(
        event_generator(prompt),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
```

### With Event Filtering

```python
from kiva.events import EventType

async def filtered_event_generator(prompt: str):
    """Generate SSE events, filtering out token events."""
    event_filter = {
        EventType.EXECUTION_START,
        EventType.AGENT_START,
        EventType.AGENT_END,
        EventType.EXECUTION_END,
    }
    async for event in kiva.stream(prompt, event_filter=event_filter):
        yield event.to_sse()


@app.get("/stream/filtered")
async def stream_filtered(prompt: str):
    """SSE endpoint with filtered events (no token streaming)."""
    return StreamingResponse(
        filtered_event_generator(prompt),
        media_type="text/event-stream",
    )
```

### Complete Example with Error Handling

```python
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from kiva import Kiva
from kiva.events import EventType
import logging

app = FastAPI()
logger = logging.getLogger(__name__)

kiva = Kiva(
    base_url="https://api.openai.com/v1",
    api_key="your-api-key",
    model="gpt-4o",
)

@kiva.agent("weather", "Gets weather information")
def get_weather(city: str) -> str:
    return f"Sunny, 25°C in {city}"

@kiva.agent("calculator", "Performs calculations")
def calculate(expression: str) -> str:
    return str(eval(expression))


async def sse_generator(prompt: str):
    """Generate SSE events with error handling."""
    try:
        async for event in kiva.stream(prompt):
            yield event.to_sse()
            
            # Send keepalive comment every 15 seconds if needed
            # yield ": keepalive\n\n"
            
    except Exception as e:
        logger.error(f"Stream error: {e}")
        # Send error event to client
        error_data = {"error": str(e), "type": "stream_error"}
        yield f"event: error\ndata: {error_data}\n\n"


@app.get("/api/chat/stream")
async def chat_stream(prompt: str):
    """
    Stream chat responses as SSE events.
    
    Usage:
        curl -N "http://localhost:8000/api/chat/stream?prompt=What's%20the%20weather%20in%20Tokyo?"
    """
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")
    
    return StreamingResponse(
        sse_generator(prompt),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

## Starlette Integration

```python
from starlette.applications import Starlette
from starlette.responses import StreamingResponse
from starlette.routing import Route
from kiva import Kiva

kiva = Kiva(base_url="...", api_key="...", model="gpt-4o")

@kiva.agent("weather", "Gets weather")
def get_weather(city: str) -> str:
    return f"Sunny in {city}"


async def sse_endpoint(request):
    prompt = request.query_params.get("prompt", "")
    
    async def generate():
        async for event in kiva.stream(prompt):
            yield event.to_sse()
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
    )


app = Starlette(routes=[
    Route("/stream", sse_endpoint),
])
```

## Client-Side JavaScript

### Using EventSource API

```javascript
const eventSource = new EventSource('/api/chat/stream?prompt=Hello');

eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Event:', data.type, data.data);
};

eventSource.addEventListener('agent_start', (event) => {
    const data = JSON.parse(event.data);
    console.log('Agent started:', data.data.agent_id);
});

eventSource.addEventListener('agent_end', (event) => {
    const data = JSON.parse(event.data);
    console.log('Agent result:', data.data.result);
});

eventSource.addEventListener('execution_end', (event) => {
    console.log('Execution complete');
    eventSource.close();
});

eventSource.onerror = (error) => {
    console.error('SSE Error:', error);
    eventSource.close();
};
```

### Using Fetch API (for more control)

```javascript
async function streamChat(prompt) {
    const response = await fetch(`/api/chat/stream?prompt=${encodeURIComponent(prompt)}`);
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    
    let buffer = '';
    
    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        
        // Parse SSE events from buffer
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        
        let eventType = '';
        let eventData = '';
        
        for (const line of lines) {
            if (line.startsWith('event: ')) {
                eventType = line.slice(7);
            } else if (line.startsWith('data: ')) {
                eventData = line.slice(6);
            } else if (line === '' && eventData) {
                // End of event
                const data = JSON.parse(eventData);
                handleEvent(eventType, data);
                eventType = '';
                eventData = '';
            }
        }
    }
}

function handleEvent(type, data) {
    switch (type) {
        case 'token':
            // Append token to output
            document.getElementById('output').textContent += data.data.content;
            break;
        case 'agent_end':
            console.log(`Agent ${data.data.agent_id} finished`);
            break;
        case 'execution_end':
            console.log('Done!');
            break;
    }
}
```

## React Integration

```jsx
import { useEffect, useState } from 'react';

function ChatStream({ prompt }) {
    const [messages, setMessages] = useState([]);
    const [isStreaming, setIsStreaming] = useState(false);

    useEffect(() => {
        if (!prompt) return;
        
        setIsStreaming(true);
        const eventSource = new EventSource(
            `/api/chat/stream?prompt=${encodeURIComponent(prompt)}`
        );

        eventSource.addEventListener('token', (event) => {
            const data = JSON.parse(event.data);
            setMessages(prev => [...prev, { type: 'token', content: data.data.content }]);
        });

        eventSource.addEventListener('agent_end', (event) => {
            const data = JSON.parse(event.data);
            setMessages(prev => [...prev, { 
                type: 'result', 
                agent: data.data.agent_id,
                content: data.data.result 
            }]);
        });

        eventSource.addEventListener('execution_end', () => {
            setIsStreaming(false);
            eventSource.close();
        });

        eventSource.onerror = () => {
            setIsStreaming(false);
            eventSource.close();
        };

        return () => eventSource.close();
    }, [prompt]);

    return (
        <div>
            {messages.map((msg, i) => (
                <div key={i} className={msg.type}>
                    {msg.content}
                </div>
            ))}
            {isStreaming && <span className="loading">Streaming...</span>}
        </div>
    );
}
```

## Event Types Reference

| Event Type | Description | Key Data Fields |
|------------|-------------|-----------------|
| `execution_start` | Execution begins | `prompt`, `agent_count` |
| `agent_start` | Agent starts processing | `agent_id`, `task` |
| `agent_end` | Agent completes | `agent_id`, `result`, `duration_ms` |
| `token` | Streaming token | `content` |
| `execution_end` | Execution completes | `result`, `success`, `duration_ms` |
| `execution_error` | Error occurred | `error_type`, `error_message` |

See [Execution Outputs](execution-outputs.md) for complete event documentation.

## Best Practices

1. **Set appropriate headers**: Include `Cache-Control: no-cache` and `X-Accel-Buffering: no` for nginx
2. **Handle reconnection**: EventSource automatically reconnects; use `id` field for resumption
3. **Filter events**: Use `event_filter` to reduce bandwidth if you don't need all events
4. **Close connections**: Always close EventSource when done to free resources
5. **Error handling**: Listen for error events and handle connection failures gracefully
