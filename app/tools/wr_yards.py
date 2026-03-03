from __future__ import annotations

import os
from typing import Any, Dict

import httpx


class PredictorError(RuntimeError):
    pass


def wr_yards_predict(receiver: str, defteam: str) -> Dict[str, Any]:
    """
    Calls the deployed NFL Receiver Yards ML API.

    Requires:
      RECEIVER_YARDS_API_URL environment variable.
    """
    base_url = os.getenv("RECEIVER_YARDS_API_URL", "").rstrip("/")
    if not base_url:
        raise PredictorError("Missing RECEIVER_YARDS_API_URL environment variable.")

    url = f"{base_url}/predict"

    payload = {
        "receiver": receiver,
        "defteam": defteam,
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.post(url, json=payload)
            r.raise_for_status()
            return r.json()
    except httpx.HTTPStatusError as e:
        raise PredictorError(f"Model API error: {e.response.text}") from e
    except httpx.RequestError as e:
        raise PredictorError(f"Request failed: {type(e).__name__}: {e}") from e
