from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app.tools.web_fetch import web_fetch
from app.tools.analyze_wr import analyze_wr


RECEIVER_TEAM = {
    "J.Jefferson": "MIN",
    "J. Jefferson": "MIN",
    "Justin Jefferson": "MIN",
}

INJURY_REPORT_URL = {
    "MIN": "https://www.vikings.com/team/injury-report/",
    "CHI": "https://www.chicagobears.com/team/injury-report/",
}

DEPTH_CHART_URL = {
    "MIN": "https://www.espn.com/nfl/team/depth/_/name/min/minnesota-vikings",
    "CHI": "https://www.espn.com/nfl/team/depth/_/name/chi/chicago-bears",
}


def _fetch_many(tagged_urls: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
    """
    tagged_urls: [(url, tag), ...]
    Produces evidence items like:
      {"url":..., "snippets":[...], "mode":..., "tag":"injury_off"}
    """
    evidence: List[Dict[str, Any]] = []
    for u, tag in tagged_urls:
        try:
            item = web_fetch(url=u)
            if isinstance(item, list):
                for it in item:
                    if isinstance(it, dict):
                        it["tag"] = tag
                        evidence.append(it)
            elif isinstance(item, dict):
                item["tag"] = tag
                evidence.append(item)
            else:
                evidence.append({"url": u, "snippets": [f"Unexpected web_fetch return type: {type(item).__name__}"], "mode": "error", "tag": tag})
        except Exception as e:
            evidence.append({"url": u, "snippets": [f"{type(e).__name__}: {e}"], "mode": "error", "tag": tag})
    return evidence


def analyze_wr_auto(receiver: str, defteam: str) -> str:
    receiver_team = RECEIVER_TEAM.get(receiver)

    tagged: List[Tuple[str, str]] = []

    # Defense injury report (DL/CB availability impacts pressure + coverage)
    if defteam in INJURY_REPORT_URL:
        tagged.append((INJURY_REPORT_URL[defteam], "injury_def"))

    # Offense injury report (OL/QB/WR availability impacts protection + volume)
    if receiver_team and receiver_team in INJURY_REPORT_URL:
        tagged.append((INJURY_REPORT_URL[receiver_team], "injury_off"))

    # Depth charts (context / role)
    if receiver_team and receiver_team in DEPTH_CHART_URL:
        tagged.append((DEPTH_CHART_URL[receiver_team], "depth_off"))

    if defteam in DEPTH_CHART_URL:
        tagged.append((DEPTH_CHART_URL[defteam], "depth_def"))

    evidence = _fetch_many(tagged)

    # Pass evidence directly (already fetched + tagged)
    return analyze_wr(receiver=receiver, defteam=defteam, evidence=evidence)