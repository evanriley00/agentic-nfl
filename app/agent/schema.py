from typing import Literal, Optional, Dict, Any
from pydantic import BaseModel, Field

class ToolCall(BaseModel):
    name: str = Field(..., description="Tool name to call")
    args: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments")

class AgentDecision(BaseModel):
    type: Literal["tool", "final"] = Field(..., description="Decision type")
    tool: Optional[ToolCall] = None
    final: Optional[str] = None