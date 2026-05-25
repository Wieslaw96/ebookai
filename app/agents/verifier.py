import logging

from app.client import MODEL_PRO, get_client
from app.state import EbookState

logger = logging.getLogger(__name__)

_APPROVED_MARKER = "APPROVED"
_REVISION_MARKER = "REVISION_NEEDED"

# Minimum word count considered acceptable for a chapter draft.
_MIN_WORDS = 1_200


def verifier_node(state: EbookState) -> dict:
    """Quality-gate the current chapter draft and decide pass or revise.

    Evaluates the draft on five axes: completeness (all key_points covered),
    factual coherence, depth, writing style, and minimum length. The model
    is instructed to begin its response with exactly ``APPROVED`` or
    ``REVISION_NEEDED`` so the output can be parsed deterministically.

    *On approval*: the draft is committed to ``completed_chapters``,
    ``current_chapter_index`` is incremented, and ``current_draft`` /
    ``feedback`` are cleared — ready for the writer to tackle the next
    chapter.

    *On rejection*: ``feedback`` is populated with actionable editor notes
    and the writer node will be re-invoked on the same chapter.

    Args:
        state: Current graph state.

    Returns:
        On approval: updated ``completed_chapters``, incremented
        ``current_chapter_index``, cleared ``current_draft`` and ``feedback``.
        On rejection: updated ``feedback`` only.
    """
    idx = state.current_chapter_index
    chapter = state.outline[idx]

    chapter_title: str = chapter.get("title", f"Chapter {idx + 1}")
    key_points: list[str] = chapter.get("key_points", [])
    key_points_block = "\n".join(f"  • {kp}" for kp in key_points)

    word_count = len(state.current_draft.split())

    prompt = (
        f"You are a rigorous non-fiction book editor.\n\n"
        f"Book topic: {state.topic}\n"
        f"Chapter under review: \"{chapter_title}\" (Chapter {idx + 1})\n\n"
        f"Required key points that must be addressed:\n{key_points_block}\n\n"
        f"DRAFT TO REVIEW ({word_count} words):\n"
        f"---\n{state.current_draft}\n---\n\n"
        "Evaluate the draft on these five criteria:\n"
        f"1. COMPLETENESS – Are all {len(key_points)} key points addressed?\n"
        "2. ACCURACY – Is the content factually coherent with no obvious errors?\n"
        "3. DEPTH – Is each topic explored in sufficient detail?\n"
        "4. STYLE – Is the writing authoritative, clear, and engaging?\n"
        f"5. LENGTH – Is it substantial enough? (minimum {_MIN_WORDS} words)\n\n"
        "DECISION RULES:\n"
        f"- If the draft satisfactorily meets all criteria → respond: {_APPROVED_MARKER}\n"
        f"- If it needs improvement → respond: {_REVISION_MARKER}\n"
        "  Followed by a numbered list of specific, actionable feedback points.\n"
        "  Be precise: cite the key point that is missing or the paragraph that "
        "needs improvement.\n\n"
        f"Your response (start with {_APPROVED_MARKER} or {_REVISION_MARKER}):"
    )

    response = get_client().models.generate_content(
        model=MODEL_PRO,
        contents=prompt,
    )

    verdict = (response.text or "").strip()
    chapter_id: str = chapter["id"]

    if verdict.startswith(_APPROVED_MARKER):
        logger.info(
            "[Verifier] APPROVED chapter %d: %r (%d words)",
            idx + 1,
            chapter_title[:60],
            word_count,
        )
        updated_chapters = {**state.completed_chapters, chapter_id: state.current_draft}
        return {
            "completed_chapters": updated_chapters,
            "current_chapter_index": idx + 1,
            "current_draft": "",
            "feedback": "",
        }

    # Extract the actionable feedback (everything after the REVISION_NEEDED marker).
    feedback_text = verdict.removeprefix(_REVISION_MARKER).strip()
    logger.info(
        "[Verifier] REVISION_NEEDED for chapter %d: %r | feedback: %d chars",
        idx + 1,
        chapter_title[:60],
        len(feedback_text),
    )
    return {"feedback": feedback_text}
