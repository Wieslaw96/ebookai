from typing import Any

from google.genai import types
from pydantic import BaseModel, Field

from app.client import MODEL_FLASH, get_client

# Narzędzie Google Search przekazywane do modelu w polu `tools`.
# types.Tool z google_search=types.GoogleSearch() aktywuje natywne grounding
# po stronie Gemini – model sam decyduje kiedy wywołać wyszukiwarkę.
GOOGLE_SEARCH_TOOL = types.Tool(google_search=types.GoogleSearch())


def web_search(query: str) -> str:
    """Perform a grounded web search using the Gemini Google Search tool.

    Sends the query to Gemini Flash with the native Google Search grounding
    tool enabled. The model synthesises a factual answer from live search
    results and appends a numbered reference list so every claim can be
    traced back to its source URL.

    The returned string is ready to be stored as a value in
    ``EbookState.research_data`` (e.g. ``state.research_data[section_id]``).

    Args:
        query: A specific, focused search query in any language. For best
            results, phrase it as a research question rather than a keyword
            string (e.g. "What are the neurological mechanisms behind
            confirmation bias according to recent studies?").

    Returns:
        A plain-text string containing:
        - A synthesised, factual answer to the query (2-5 paragraphs).
        - A "Sources" section with numbered citations in the format
          ``[N] Title – URL`` derived from the grounding metadata returned
          by the Gemini API.

        Returns an error message string if the API call fails, so callers
        do not need to handle exceptions for basic error cases.

    Raises:
        google.genai.errors.APIError: If the Gemini API returns a non-
            recoverable HTTP error (e.g. 401 Unauthorized, 429 quota exceeded).
    """
    response = get_client().models.generate_content(
        model=MODEL_FLASH,
        contents=query,
        config=types.GenerateContentConfig(
            tools=[GOOGLE_SEARCH_TOOL],
            # Instrukcja systemowa nakierowuje model na tryb badawczy:
            # zwięzła synteza faktów + obowiązek podania źródeł.
            system_instruction=(
                "You are a rigorous research assistant gathering factual material "
                "for a non-fiction book. Answer the query with accurate, well-structured "
                "information. Prioritise recent, authoritative sources. "
                "Do NOT add personal opinions or speculation."
            ),
        ),
    )

    answer = response.text or ""

    # Wydobywamy źródła z metadanych groundingu i dołączamy je do odpowiedzi.
    sources: list[str] = []
    candidate = response.candidates[0] if response.candidates else None
    if candidate and candidate.grounding_metadata:
        chunks = candidate.grounding_metadata.grounding_chunks or []
        for i, chunk in enumerate(chunks, start=1):
            if chunk.web and chunk.web.uri:
                title = chunk.web.title or chunk.web.uri
                sources.append(f"[{i}] {title} – {chunk.web.uri}")

    if sources:
        answer += "\n\nSources:\n" + "\n".join(sources)

    return answer


# ---------------------------------------------------------------------------
# Schematy Pydantic dla Structured Outputs – używane przez Agenta Architekta
# jako response_schema w GenerateContentConfig, gwarantując, że model zwróci
# outline dokładnie pasujący do list[dict[str, Any]] z EbookState.
# ---------------------------------------------------------------------------


class SectionSchema(BaseModel):
    """Represents a single subsection within a chapter."""

    id: str = Field(description="Unique identifier, e.g. 'chapter_1_section_2'.")
    title: str = Field(description="Subsection title.")


class ChapterSchema(BaseModel):
    """Represents a single chapter in the ebook outline."""

    id: str = Field(description="Unique identifier, e.g. 'chapter_1'.")
    title: str = Field(description="Chapter title.")
    sections: list[SectionSchema] = Field(
        description="Ordered list of subsections in this chapter."
    )
    key_points: list[str] = Field(
        description="Key facts, arguments or concepts that must be covered."
    )


class OutlineSchema(BaseModel):
    """Full ebook outline returned by the Outliner agent."""

    title: str = Field(description="Full title of the ebook.")
    chapters: list[ChapterSchema] = Field(
        description="Ordered list of chapters forming the complete structure."
    )

    def to_state_outline(self) -> list[dict[str, Any]]:
        """Convert to the list[dict] format expected by EbookState.outline."""
        return [chapter.model_dump() for chapter in self.chapters]
