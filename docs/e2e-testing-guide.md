# E2E Testing Guide for Kiva SDK

This guide explains how to run, understand, and extend the end-to-end tests for the Kiva SDK.

## Running Tests
 
 ### Run All E2E Tests
 
```bash
 uv run --dev pytest tests/e2e/ -v
```
 
 ### Run Specific Test File
 
```bash
 uv run --dev pytest tests/e2e/test_e2e_router_workflow.py -v
```
 
 ### Run Specific Test
 
```bash
 uv run --dev pytest tests/e2e/test_e2e_router_workflow.py::TestRouterWorkflowE2E::test_router_simple_weather_query -v
```
 
 ### Run with Output Capture
 
```bash
 uv run --dev pytest tests/e2e/test_e2e_output_capture.py -v -s
```
 
 ### Run with Coverage
 
```bash
 uv run --dev pytest tests/e2e/ --cov=src/kiva --cov-report=html
```

## Test Configuration

All E2E tests use environment variables for API configuration:

```bash
# Set environment variables
export KIVA_API_BASE="http://your-api-endpoint/v1"
export KIVA_API_KEY="your-api-key"
export KIVA_MODEL="your-model-name"

# Run tests
uv run --dev pytest tests/e2e/ -v
```

**Environment Variables:**
- `KIVA_API_BASE`: API endpoint URL (default: `http://localhost:8000/v1`)
- `KIVA_API_KEY`: API authentication key (default: empty)
- `KIVA_MODEL`: Model identifier (default: `gpt-4o`)

## Understanding Test Output

### Successful Test

```
tests/e2e/test_e2e_router_workflow.py::TestRouterWorkflowE2E::test_router_simple_weather_query PASSED [20%]

Event: workflow_selected - {'workflow': 'router', 'complexity': 'simple', ...}
Event: agent_start - {'agent_id': 'weather_agent', ...}
Event: agent_end - {'agent_id': 'weather_agent', 'result': '...'}
Event: final_result - {'result': 'The current weather in Beijing is sunny...'}

Final Result: The current weather in Beijing is sunny with a temperature of 25°C and a humidity of 45%.
```

### Failed Test

```
tests/e2e/test_e2e_error_handling.py::TestErrorHandlingE2E::test_empty_agents_raises_error FAILED

AssertionError: Expected ConfigurationError but got None
```

## Test Categories Explained

### 1. Workflow Tests

Test the three core workflow patterns:

- **Router**: Single agent handles the task
- **Supervisor**: Multiple agents work in parallel
- **Parliament**: Iterative conflict resolution

**Key Validations:**
- Correct workflow selection
- Event sequence ordering
- Result synthesis
- Error handling

### 2. API Level Tests

Test different API interfaces:

- **High-Level (Kiva)**: Decorator-based agent registration
- **Low-Level (run)**: Event streaming with full control
- **AgentRouter**: Modular multi-file organization

**Key Validations:**
- API consistency
- Event structure
- Return values
- Method chaining

### 3. Feature Tests

Test advanced features:

- **Parallel Instances**: Multiple instances of same agent
- **Console Output**: Rich terminal visualization

**Key Validations:**
- Instance isolation
- Event emission
- Display rendering
- Result aggregation

### 4. Quality Tests

Test error handling and consistency:

- **Error Handling**: Boundary conditions and edge cases
- **Consistency**: API behavior across interfaces
- **Validation**: Output pattern verification

**Key Validations:**
- Error messages
- Graceful degradation
- Consistent behavior
- Pattern compliance

## Common Test Patterns

### Basic Test Structure

```python
@pytest.mark.asyncio
async def test_scenario_name(self, api_config):
    """Test description."""
    from kiva import Kiva
    
    kiva = Kiva(
        base_url=api_config["base_url"],
        api_key=api_config["api_key"],
        model=api_config["model"],
    )
    
    @kiva.agent("weather", "Gets weather")
    def get_weather(city: str) -> str:
        return f"{city}: Sunny"
    
    # Method 1: Rich console output
    result = await kiva.run("Test prompt")
    assert result is not None
    
    # Method 2: Stream events
    async for event in kiva.stream("Test prompt"):
        print(f"Event: {event.type.value}")
```

### Event Validation Pattern

```python
import asyncio
from kiva import Kiva

kiva = Kiva(base_url="...", api_key="...", model="gpt-4o")

@kiva.agent("weather", "Gets weather")
def get_weather(city: str) -> str:
    return f"{city}: Sunny"

async def main():
    # Method 1: Rich console output
    result = await kiva.run("What's the weather?")
    assert result is not None
    
    # Method 2: Stream events
    events = []
    async for event in kiva.stream("What's the weather?"):
        events.append(event)
    assert any(e.type.value == "execution_end" for e in events)

asyncio.run(main())
```

### Error Testing Pattern

```python
from kiva import Kiva, ConfigurationError

# Test that empty agents raises error
kiva = Kiva(base_url="...", api_key="...", model="gpt-4o")
# No agents registered - will raise error when run
```

## Extending Tests

### Adding a New Test

1. **Create test file** (if needed):
```bash
touch tests/e2e/test_e2e_new_feature.py
```

2. **Import required modules**:
```python
import pytest
from kiva import Kiva

class TestNewFeatureE2E:
    """E2E tests for new feature."""
```

3. **Write test method**:
```python
@pytest.mark.asyncio
async def test_new_scenario(self, api_config, create_weather_agent):
    """Test new scenario."""
    # Test implementation
    pass
```

4. **Use shared fixtures**:
```python
# Available fixtures from conftest.py
- api_config
- create_model
- weather_tool, calculate_tool, search_tool, translate_tool
- create_weather_agent, create_calculator_agent, etc.
```

5. **Add assertions**:
```python
# Verify behavior
assert result is not None
assert "expected_value" in result
```

6. **Update documentation**:
- Add to `tests/e2e/README.md`
- Update `docs/testing-summary.md`

### Adding a New Fixture

In `tests/e2e/conftest.py`:

```python
@pytest.fixture
def create_new_agent(create_model, new_tool):
    """Factory to create a new agent."""
    def _create():
        agent = create_agent(model=create_model(), tools=[new_tool])
        agent.name = "new_agent"
        agent.description = "Description"
        return agent
    return _create
```

## Troubleshooting

### Tests Timeout

**Problem:** Tests hang or timeout

**Solutions:**
1. Check API endpoint is accessible:
   ```bash
   curl $KIVA_API_BASE/models
   ```

2. Verify API key is valid

3. Check network connection

4. Increase timeout:
   ```python
   @pytest.mark.timeout(120)  # 2 minutes
   async def test_long_running():
       pass
   ```

### Tests Fail Intermittently

**Problem:** Tests pass sometimes, fail other times

**Solutions:**
1. LLM responses vary - adjust assertions to be more flexible
2. Check for race conditions in parallel tests
3. Add retry logic for flaky tests:
   ```python
   @pytest.mark.flaky(reruns=3)
   async def test_flaky():
       pass
   ```

### Import Errors

**Problem:** Cannot import kiva modules

**Solutions:**
1. Install in development mode:
   ```bash
   pip install -e .
   ```

2. Check Python path:
   ```bash
   export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
   ```

### API Errors

**Problem:** API returns errors

**Solutions:**
1. Check API status
2. Verify model name is correct
3. Check rate limits
4. Review API logs

## Best Practices

### 1. Test Independence

Each test should be independent:

```python
# ✅ Good - creates own agents
async def test_scenario(self, create_weather_agent):
    agents = [create_weather_agent()]
    # test code

# ❌ Bad - shares state
agents = [weather_agent]  # module level
async def test_scenario(self):
    # uses shared agents
```

### 2. Clear Assertions

Use descriptive assertion messages:

```python
# ✅ Good
assert "workflow_selected" in event_types, \
    f"Missing workflow_selected event. Got: {event_types}"

# ❌ Bad
assert "workflow_selected" in event_types
```

### 3. Meaningful Output

Print useful debugging information:

```python
print(f"\nEvent types: {event_types}")
print(f"Final result: {final_event.data['result']}")
```

### 4. Use Fixtures

Leverage shared fixtures:

```python
# ✅ Good - uses fixture
async def test_scenario(self, api_config, create_weather_agent):
    agents = [create_weather_agent()]

# ❌ Bad - duplicates setup
async def test_scenario(self):
    model = ChatOpenAI(...)
    agent = create_agent(...)
```

### 5. Test One Thing

Each test should focus on one behavior:

```python
# ✅ Good - tests one thing
async def test_router_selects_correct_workflow(self):
    # test workflow selection

async def test_router_executes_single_agent(self):
    # test agent execution

# ❌ Bad - tests multiple things
async def test_router_everything(self):
    # tests workflow selection, execution, and results
```

## Performance Considerations

### Test Duration

- **Unit tests:** < 1 second
- **E2E tests:** 2-5 seconds
- **Full suite:** ~5 minutes

### Optimization Tips
 
 1. **Run in parallel** (if API supports):
    ```bash
    uv run --dev pytest tests/e2e/ -n 4  # 4 workers
    ```
 
 2. **Skip slow tests** during development:
    ```python
    @pytest.mark.slow
    async def test_slow_scenario():
        pass
    
    # Run: uv run --dev pytest -m "not slow"
    ```
 
 3. **Use markers** for selective testing:
    ```python
    @pytest.mark.workflow
    async def test_workflow():
        pass
    
    # Run: uv run --dev pytest -m workflow
    ```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  e2e-tests:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Install uv
      uses: astral-sh/setup-uv@v7
    
    - name: Install Python 3.12
      run: uv python install 3.12
    
    - name: Install dependencies
      run: uv sync --dev
    
    - name: Run E2E tests
      run: uv run --dev pytest tests/e2e/ -v --tb=short
      env:
        API_BASE: ${{ secrets.API_BASE }}
        API_KEY: ${{ secrets.API_KEY }}
```

## Documentation

### Generated Documentation

Tests automatically generate documentation:

1. **Execution Outputs** (`docs/execution-outputs.md`)
   - Real execution traces
   - Event sequences
   - Code examples

2. **Captured Data** (`docs/outputs/*.json`)
   - Complete event logs
   - Timing information
   - Full data payloads

### Regenerating Documentation
 
 ```bash
 # Run output capture tests
 uv run --dev pytest tests/e2e/test_e2e_output_capture.py -v -s
 
 # Check generated files
 ls -la docs/outputs/
 ```

## Resources

- **Test Files:** `tests/e2e/`
- **Fixtures:** `tests/e2e/conftest.py`
- **Documentation:** `docs/execution-outputs.md`
- **Summary:** `docs/testing-summary.md`
- **README:** `tests/e2e/README.md`

## Support

For issues or questions:

1. Check test output for error messages
2. Review `docs/execution-outputs.md` for expected patterns
3. Check API endpoint status
4. Review test logs
5. Open an issue with test output

## Conclusion

The E2E test suite provides comprehensive coverage of all Kiva SDK features. By following this guide, you can run, understand, and extend the tests to ensure the SDK works correctly in real-world scenarios.

**Happy Testing! 🧪**
