import logging

from app.state import EbookState

logger = logging.getLogger(__name__)


def manager_node(state: EbookState) -> dict:
    """Initialise and validate the project state before the pipeline starts.

    Acts as the entry point of the graph. Validates that a topic is present,
    then logs a structured progress report so the operator can track the
    pipeline without inspecting the full state object.

    Args:
        state: Current graph state.

    Returns:
        Empty dict – the manager does not mutate state; it only validates
        and logs. Raises ValueError if the topic is missing.
    """
    if not state.topic.strip():
        raise ValueError(
            "EbookState.topic is empty. Set a topic before invoking the graph."
        )

    total = len(state.outline)
    done = len(state.completed_chapters)
    has_research = bool(state.research_data)

    logger.info(
        "[Manager] Project: %r | outline: %d chapters | research: %s"
        " | completed: %d/%d | current_index: %d | pending_feedback: %s",
        state.topic[:80],
        total,
        "ready" if has_research else "pending",
        done,
        max(total, 1),
        state.current_chapter_index,
        "yes" if state.feedback else "no",
    )

    return {}
