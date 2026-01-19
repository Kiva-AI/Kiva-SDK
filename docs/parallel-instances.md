# Parallel Agent Instances

Kiva supports spawning multiple instances of the same agent definition for parallel subtask execution. This enables efficient processing of tasks that can be decomposed into independent subtasks.

## Overview

Traditional multi-agent systems allow different agents to run in parallel, but each agent definition can only have one active instance. Kiva extends this by allowing:

- Single agent definition to spawn N parallel instances
- Each instance has isolated context (scratchpad/memory)
- Planner automatically decides parallelization strategy
- Instances execute concurrently and results are aggregated

## When to Use

Parallel instances are useful when:

- A task can be split into independent subtasks
- The same capability needs to process multiple items
- You want to parallelize without defining multiple identical agents

Examples:
- "Search for information about 5 different topics" → 5 instances of search agent
- "Analyze these 3 documents" → 3 instances of analyzer agent
- "Get weather for NYC, LA, and Chicago" → 3 instances of weather agent

## How It Works

### Planner Decision

The `analyze_and_plan` node examines the user's request and decides:

1. **Complexity**: simple, medium, or complex
2. **Workflow**: router, supervisor, or parliament
3. **Parallel Strategy**: none, fan_out, or map_reduce
4. **Instance Count**: How many instances to spawn per agent

### Parallel Strategies

| Strategy | Description | Use Case |
|----------|-------------|----------|
| `none` | No parallelization, single instance | Simple direct tasks |
| `fan_out` | Spawn N instances for independent subtasks | Multiple independent queries |
| `map_reduce` | Split, process in parallel, aggregate | Data processing pipelines |

### Instance Context

Each instance receives isolated context:

```python
{
    "instance_id": "exec-abc-search-i0-xyz123",
    "agent_id": "search_agent",
    "task": "Search for Python tutorials",
    "scratchpad": [],  # Instance-specific working memory
    "memory": {},      # Instance-specific persistent data
    "created_at": 1234567890.0
}
```

## Task Assignment Format

The planner generates task assignments with instance configuration:

```python
{
    "agent_id": "search_agent",
    "task": "Search for Python tutorials",
    "instances": 3,  # Spawn 3 parallel instances
    "instance_context": {"topic": "Python"}  # Optional base context
}
```

## Events

Instance execution emits specific events for monitoring:

### Instance Lifecycle Events

| Event Type | Description | Data Fields |
|------------|-------------|-------------|
| `instance_spawn` | Instance created and starting | `instance_id`, `agent_id`, `task`, `execution_id` |
| `instance_start` | Instance beginning task execution | `instance_id`, `agent_id`, `task`, `execution_id` |
| `instance_end` | Instance completed task | `instance_id`, `agent_id`, `result`, `execution_id` |
| `instance_complete` | Instance finished (success or error) | `instance_id`, `agent_id`, `success`, `execution_id` |
| `instance_result` | Result from instance execution | `instance_id`, `agent_id`, `result`, `error`, `execution_id` |

### Batch Events

| Event Type | Description | Data Fields |
|------------|-------------|-------------|
| `parallel_instances_start` | Batch of instances starting | `instance_count`, `agent_ids`, `execution_id` |
| `parallel_instances_complete` | Batch of instances finished | `results` (list with `agent_id`, `instance_id`, `success`), `execution_id` |

### Event Flow Example

```
workflow_selected (parallel_strategy: fan_out, total_instances: 3)
  └─> parallel_instances_start (instance_count: 3)
        ├─> instance_spawn (instance_id: exec-abc-search-i0-xyz)
        │     └─> instance_start
        │           └─> instance_end (result: "...")
        │                 └─> instance_complete (success: true)
        ├─> instance_spawn (instance_id: exec-abc-search-i1-xyz)
        │     └─> instance_start
        │           └─> instance_end (result: "...")
        │                 └─> instance_complete (success: true)
        └─> instance_spawn (instance_id: exec-abc-search-i2-xyz)
              └─> instance_start
                    └─> instance_end (result: "...")
                          └─> instance_complete (success: true)
  └─> parallel_instances_complete (results: [...])
        └─> final_result
```

## Configuration

Control parallelization via the Kiva client:

```python
import asyncio
from kiva import Kiva

kiva = Kiva(base_url="...", api_key="...", model="gpt-4o")

@kiva.agent("search", "Searches for information")
def search(query: str) -> str:
    return f"Results for: {query}"

async def main():
    # Method 1: Rich console output
    result = await kiva.run("Search for 10 different topics")
    
    # Method 2: Stream events to monitor instances
    async for event in kiva.stream("Search for 10 different topics"):
        if event.type.value.startswith("instance_"):
            print(f"{event.type.value}: {event.data}")

asyncio.run(main())
```

## Example

```python
import asyncio
from kiva import Kiva

kiva = Kiva(base_url="...", api_key="...", model="gpt-4o")

@kiva.agent("researcher", "Researches topics")
def research(topic: str) -> str:
    """Research a specific topic."""
    return f"Research results for {topic}"

async def main():
    # Rich console output
    result = await kiva.run(
        "Research the following topics: AI, blockchain, quantum computing"
    )
    print(result)

asyncio.run(main())
```

## State Types

### AgentInstanceState

State for individual instance execution:

```python
class AgentInstanceState(TypedDict):
    instance_id: str      # Unique instance identifier
    agent_id: str         # Parent agent definition ID
    task: str             # Specific subtask
    context: dict         # Isolated context/scratchpad
    execution_id: str     # Parent execution ID
    model_name: str
    api_key: str | None
    base_url: str | None
```

### TaskAssignment

Task assignment with instance configuration:

```python
class TaskAssignment(TypedDict, total=False):
    agent_id: str              # Agent to use
    task: str                  # Task description
    instances: int             # Number of instances (default: 1)
    instance_context: dict     # Base context for instances
```

### PlanningResult

Result from the planning phase:

```python
class PlanningResult(TypedDict, total=False):
    complexity: str            # simple, medium, complex
    workflow: str              # router, supervisor, parliament
    reasoning: str             # Planning explanation
    task_assignments: list[TaskAssignment]
    parallel_strategy: str     # none, fan_out, map_reduce
    total_instances: int       # Total instances to spawn
```

## Best Practices

1. **Set appropriate limits**: Use `max_parallel_agents` to prevent resource exhaustion
2. **Design for independence**: Ensure subtasks don't depend on each other
3. **Handle partial failures**: Some instances may fail while others succeed
4. **Monitor instance events**: Track individual instance progress for debugging

## Rich Console Display

When using `kiva.run()`, parallel instances are displayed with:

- **Workflow Info Panel**: Shows parallel strategy and total instance count
- **Agent Instances Table**: Displays each instance with:
  - Agent ID
  - Instance ID (shortened)
  - Status: `SPAWNED` → `RUNNING` → `DONE` or `ERROR`
  - Task/Result preview

Example display:
```
┌─────────────────────────────────────────────────────────────┐
│                    Workflow Selected                         │
├─────────────────────────────────────────────────────────────┤
│ Workflow          │ SUPERVISOR                               │
│ Complexity        │ medium                                   │
│ Parallel Strategy │ FAN_OUT                                  │
│ Total Instances   │ 3                                        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                 Agent Instances Execution                    │
├──────────────┬──────────┬───────────┬───────────────────────┤
│ Agent        │ Instance │ Status    │ Task / Result         │
├──────────────┼──────────┼───────────┼───────────────────────┤
│ search_agent │ xyz12345 │ [v] DONE  │ Results for AI...     │
│ search_agent │ abc67890 │ [~] RUNNING│ Search blockchain... │
│ search_agent │ def11111 │ [+] SPAWNED│ Search quantum...    │
└──────────────┴──────────┴───────────┴───────────────────────┘
```
