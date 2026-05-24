import logging

from app.state import EbookState
from app.tools import web_search

logger = logging.getLogger(__name__)

# Number of broad queries fired before an outline exists.
_INITIAL_QUERY_COUNT = 4


def researcher_node(state: EbookState) -> dict:
    """Gather factual research material and store it in state.research_data.

    Operates in two modes depending on pipeline phase:

    * **Pre-outline** – fires broad queries covering the topic from multiple
      angles (history, theory, recent findings, controversies). Results are
      stored under keys ``initial_0`` … ``initial_N``.

    * **Post-outline** – fires one focused query per chapter, combining its
      title and key_points into a precise research question. Results are
      stored under the chapter's ``id`` key. Already-researched chapters are
      skipped to avoid redundant API calls.

    Args:
        state: Current graph state. Uses ``state.topic``, ``state.outline``,
            and ``state.research_data``.

    Returns:
        Dict with the updated ``research_data`` field (existing entries
        preserved, new ones merged in).
    """
    updated: dict[str, list[str]] = dict(state.research_data)

    if state.outline:
        _research_by_chapter(state, updated)
    else:
        _research_initial(state, updated)

    return {"research_data": updated}


def _research_initial(state: EbookState, target: dict[str, list[str]]) -> None:
    """Broad topic research executed before the outline is available."""
    queries = [
        f"Overview, history and foundational principles of: {state.topic}",
        f"Key theories, frameworks and leading expert opinions on: {state.topic}",
        f"Recent research findings and real-world applications of: {state.topic}",
        f"Common misconceptions, controversies and open questions about: {state.topic}",
    ]
    for i, query in enumerate(queries[:_INITIAL_QUERY_COUNT]):
        key = f"initial_{i}"
        if key in target:
            logger.debug("[Researcher] Skipping already-cached key: %s", key)
            continue
        logger.info("[Researcher] Initial query %d/%d: %r", i + 1, len(queries), query[:80])
        target[key] = [web_search(query)]


def _research_by_chapter(state: EbookState, target: dict[str, list[str]]) -> None:
    """Targeted research, one query per outline chapter."""
    for chapter in state.outline:
        chapter_id: str = chapter["id"]
        if chapter_id in target:
            logger.debug("[Researcher] Chapter already researched: %s", chapter_id)
            continue

        title: str = chapter.get("title", chapter_id)
        key_points: list[str] = chapter.get("key_points", [])
        points_str = "; ".join(key_points) if key_points else title

        query = (
            f"Detailed, factual research for a non-fiction book chapter titled "
            f"'{title}'. Topics to cover: {points_str}. "
            f"Overall book subject: {state.topic}"
        )

        logger.info("[Researcher] Researching chapter: %r", title[:60])
        target[chapter_id] = [web_search(query)]
