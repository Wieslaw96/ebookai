import logging
import re
from pathlib import Path
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from app.agents import (
    architect_node,
    manager_node,
    researcher_node,
    verifier_node,
    writer_node,
)
from app.state import EbookState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Routing functions
# ---------------------------------------------------------------------------


def route_after_researcher(state: EbookState) -> Literal["architect", "writer"]:
    """Branch immediately after researcher completes.

    First pass (no outline yet): researcher did broad initial research →
    architect must now create the outline.

    Subsequent passes (outline exists): researcher checked / filled per-chapter
    data → writer can proceed with the current chapter.
    """
    return "architect" if not state.outline else "writer"


def should_continue(
    state: EbookState,
) -> Literal["writer", "researcher", "__end__"]:
    """Branch after verifier decides on the current chapter draft.

    Three outcomes:
    1. Draft rejected (feedback != "")    → writer revises the same chapter.
    2. Chapter accepted, more remaining   → researcher tops up data for the
                                            next chapter (idempotent – already-
                                            researched chapters are skipped),
                                            then writer takes over.
    3. Chapter accepted, outline complete → END.
    """
    if state.feedback:
        return "writer"
    if state.current_chapter_index < len(state.outline):
        return "researcher"
    return END


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

workflow = StateGraph(EbookState)

# --- Nodes ---
workflow.add_node("manager", manager_node)
workflow.add_node("researcher", researcher_node)
workflow.add_node("architect", architect_node)
workflow.add_node("writer", writer_node)
workflow.add_node("verifier", verifier_node)

# --- Static edges ---
# Entry: validate project state and kick off broad research.
workflow.add_edge(START, "manager")
workflow.add_edge("manager", "researcher")

# After outline is created, loop back through researcher so that chapter-
# specific data is fetched for every chapter before writing begins.
workflow.add_edge("architect", "researcher")

# Writing always leads to a quality gate.
workflow.add_edge("writer", "verifier")

# --- Conditional edge: researcher ---
# No outline yet  → architect (build the structure)
# Outline present → writer   (start / continue writing)
workflow.add_conditional_edges("researcher", route_after_researcher)

# --- Conditional edge: verifier ---
# Feedback present            → writer    (revise current chapter)
# No feedback + chapters left → researcher (ensure next chapter is researched)
# No feedback + all done      → END
workflow.add_conditional_edges("verifier", should_continue)

# ---------------------------------------------------------------------------
# Compile
# ---------------------------------------------------------------------------

app_graph = workflow.compile()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_ebook_factory(
    topic: str,
    output_dir: str = ".",
    max_chapters: int = 0,
    outline: list[dict] | None = None,
) -> str:
    """Run the full ebook generation pipeline for a given topic.

    Initialises ``EbookState`` with the supplied topic, then invokes the
    compiled LangGraph workflow to completion.  The pipeline will:

    1. ``manager``    – validate input and log project info.
    2. ``researcher`` – broad initial research (no outline yet).
    3. ``architect``  – generate the full chapter outline (Structured Output).
    4. ``researcher`` – per-chapter targeted research (skips already-cached).
    5. ``writer``     – draft the current chapter.
    6. ``verifier``   – accept or request revision; repeat 5-6 until accepted.
    7. Repeat 4-6 for every chapter in the outline.

    The assembled book is saved as a UTF-8 Markdown file.

    Args:
        topic: Subject of the non-fiction ebook, phrased as a descriptive
            title or brief (e.g. "The psychology of decision-making").
        output_dir: Directory for the output ``.md`` file (default: ``"."``).
        max_chapters: Cap on the number of chapters the architect may generate.
            ``0`` means no limit (the model decides). Useful for test runs.

    Returns:
        Absolute path to the generated Markdown file.

    Raises:
        ValueError: If ``topic`` is empty or no chapters were completed.
    """
    if not topic.strip():
        raise ValueError("topic must not be empty")

    logger.info("[run_ebook_factory] Starting pipeline | topic: %r", topic)

    initial_state: dict[str, Any] = {"topic": topic}
    if max_chapters > 0:
        initial_state["max_chapters"] = max_chapters
    if outline:
        initial_state["outline"] = outline  # skips architect node

    result: Any = app_graph.invoke(
        initial_state,
        # Generous limit: 10 chapters × ~6 node visits × up to 3 revisions each
        {"recursion_limit": 300},
    )

    # Normalise result – LangGraph may return an EbookState or a plain dict.
    if isinstance(result, EbookState):
        completed: dict[str, str] = result.completed_chapters
        outline: list[dict] = result.outline
    else:
        completed = result.get("completed_chapters", {})
        outline = result.get("outline", [])

    if not completed:
        raise ValueError(
            "Pipeline finished without completing any chapters. "
            "Check logs for errors."
        )

    # --- Assemble chapters in outline order ---
    book_parts: list[str] = [f"# {topic}\n\n---\n"]
    for i, chapter in enumerate(outline):
        chapter_id = chapter["id"]
        title = chapter.get("title", f"Chapter {i + 1}")
        body = completed.get(chapter_id, "*(chapter not generated)*")
        # Strip any leading heading the LLM may have included to avoid duplicates.
        body_clean = re.sub(r"^[ \t]*#{1,3}[^\n]*\n+", "", body, count=1).lstrip()
        book_parts.append(f"## {i + 1}. {title}\n\n{body_clean}")

    full_book = "\n\n---\n\n".join(book_parts)

    # --- Derive a filesystem-safe filename ---
    slug = re.sub(r"[^\w\s-]", "", topic.lower()).strip()
    slug = re.sub(r"[\s-]+", "_", slug)[:60]
    output_path = Path(output_dir).resolve() / f"{slug}.md"
    output_path.write_text(full_book, encoding="utf-8")

    logger.info(
        "[run_ebook_factory] Complete. %d/%d chapters → %s",
        len(completed),
        len(outline),
        output_path,
    )
    return str(output_path)
