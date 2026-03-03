from __future__ import annotations

import re
from typing import Dict, List

import httpx


class WebFetchError(RuntimeError):
    pass


_SIGNAL_TERMS = [
    # practice status / game status
    "dnp", "did not practice", "did not participate",
    "limited", "limited participation",
    "full", "full participation", "full practice",
    "questionable", "doubtful", "out", "inactive",
    "no injury designation", "no designation", "cleared",
    "injury report", "practice status", "game status",
    "wednesday", "thursday", "friday",
    # common injury words
    "hamstring", "ankle", "groin", "concussion", "illness", "knee", "hip", "toe",
]


def _clean_html_to_text(html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _find_windows(raw: str, *, max_snippets: int = 6, window: int = 220) -> List[str]:
    raw_l = raw.lower()
    hits: List[str] = []

    for term in _SIGNAL_TERMS:
        start = 0
        while True:
            idx = raw_l.find(term, start)
            if idx == -1:
                break
            lo = max(0, idx - window)
            hi = min(len(raw), idx + len(term) + window)
            snippet = raw[lo:hi].strip()
            if snippet:  # IMPORTANT: never append empties
                hits.append(snippet)
            start = idx + len(term)

    # de-dupe + drop empties
    seen = set()
    uniq: List[str] = []
    for s in hits:
        s = s.strip()
        if not s:
            continue
        key = s[:160]
        if key in seen:
            continue
        seen.add(key)
        uniq.append(s)
        if len(uniq) >= max_snippets:
            break

    return uniq


def web_fetch(url: str) -> Dict[str, object]:
    """
    Returns:
      {"url": "...", "snippets": [...], "mode": "..."}
    GUARANTEE: snippets is always a non-empty list of non-empty strings
    """
    try:
        with httpx.Client(timeout=12.0, follow_redirects=True) as client:
            r = client.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
            r.raise_for_status()
            html = r.text or ""
    except httpx.HTTPError as e:
        raise WebFetchError(f"Fetch failed: {type(e).__name__}: {e}") from e

    cleaned = _clean_html_to_text(html)

    hits = _find_windows(cleaned)
    hits = [h for h in hits if h.strip()]
    if hits:
        return {"url": url, "snippets": hits, "mode": "cleaned_text_windows"}

    raw_hits = _find_windows(html)
    raw_hits = [h for h in raw_hits if h.strip()]
    if raw_hits:
        pretty = [_clean_html_to_text(s) for s in raw_hits]
        pretty = [p for p in pretty if p.strip()]
        if pretty:
            return {"url": url, "snippets": pretty[:6], "mode": "raw_html_windows"}

    # HARD fallback: guaranteed non-empty
    fallback = (cleaned[:1200] or html[:1200]).strip()
    if not fallback:
        fallback = f"[no readable text extracted; likely JS-rendered/blocked] url={url}"

    return {"url": url, "snippets": [fallback], "mode": "fallback_head"}
