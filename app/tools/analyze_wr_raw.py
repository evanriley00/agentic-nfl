from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.tools.wr_yards import wr_yards_predict
from app.tools.web_fetch import web_fetch


def analyze_wr_raw(receiver: str, defteam: str, urls: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Returns the raw analysis bundle (ML prediction + fetched evidence previews).

    Normalizes web_fetch output into:
      evidence: [{ "url": str, "snippets": [str, ...], "mode": str }]
    """
    ml = wr_yards_predict(receiver=receiver, defteam=defteam)

    evidence: List[Dict[str, Any]] = []
    for url in (urls or [])[:5]:
        fetched = web_fetch(url=url)

        snippets = fetched.get("snippets") or []
        if not isinstance(snippets, list):
            snippets = [snippets]

        # ensure strings + drop empties
        snippets = [str(s).strip() for s in snippets if str(s).strip()]

        evidence.append(
            {
                "url": str(fetched.get("url", url)),
                "snippets": snippets,
                "mode": str(fetched.get("mode", "")),
            }
        )

    return {
        "receiver": receiver,
        "defteam": defteam,
        "ml_prediction": ml,
        "evidence": evidence,
    }