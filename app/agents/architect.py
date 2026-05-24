import logging

from google.genai import types

from app.client import MODEL_PRO, get_client
from app.state import EbookState
from app.tools import OutlineSchema

logger = logging.getLogger(__name__)

# Maximum characters of research material passed to the model to avoid
# exceeding the context window when research_data is large.
_RESEARCH_BUDGET = 12_000


def architect_node(state: EbookState) -> dict:
    """Design the full ebook structure using Gemini Structured Outputs.

    Sends the topic and a condensed research summary to ``MODEL_PRO`` with
    ``OutlineSchema`` as the ``response_schema``. The SDK automatically
    deserialises the JSON response into an ``OutlineSchema`` Pydantic object
    (available on ``response.parsed``). The result is then converted to the
    ``list[dict]`` format expected by ``EbookState.outline``.

    Args:
        state: Current graph state. Uses ``state.topic`` and
            ``state.research_data``.

    Returns:
        Dict with the ``outline`` field set to the generated chapter list.

    Raises:
        ValueError: If the model returns an unparseable response.
    """
    research_summary = _condense_research(state.research_data)

    # Build an optional hard constraint on chapter count (used during tests/previews).
    if state.max_chapters > 0:
        chapter_count_rule = (
            f"⚠ HARD CONSTRAINT: Generate EXACTLY {state.max_chapters} chapter(s). "
            "Do not produce more or fewer chapters under any circumstances.\n\n"
        )
        chapter_range_rule = f"- EXACTLY {state.max_chapters} chapter(s)\n"
    else:
        chapter_count_rule = ""
        chapter_range_rule = "- 8 to 12 chapters with a clear narrative arc\n"

    prompt = (
        f"You are the architect of a professional non-fiction book.\n\n"
        f"Topic: {state.topic}\n\n"
        f"Research material collected:\n{research_summary}\n\n"
        f"{chapter_count_rule}"
        "Design a comprehensive outline for a non-fiction book "
        "on this topic. Requirements:\n"
        f"{chapter_range_rule}"
        "- Each chapter must have 3 to 5 subsections\n"
        "- Each chapter must list 4 to 6 specific key points to cover\n"
        "- Chapter and section titles must be professional and descriptive\n"
        "- The book title should be compelling and marketable\n"
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

    # The SDK populates response.parsed when response_schema is a Pydantic class.
    outline_obj: OutlineSchema | None = response.parsed  # type: ignore[assignment]
    if outline_obj is None:
        raise ValueError(
            "Architect: model returned an unparseable response. "
            f"Raw text: {response.text[:200]!r}"
        )

    logger.info(
        "[Architect] Outline created: %r | %d chapters",
        outline_obj.title,
        len(outline_obj.chapters),
    )

    return {"outline": outline_obj.to_state_outline()}


def _condense_research(research_data: dict[str, list[str]]) -> str:
    """Flatten research_data into a single string, respecting the budget."""
    if not research_data:
        return "(No research data available – proceed from general knowledge.)"

    parts: list[str] = []
    budget = _RESEARCH_BUDGET
    for key, findings in research_data.items():
        snippet = findings[0] if findings else ""
        chunk = f"[{key}]\n{snippet}"
        if len(chunk) > budget:
            chunk = chunk[:budget] + "…"
        parts.append(chunk)
        budget -= len(chunk)
        if budget <= 0:
            break

    return "\n\n".join(parts)
