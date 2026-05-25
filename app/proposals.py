import re

from google.genai import types

from app.client import MODEL_FLASH, MODEL_PRO, get_client
from app.tools import OutlineSchema


def generate_titles(topic: str) -> list[str]:
    """Generate 5 compelling ebook title options for the given topic."""
    prompt = (
        "Generate 5 compelling, attention-grabbing titles for a non-fiction book about:\n"
        f"{topic}\n\n"
        "Requirements:\n"
        "- Each title must be intriguing and make readers immediately want to read the book\n"
        "- Use proven non-fiction title patterns: bold claims, curiosity gaps, specific promises\n"
        "- Vary the style: some short and punchy, some with subtitles, some with numbers\n"
        "- Write titles in the same language as the topic\n"
        "- Return ONLY the 5 titles, one per line, numbered 1 to 5\n"
    )
    response = get_client().models.generate_content(model=MODEL_FLASH, contents=prompt)
    raw = response.text or ""
    titles: list[str] = []
    for line in raw.splitlines():
        cleaned = re.sub(r"^[\d]+[.)]\s*", "", line.strip()).strip()
        if cleaned:
            titles.append(cleaned)
    return titles[:5]


def generate_outline(title: str, topic: str, max_chapters: int) -> list[dict]:
    """Generate a chapter outline for the given title and topic."""
    if max_chapters > 0:
        chapter_count_rule = (
            f"⚠ HARD CONSTRAINT: Generate EXACTLY {max_chapters} chapter(s). "
            "Do not produce more or fewer chapters.\n\n"
        )
        chapter_range_rule = f"- EXACTLY {max_chapters} chapter(s)\n"
    else:
        chapter_count_rule = ""
        chapter_range_rule = "- 8 to 12 chapters with a clear narrative arc\n"

    prompt = (
        "You are the architect of a professional non-fiction book.\n\n"
        f"Book title: {title}\n"
        f"Topic context: {topic}\n\n"
        f"{chapter_count_rule}"
        "Design a comprehensive chapter outline. Requirements:\n"
        f"{chapter_range_rule}"
        "- Each chapter must have 3 to 5 subsections\n"
        "- Each chapter must list 4 to 6 specific key points to cover\n"
        "- Chapter and section titles must be professional and descriptive\n"
        "- Chapters should build progressively on each other\n"
    )

    response = get_client().models.generate_content(
        model=MODEL_PRO,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_schema=OutlineSchema,
            response_mime_type="application/json",
        ),
    )

    outline_obj: OutlineSchema | None = response.parsed  # type: ignore[assignment]
    if outline_obj is None:
        raise ValueError("Could not parse outline from model response.")
    return outline_obj.to_state_outline()
