from __future__ import annotations

from typing import Any, Dict, Optional, Literal
from pydantic import BaseModel


class RouteDecision(BaseModel):
    route: Literal["tool", "direct"]
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    reason: str = ""