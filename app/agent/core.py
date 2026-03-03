from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from openai import APIConnectionError, AuthenticationError, RateLimitError

from app.agent.schema import AgentDecision
from app.agent.llm import decide_with_llm
from app.router.rules import decide_route
from app.tools.registry import ToolRegistry
from app.tools.basic import calculator
from app.tools.wr_yards import wr_yards_predict
from app.tools.web_fetch import web_fetch
from app.tools.analyze_wr import analyze_wr
from app.tools.analyze_wr_raw import analyze_wr_raw
from app.tools.analyze_wr_auto import analyze_wr_auto


@dataclass
class Step:
    kind: str
    content: str
    data: Optional[Dict[str, Any]] = None


class Agent:
    def __init__(self) -> None:
        self.tools = ToolRegistry()
        self.tools.register("calculator", calculator)
        self.tools.register("wr_yards_predict", wr_yards_predict)
        self.tools.register("web_fetch", web_fetch)
        self.tools.register("analyze_wr", analyze_wr)
        self.tools.register("analyze_wr_raw", analyze_wr_raw)
        self.tools.register("analyze_wr_auto", analyze_wr_auto)

    def decide_llm(self, user_message: str, history: List[Dict[str, str]]) -> AgentDecision:
        try:
            return decide_with_llm(user_message, history)
        except RateLimitError:
            return AgentDecision(type="final", final="LLM unavailable: quota/rate limit.")
        except AuthenticationError:
            return AgentDecision(type="final", final="LLM unavailable: bad API key.")
        except APIConnectionError:
            return AgentDecision(type="final", final="LLM unavailable: network error.")
        except Exception as e:
            return AgentDecision(type="final", final=f"LLM unavailable: {type(e).__name__}: {e}")

    def run(
        self,
        user_message: str,
        history: List[Dict[str, str]],
        *,
        trace=None,
        session_id: str | None = None,
    ) -> str:
        route = decide_route(user_message, history)

        if trace is not None:
            trace.log_event(
                event="route_decision",
                data={
                    "route": route.route,
                    "tool_name": route.tool_name,
                    "tool_args": route.tool_args,
                    "reason": route.reason,
                    "session_id": session_id,
                },
            )

        if route.route == "tool":
            tool_name = route.tool_name or ""
            tool_args = route.tool_args or {}

            try:
                if trace is not None:
                    with trace.span(
                        name="tool_call",
                        kind="tool",
                        input={"tool": tool_name, "args": tool_args},
                    ) as sp:
                        result = self.tools.get(tool_name)(**tool_args)
                        trace.log_event(
                            event="tool_result",
                            data={"tool": tool_name, "result_preview": str(result)[:200]},
                            parent_span_id=sp.span_id,
                        )
                else:
                    result = self.tools.get(tool_name)(**tool_args)

                                # Return formatting:
                # - If tool already returns a human-readable string, return it directly.
                # - Otherwise JSON stringify (stable for dicts/lists) and prefix with Result.
                if isinstance(result, str):
                    return result

                # Special-case: raw bundle should come back as machine-readable JSON
                if tool_name == "analyze_wr_raw" and isinstance(result, dict):
                    return "RAW_BUNDLE: " + json.dumps(result)

                return "Result: " + json.dumps(result)

                return f"Result: {result}"
            except Exception as e:
                if trace is not None:
                    trace.log_error(step="tool_call", err=e)
                return f"Tool error: {type(e).__name__}: {e}"

        decision = self.decide_llm(user_message, history)
        if decision.type == "tool":
            return "Tool routing is restricted to deterministic rules only."

        return decision.final or "No final response."
