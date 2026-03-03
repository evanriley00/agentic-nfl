from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.tools.analyze_wr_raw import analyze_wr_raw

# Local anchor averages 
RECEIVER_AVG_YARDS = {
    "J.Jefferson": 91.0,  # example placeholder;
}
# --- Helpers to read evidence text consistently ---

def _text_from_evidence_item(item: Dict[str, Any]) -> str:
    snippets = item.get("snippets")
    if isinstance(snippets, list) and snippets:
        joined = " ".join(str(s) for s in snippets if str(s).strip())
        return joined.lower().strip()

    preview = item.get("preview")
    if isinstance(preview, str) and preview.strip():
        return preview.lower().strip()

    return ""


def _receiver_mentioned(txt: str, receiver: str) -> bool:
    r = receiver.lower().strip()
    last = r.split(".")[-1] if "." in r else (r.split()[-1] if r else "")
    if not last:
        return False
    return (r in txt) or (last in txt)


def _severity(txt: str) -> int:
    """
    Map injury/practice language to severity.
    0 = none/unknown
    1 = questionable/limited
    2 = doubtful
    3 = out/inactive/ruled out/IR
    """
    if any(t in txt for t in ["ruled out", "out", "inactive", "placed on ir", "injured reserve"]):
        return 3
    if "doubtful" in txt:
        return 2
    if any(t in txt for t in ["questionable", "limited", "did not practice", "dnp"]):
        return 1
    return 0


def _near(txt: str, a: str, b: str, window: int = 80) -> bool:
    i = txt.find(a)
    if i == -1:
        return False
    lo = max(0, i - window)
    hi = min(len(txt), i + len(a) + window)
    return b in txt[lo:hi]


# --- Domain-ish vocab for trenches ---

_OL_TERMS = [
    "lt", "rt", "lg", "rg", "c",
    "left tackle", "right tackle", "left guard", "right guard", "center",
    "tackle", "guard", "offensive line", "o-line", "oline",
]

_DL_TERMS = [
    "edge", "de", "dt",
    "defensive end", "defensive tackle",
    "pass rush", "pressure", "pressures", "sack", "sacks",
    "front four", "rush", "rushes",
]

_CB_TERMS = [
    "cb", "corner", "cornerback", "secondary", "nickel", "slot",
]


def _has_any(txt: str, terms: List[str]) -> bool:
    return any(t in txt for t in terms)


def _score_shift_and_uncertainty(receiver: str, evidence: List[Dict[str, Any]]) -> Tuple[float, float, List[str]]:
    """
    Returns:
      shift_yards: positive => MORE than ML, negative => LESS than ML
      widen_yards: additional width to add to the range (>=0)
      reasons: human-readable, source-citable strings
    """
    shift = 0.0
    widen = 0.0
    reasons: List[str] = []

    # Track conflicting signals to widen the range
    pos_hits = 0
    neg_hits = 0

    for item in evidence:
        url = str(item.get("url", "")).strip()
        tag = str(item.get("tag", "")).strip()
        txt = _text_from_evidence_item(item)
        if not txt:
            continue

        sev = _severity(txt)

        # --- Coverage (CB availability) ---
        # If defense has secondary injuries OUT => tailwind for WR (MORE) + some widen (uncertainty)
        if tag == "injury_def" and _has_any(txt, _CB_TERMS):
            if sev >= 2:
                shift += 6.0 * sev  # big-ish
                widen += 2.0 * sev
                pos_hits += 1
                reasons.append(f"Coverage tailwind: defense secondary issue severity={sev} from {url}")
            elif sev == 1:
                shift += 3.0
                widen += 1.0
                pos_hits += 1
                reasons.append(f"Coverage tailwind: defense secondary questionables/limited from {url}")

        # --- Trenches: Offense OL health ---
        # Only treat OL status as meaningful if snippet looks OL-related
        if tag == "injury_off" and _has_any(txt, _OL_TERMS):
            if sev >= 2:
                # OL starter OUT/DOUBTFUL hurts WR ceiling (LESS) and increases uncertainty a lot
                shift -= 7.0 * sev
                widen += 4.0 * sev
                neg_hits += 1
                reasons.append(f"Trench headwind: offense OL issue severity={sev} from {url}")
            elif sev == 1:
                shift -= 4.0
                widen += 2.0
                neg_hits += 1
                reasons.append(f"Trench headwind: offense OL limited/questionable from {url}")

        # --- Trenches: Defense DL / pass rush health ---
        if tag == "injury_def" and _has_any(txt, _DL_TERMS):
            if sev >= 2:
                # Defensive front missing key pieces reduces pressure -> MORE for WR; still widen due to replacement uncertainty
                shift += 8.0 * sev
                widen += 3.0 * sev
                pos_hits += 1
                reasons.append(f"Trench tailwind: defense pass rush/DL issue severity={sev} from {url}")
            elif sev == 1:
                shift += 4.0
                widen += 2.0
                pos_hits += 1
                reasons.append(f"Trench tailwind: defense pass rush/DL limited/questionable from {url}")

        # --- Receiver-specific health: only count if receiver mentioned ---
        # This prevents “team injury report noise” from nuking the projection.
        if _receiver_mentioned(txt, receiver):
            if sev >= 2:
                shift -= 10.0 * sev
                widen += 5.0 * sev
                neg_hits += 1
                reasons.append(f"Receiver headwind: receiver mentioned with severity={sev} from {url}")
            elif sev == 1:
                shift -= 6.0
                widen += 3.0
                neg_hits += 1
                reasons.append(f"Receiver headwind: receiver mentioned as limited/questionable from {url}")

    # Conflict widens the range: if we have both headwinds and tailwinds, uncertainty jumps
    if pos_hits > 0 and neg_hits > 0:
        widen += 6.0

    # Keep widen sane
    if widen < 0:
        widen = 0.0
    if widen > 35.0:
        widen = 35.0

    # Cap shift to avoid absurd jumps (still lets big players matter)
    if shift > 35.0:
        shift = 35.0
    if shift < -35.0:
        shift = -35.0

    return shift, widen, reasons


def analyze_wr(
    receiver: str,
    defteam: str,
    urls: Optional[List[str]] = None,
    evidence: Optional[List[Dict[str, Any]]] = None,
) -> str:
    # Always get ML base from your predictor via analyze_wr_raw (even if evidence passed)
    ml_bundle = analyze_wr_raw(receiver=receiver, defteam=defteam, urls=[])
    ml = ml_bundle.get("ml_prediction") or {}
    base = float(ml.get("predicted_yards", 0.0))

    if evidence is None:
        bundle = analyze_wr_raw(receiver=receiver, defteam=defteam, urls=urls or [])
        evidence = bundle.get("evidence") or []

    shift, widen, reasons = _score_shift_and_uncertainty(receiver, evidence or [])

    adjusted_point = max(0.0, base + shift)

    # Range width: start small, widen based on trench/availability uncertainty
    base_half_width = 3.0
    half_width = base_half_width + widen

    low = max(0.0, adjusted_point - half_width)
    high = adjusted_point + half_width

    # Verdict compared to ML baseline
    if adjusted_point > base + 2.0:
        direction = "MORE"
    elif adjusted_point < base - 2.0:
        direction = "LESS"
    else:
        direction = "NEUTRAL"

    # sources list (unique, preserve order)
    seen = set()
    sources: List[str] = []
    for it in (evidence or []):
        u = str(it.get("url", "")).strip()
        if u and u not in seen:
            seen.add(u)
            sources.append(u)

    out_lines = [
        f"Receiver: {receiver} vs {defteam}",
        f"ML Base: {base:.3f} yards",
        f"Verdict vs ML: {direction}",
        f"Adjusted Point: {adjusted_point:.1f}",
        f"Adjusted Range: {low:.1f}-{high:.1f}",
        "Reasons:",
    ]

    if reasons:
        for r in reasons[:8]:
            out_lines.append(f"- {r}")
    else:
        out_lines.append("- No strong evidence signals detected; staying near the model baseline.")

    out_lines.append("Sources:")
    if sources:
        for i, u in enumerate(sources[:10], start=1):
            out_lines.append(f"[{i}] {u}")
    else:
        out_lines.append("- (none)")

    return "\n".join(out_lines)