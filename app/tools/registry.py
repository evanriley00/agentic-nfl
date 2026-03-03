from typing import Any, Callable, Dict

ToolFn = Callable[..., Any]

class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, ToolFn] = {}

    def register(self, name: str, fn: ToolFn) -> None:
        if name in self._tools:
            raise ValueError(f"Tool already registered: {name}")
        self._tools[name] = fn

    def get(self, name: str) -> ToolFn:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name]

    def list_tools(self) -> Dict[str, ToolFn]:
        return dict(self._tools)