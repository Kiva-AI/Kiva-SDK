# AgentRouter - 模块化多文件应用

`AgentRouter` 是 Kiva SDK 提供的模块化路由器，灵感来自 FastAPI 的 `APIRouter`，让你能够将 agents 组织到多个文件中，构建可扩展的大型应用。

## 为什么需要 AgentRouter？

当项目规模增长时，将所有 agents 定义在一个文件中会变得难以维护：

```python
# ❌ 不推荐：所有 agents 在一个文件中
kiva = Kiva(...)

@kiva.agent("weather_forecast", "...")
def forecast(): ...

@kiva.agent("weather_alerts", "...")
def alerts(): ...

@kiva.agent("math_add", "...")
def add(): ...

@kiva.agent("math_multiply", "...")
def multiply(): ...

# ... 更多 agents
```

使用 `AgentRouter` 可以将 agents 按功能模块拆分：

```
myapp/
├── main.py              # 入口文件
├── agents/
│   ├── __init__.py
│   ├── weather.py       # 天气相关 agents
│   ├── math.py          # 数学相关 agents
│   └── search.py        # 搜索相关 agents
```

## 基本用法

### 创建 Router

```python
from kiva import AgentRouter

# 创建带前缀的 router
router = AgentRouter(prefix="weather", tags=["weather", "forecast"])
```

### 注册 Agent

```python
# 单工具 agent - 装饰函数
@router.agent("forecast", "获取天气预报")
def get_forecast(city: str) -> str:
    """获取城市天气预报"""
    return f"{city}: 晴天, 25°C"

# 多工具 agent - 装饰类
@router.agent("calculator", "数学计算")
class Calculator:
    def add(self, a: int, b: int) -> int:
        """加法"""
        return a + b
    
    def multiply(self, a: int, b: int) -> int:
        """乘法"""
        return a * b
```

### 在 Kiva 中使用

```python
from kiva import Kiva
from agents.weather import weather_router
from agents.math import math_router

kiva = Kiva(base_url="...", api_key="...", model="gpt-4o")

# 包含 routers
kiva.include_router(weather_router)
kiva.include_router(math_router)

# Method 1: Rich console output
result = await kiva.run("北京天气怎么样？顺便算一下 15 * 8")

# Method 2: Stream events
async for event in kiva.stream("北京天气"):
    print(event.type.value)
```

## 前缀命名

`AgentRouter` 的 `prefix` 参数会自动添加到所有 agent 名称前：

```python
router = AgentRouter(prefix="weather")

@router.agent("forecast", "天气预报")  # 实际名称: weather_forecast
def forecast(): ...

@router.agent("alerts", "天气预警")    # 实际名称: weather_alerts
def alerts(): ...
```

在 `include_router` 时还可以添加额外前缀：

```python
kiva.include_router(weather_router, prefix="v2")
# weather_forecast -> v2_weather_forecast
```

## 嵌套 Router

Router 可以嵌套，实现更细粒度的模块化：

```python
# agents/weather/__init__.py
from kiva import AgentRouter
from .forecast import forecast_router
from .alerts import alerts_router

weather_router = AgentRouter(prefix="weather")
weather_router.include_router(forecast_router)
weather_router.include_router(alerts_router)

# agents/weather/forecast.py
forecast_router = AgentRouter(prefix="forecast")

@forecast_router.agent("daily", "每日预报")
def daily(city: str) -> str: ...

@forecast_router.agent("weekly", "周预报")
def weekly(city: str) -> str: ...
```

最终 agent 名称：`weather_forecast_daily`, `weather_forecast_weekly`

## 完整示例

### 项目结构

```
myapp/
├── main.py
└── agents/
    ├── __init__.py
    ├── weather.py
    └── math.py
```

### agents/weather.py

```python
from kiva import AgentRouter

router = AgentRouter(prefix="weather", tags=["weather"])

@router.agent("forecast", "获取天气预报")
def get_forecast(city: str) -> str:
    """获取指定城市的天气预报"""
    forecasts = {
        "beijing": "北京: 晴, 25°C",
        "tokyo": "东京: 多云, 22°C",
    }
    return forecasts.get(city.lower(), f"{city}: 暂无数据")

@router.agent("alerts", "获取天气预警")
def get_alerts(region: str) -> str:
    """获取指定地区的天气预警"""
    return f"{region}: 无预警"
```

### agents/math.py

```python
from kiva import AgentRouter

router = AgentRouter(prefix="math", tags=["math"])

@router.agent("calculator", "数学计算器")
class Calculator:
    def calculate(self, expression: str) -> str:
        """计算数学表达式"""
        try:
            return str(eval(expression))
        except Exception as e:
            return f"计算错误: {e}"
    
    def add(self, a: int, b: int) -> int:
        """加法"""
        return a + b
```

### main.py

```python
import asyncio
from kiva import Kiva
from agents.weather import router as weather_router
from agents.math import router as math_router

def create_app() -> Kiva:
    kiva = Kiva(
        base_url="https://api.openai.com/v1",
        api_key="your-api-key",
        model="gpt-4o",
    )
    
    kiva.include_router(weather_router)
    kiva.include_router(math_router)
    
    return kiva

async def main():
    app = create_app()
    
    # Method 1: Rich console output
    result = await app.run("北京天气如何？计算 100 / 4")
    print(result)
    
    # Method 2: Stream events
    async for event in app.stream("计算 15 + 8"):
        print(f"{event.type.value}")

if __name__ == "__main__":
    asyncio.run(main())
```

## API 参考

### AgentRouter

```python
class AgentRouter:
    def __init__(
        self,
        prefix: str = "",           # agent 名称前缀
        tags: list[str] | None = None,  # 分类标签
    ): ...
    
    def agent(
        self,
        name: str,          # agent 名称
        description: str,   # agent 描述
    ) -> Callable: ...
    
    def include_router(
        self,
        router: AgentRouter,  # 要包含的子 router
        prefix: str = "",     # 额外前缀
    ) -> None: ...
    
    def get_agents(self) -> list[AgentDefinition]: ...
```

### Kiva.include_router

```python
def include_router(
    self,
    router: AgentRouter,  # 要包含的 router
    prefix: str = "",     # 额外前缀
) -> Kiva: ...  # 返回 self，支持链式调用
```

## 最佳实践

1. **按功能模块划分**：将相关的 agents 放在同一个 router 中
2. **使用有意义的前缀**：前缀应该清晰表达模块的功能
3. **保持 router 独立**：每个 router 应该是自包含的，不依赖其他 router
4. **链式调用**：`include_router` 返回 `self`，支持链式调用

```python
kiva.include_router(weather_router)
kiva.include_router(math_router)
kiva.include_router(search_router)

# 运行
await kiva.run("...")
```
