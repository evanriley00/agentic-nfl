from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class RouteDecision:
    route: str  # "tool" | "direct"
    tool_name: str | None = None
    tool_args: Dict | None = None
    reason: str = ""


_CALC_PATTERNS = [
    r"^\s*calc\s+.+",
    r"^\s*calculate\s+.+",
    r"^\s*what\s+is\s+[-+*/().\d\s]+[?]?\s*$",
    r"^\s*[-+*/().\d\s]+\s*$",
]

# Existing patterns (keep)
_ANALYZE_RAW_PAT = r"^\s*analyze-raw\s+(.+?)\s+vs\s+([A-Z]{2,3})\b(.*)$"
_ANALYZE_PAT = r"^\s*analyze\s+(.+?)\s+vs\s+([A-Z]{2,3})\b(.*)$"

# New: predict patterns
_PREDICT_PAT = r"^\s*predict\s+(.+?)\s+(?:vs|against)\s+([A-Z]{2,3})\b(.*)$"

# New: explicit tool-call prefix
_TOOLCALL_ANALYZE_WR_RAW = r"^\s*analyze_wr_raw\b(.*)$"

def _normalize_receiver_name(name: str) -> str:
    """
    Converts 'Justin Jefferson' -> 'J.Jefferson'
    If already in 'X.Last' format, returns as-is.
    """
    name = name.strip()

    # already like J.Jefferson
    if re.match(r"^[A-Z]\.[A-Za-z]+$", name):
        return name

    parts = re.split(r"\s+", name)
    if len(parts) >= 2:
        first = parts[0]
        last = parts[-1]
        return f"{first[0].upper()}.{last}"

    return name

def _parse_tool_kv_args(rest: str) -> Dict:
    """
    Parses strings like:
      receiver="Justin Jefferson" defteam="CLE" urls=["https://...","https://..."]

    Uses ast.literal_eval for bracketed lists; otherwise strips quotes.
    """
    rest = rest.strip()
    args: Dict = {}

    # key=value tokens where value can be "quoted", [list], or bare
    parts = re.findall(r'(\w+)=(".*?"|\[.*?\]|\S+)', rest)
    for k, v in parts:
        v = v.strip()
        if v.startswith('"') and v.endswith('"'):
            args[k] = v[1:-1]
        elif v.startswith("[") and v.endswith("]"):
            try:
                args[k] = ast.literal_eval(v)
            except Exception:
                # fall back to a single-item list if parsing fails
                args[k] = [v]
        else:
            args[k] = v

    # normalize urls if provided as a single string
    if "urls" in args and not isinstance(args["urls"], list):
        args["urls"] = [str(args["urls"])]

    return args


def decide_route(user_message: str, history: List[Dict[str, str]] | None = None) -> RouteDecision:
    msg = (user_message or "").strip()

    # 0) explicit tool-call: analyze_wr_raw receiver=... defteam=... urls=[...]
    m = re.match(_TOOLCALL_ANALYZE_WR_RAW, msg, flags=re.IGNORECASE)
    if m:
        rest = (m.group(1) or "").strip()
        tool_args = _parse_tool_kv_args(rest)

        # minimal normalization
        if "defteam" in tool_args and isinstance(tool_args["defteam"], str):
            tool_args["defteam"] = tool_args["defteam"].upper().strip()

        return RouteDecision(
            route="tool",
            tool_name="analyze_wr_raw",
            tool_args=tool_args,
            reason="Matched explicit tool-call analyze_wr_raw routing.",
        )

    # 1) analyze-raw <receiver> vs <TEAM> [urls...]
    m = re.match(_ANALYZE_RAW_PAT, msg, flags=re.IGNORECASE)
    if m:
        receiver = _normalize_receiver_name(m.group(1).strip())
        defteam = m.group(2).upper().strip()
        rest = (m.group(3) or "").strip()
        urls = re.findall(r"https?://\S+", rest)
        return RouteDecision(
            route="tool",
            tool_name="analyze_wr_raw",
            tool_args={"receiver": receiver, "defteam": defteam, "urls": urls},
            reason="Matched deterministic analyze-raw routing.",
        )

    # 2) analyze <receiver> vs <TEAM> (auto URLs if none provided)
    m = re.match(_ANALYZE_PAT, msg, flags=re.IGNORECASE)
    if m:
        receiver = _normalize_receiver_name(m.group(1).strip())
        defteam = m.group(2).upper().strip()
        rest = (m.group(3) or "").strip()
        urls = re.findall(r"https?://\S+", rest)

        if urls:
            return RouteDecision(
                route="tool",
                tool_name="analyze_wr",
                tool_args={"receiver": receiver, "defteam": defteam, "urls": urls},
                reason="Matched analyze routing with URLs.",
            )

        return RouteDecision(
            route="tool",
            tool_name="analyze_wr_auto",
            tool_args={"receiver": receiver, "defteam": defteam},
            reason="Matched analyze routing (auto URLs).",
        )

    # 2.5) predict <receiver> vs/against <TEAM>
    m = re.match(_PREDICT_PAT, msg, flags=re.IGNORECASE)
    if m:
        receiver_raw = m.group(1).strip()
        defteam = m.group(2).upper().strip()

        receiver = _normalize_receiver_name(receiver_raw)

        return RouteDecision(
            route="tool",
            tool_name="wr_yards_predict",
            tool_args={"receiver": receiver, "defteam": defteam},
            reason="Matched deterministic predict routing.",
    )

    # 3) calculator
    for pat in _CALC_PATTERNS:
        if re.search(pat, msg, flags=re.IGNORECASE):
            expr = msg
            expr = re.sub(r"^\s*calc\s+", "", expr, flags=re.IGNORECASE)
            expr = re.sub(r"^\s*calculate\s+", "", expr, flags=re.IGNORECASE)
            expr = expr.strip().rstrip("?")
            return RouteDecision(
                route="tool",
                tool_name="calculator",
                tool_args={"expression": expr},
                reason="Matched deterministic calculator routing.",
            )

    return RouteDecision(route="direct", reason="No deterministic tool route matched.")