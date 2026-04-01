from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI

from app.config import settings


ALLOWED_CATEGORIES = ["유머", "일상", "스포츠", "정치"]
DISALLOWED_KEYWORDS = {
    # 카테고리 라벨/유사 라벨
    "유머",
    "일상",
    "스포츠",
    "정치",
    # 게시판/분류로 자주 섞이는 단어
    "뉴스",
    "기사",
    "이슈",
    "소식",
    "정보",
    "감동",
}


@dataclass(frozen=True)
class TransformResult:
    title: str
    category: str
    keywords: list[str]


def _client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return OpenAI(api_key=settings.openai_api_key)


def _is_blocked_by_moderation(title: str) -> bool:
    c = _client()
    r = c.moderations.create(model=settings.openai_moderation_model, input=title)
    out = r.results[0]
    # 성적/폭력은 반드시 스킵. (self-harm 등도 보수적으로 스킵)
    if getattr(out, "flagged", False):
        return True
    cats = getattr(out, "categories", None)
    if not cats:
        return False
    return bool(
        getattr(cats, "sexual", False)
        or getattr(cats, "sexual_minors", False)
        or getattr(cats, "violence", False)
        or getattr(cats, "self_harm", False)
        or getattr(cats, "hate", False)
    )


def transform_title_and_category(*, title: str, category: str) -> TransformResult | None:
    if not settings.openai_transform_enabled:
        return TransformResult(title=title, category=category, keywords=[])

    if _is_blocked_by_moderation(title):
        return None

    c = _client()
    import json

    system = (
        "You output ONLY valid JSON. "
        "No prose, no markdown, no code fences. "
        "Keys: skip(boolean), title(string), category(string), keywords(array of strings)."
    )
    user = {
        "title": title,
        "category_hint": category,
        "allowed_categories": ALLOWED_CATEGORIES,
        "rules": {
            "skip_if_advertising": True,
            "skip_if_sexual_or_violent": True,
            "normalize_title_max_chars": 80,
            "keywords_min": 2,
            "keywords_max": 5,
            "keywords_must_not_include": sorted(DISALLOWED_KEYWORDS),
            "keywords_must_not_be_category_label": True,
        },
    }

    # chat.completions JSON 모드로 강제 (파싱 실패 방지)
    resp = c.chat.completions.create(
        model=settings.openai_model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": "다음 입력을 규칙에 맞게 변환해 JSON으로만 응답해줘:\n" + json.dumps(user, ensure_ascii=False),
            },
        ],
        temperature=0.2,
    )

    text = (resp.choices[0].message.content or "").strip()
    if not text:
        return None

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # 모델이 실수로 여분 텍스트를 섞을 수 있어, 첫 JSON 객체만 추출 시도
        import re

        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return None
        data = json.loads(m.group(0))
    if data.get("skip"):
        return None

    out_title = str(data.get("title", "")).strip()[:512]
    out_cat = str(data.get("category", "")).strip()
    if out_cat not in ALLOWED_CATEGORIES:
        out_cat = "일상"
    kws = data.get("keywords") or []
    if not isinstance(kws, list):
        kws = []
    keywords = []
    seen = set()
    for k in kws:
        kk = str(k).strip()
        if kk in DISALLOWED_KEYWORDS:
            continue
        if kk == out_cat:
            continue
        if not kk or kk in seen:
            continue
        seen.add(kk)
        keywords.append(kk[:32])
        if len(keywords) >= 5:
            break

    if not out_title:
        return None

    return TransformResult(title=out_title, category=out_cat, keywords=keywords)

