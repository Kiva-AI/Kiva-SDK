import os
import uvicorn

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from kiva import Kiva

API_BASE = ""
API_KEY = ""
MODEL = ""

app = FastAPI()

kiva = Kiva(
    base_url=API_BASE,
    api_key=API_KEY,
    model=MODEL,
)


@kiva.agent("weather", "Gets weather information")
def get_weather(city: str) -> str:
    """Return weather summary for a city."""
    return f"Sunny, 25°C in {city}"


async def event_generator(prompt: str):
    import asyncio
    stream = kiva.stream(prompt)
    it = stream.__aiter__()
    keepalive_interval = 15
    while True:
        try:
            next_item = asyncio.create_task(it.__anext__())
            done, _ = await asyncio.wait({next_item}, timeout=keepalive_interval)
            if next_item in done:
                event = next_item.result()
                yield event.to_sse()
            else:
                yield ": keepalive\n\n"
                continue
        except StopAsyncIteration:
            break


@app.get("/stream")
async def stream_events(prompt: str):
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")
    return StreamingResponse(
        event_generator(prompt),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
