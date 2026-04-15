from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI

from app.config import settings


@dataclass(frozen=True)
class SentimentDistribution:
    positive_pct: float
    neutral_pct: float
    negative_pct: float


def _client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return OpenAI(api_key=settings.openai_api_key)


def analyze_title_sentiment_distribution(titles: list[str]) -> SentimentDistribution:
    """
    Use LLM to estimate sentiment distribution of given titles.
    Returns percentages in [0,100] that sum to ~100.
    """
    cleaned = [t.strip() for t in titles if (t or "").strip()]
    if not cleaned:
        return SentimentDistribution(positive_pct=0.0, neutral_pct=0.0, negative_pct=0.0)

    c = _client()
    import json

    system = (
        "You output ONLY valid JSON. No prose, no markdown, no code fences. "
        "Task: Given a list of Korean social/community post titles, estimate overall sentiment distribution "
        "across the titles. "
        "Sentiment labels: positive, neutral, negative. "
        "Output keys: positive_pct(number), neutral_pct(number), negative_pct(number). "
        "Percentages must be between 0 and 100 and sum to 100 (allow small rounding error)."
    )
    user = {"titles": cleaned[:200]}

    resp = c.chat.completions.create(
        model=settings.openai_model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
        ],
        temperature=0.2,
    )

    text = (resp.choices[0].message.content or "").strip()
    if not text:
        return SentimentDistribution(positive_pct=0.0, neutral_pct=0.0, negative_pct=0.0)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        import re

        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return SentimentDistribution(positive_pct=0.0, neutral_pct=0.0, negative_pct=0.0)
        data = json.loads(m.group(0))

    def _num(x) -> float:
        try:
            return float(x)
        except Exception:
            return 0.0

    p = max(0.0, min(100.0, _num(data.get("positive_pct"))))
    n = max(0.0, min(100.0, _num(data.get("neutral_pct"))))
    g = max(0.0, min(100.0, _num(data.get("negative_pct"))))
    s = p + n + g
    if s <= 0:
        return SentimentDistribution(positive_pct=0.0, neutral_pct=0.0, negative_pct=0.0)

    # Normalize to exactly 100.0 to keep API stable.
    p = p * 100.0 / s
    n = n * 100.0 / s
    g = g * 100.0 / s
    return SentimentDistribution(positive_pct=p, neutral_pct=n, negative_pct=g)

