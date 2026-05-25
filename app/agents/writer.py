import logging

from google.genai import types

from app.client import MODEL_PRO, get_client
from app.state import EbookState

logger = logging.getLogger(__name__)

# Cap on research text injected into the writer prompt.
_RESEARCH_BUDGET = 8_000
# Cap on style-reference excerpt taken from the last completed chapter.
_STYLE_SNIPPET = 600


def writer_node(state: EbookState) -> dict:
    """Generate or revise the draft for the current chapter.

    Reads ``state.current_chapter_index`` to identify the target chapter,
    pulls the relevant research material from ``state.research_data``, and
    uses the last completed chapter (if any) as a style reference so the
    book voice stays consistent throughout.

    When ``state.feedback`` is non-empty the writer operates in *revision*
    mode: both the previous draft and the verifier's specific feedback are
    included in the prompt so the model can make targeted improvements
    rather than rewriting from scratch.

    Args:
        state: Current graph state.

    Returns:
        Dict with ``current_draft`` set to the generated chapter text.

    Raises:
        IndexError: If ``current_chapter_index`` is out of bounds.
    """
    idx = state.current_chapter_index
    chapter = state.outline[idx]

    chapter_id: str = chapter["id"]
    chapter_title: str = chapter.get("title", f"Chapter {idx + 1}")
    sections: list[dict] = chapter.get("sections", [])
    key_points: list[str] = chapter.get("key_points", [])

    logger.info(
        "[Writer] %s chapter %d: %r | revision: %s",
        "Revising" if state.feedback else "Writing",
        idx + 1,
        chapter_title[:60],
        "yes" if state.feedback else "no",
    )

    sections_block = "\n".join(
        f"  • {s.get('title', s.get('id', ''))}" for s in sections
    ) or "  (write as a single unified chapter)"

    key_points_block = "\n".join(f"  • {kp}" for kp in key_points)

    research_block = _get_research(chapter_id, state.research_data)
    style_block = _get_style_reference(state.completed_chapters)
    revision_block = _get_revision_block(state.current_draft, state.feedback)

    prompt = (
        f"You are a professional non-fiction author writing a book titled:\n"
        f"'{state.topic}'\n\n"
        f"Write the complete text for Chapter {idx + 1}: \"{chapter_title}\"\n\n"
        f"Subsections to cover:\n{sections_block}\n\n"
        f"Key points that MUST be thoroughly addressed:\n{key_points_block}\n\n"
        f"Research material to draw from:\n{research_block}\n"
        f"{style_block}"
        f"{revision_block}\n\n"
        "Writing requirements:\n"
        "- Authoritative, engaging non-fiction style — no fluff\n"
        "- Each subsection: at least 4 substantial paragraphs with concrete details\n"
        "- Ground all claims in the research material provided\n"
        "- Use smooth transitions between subsections\n"
        "- Target length: 1 500–3 000 words\n"
        "- Begin directly with the chapter content (no meta-commentary)\n"
    )

    response = get_client().models.generate_content(
        model=MODEL_PRO,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=(
                "You are an expert non-fiction author. Write authoritative, "
                "precise, and engaging content grounded in the provided research."
            ),
        ),
    )

    draft = response.text or ""
    logger.info("[Writer] Draft produced: %d chars", len(draft))
    return {"current_draft": draft}


def _get_research(chapter_id: str, research_data: dict[str, list[str]]) -> str:
    findings = research_data.get(chapter_id, [])
    if not findings:
        return "(No chapter-specific research available — draw from general knowledge.)"
    text = "\n".join(findings)
    return text[:_RESEARCH_BUDGET] + ("…" if len(text) > _RESEARCH_BUDGET else "")


def _get_style_reference(completed: dict[str, str]) -> str:
    if not completed:
        return ""
    last_text = list(completed.values())[-1]
    snippet = last_text[:_STYLE_SNIPPET]
    return (
        f"\nStyle reference (maintain consistent voice and tone with previous chapters):\n"
        f"---\n{snippet}…\n---\n"
    )


def _get_revision_block(previous_draft: str, feedback: str) -> str:
    if not feedback:
        return ""
    snippet = previous_draft[:2_000] + ("…" if len(previous_draft) > 2_000 else "")
    return (
        f"\n\nPREVIOUS DRAFT (to be improved):\n---\n{snippet}\n---\n\n"
        f"REVISION INSTRUCTIONS FROM EDITOR:\n{feedback}\n"
        "Address every point above carefully in your revised version."
    )
