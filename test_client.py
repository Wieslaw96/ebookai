"""
Skrypt testowy dla app/client.py i app/tools.py.

Uruchom po uzupełnieniu .env o klucz GEMINI_API_KEY:
    poetry run python test_client.py
"""

import os
import sys


def test_imports() -> None:
    print("=== Test 1: Weryfikacja importów ===")
    from app.client import MODEL_FLASH, MODEL_PRO, get_client
    from app.tools import (
        GOOGLE_SEARCH_TOOL,
        ChapterSchema,
        OutlineSchema,
        SectionSchema,
        web_search,
    )

    print(f"  MODEL_PRO   = {MODEL_PRO}")
    print(f"  MODEL_FLASH = {MODEL_FLASH}")
    print(f"  get_client callable: {callable(get_client)}")
    print(f"  GOOGLE_SEARCH_TOOL type: {type(GOOGLE_SEARCH_TOOL).__name__}")
    print("  Importy OK\n")


def test_schemas() -> None:
    print("=== Test 2: Schematy Pydantic (OutlineSchema) ===")
    from app.tools import ChapterSchema, OutlineSchema, SectionSchema

    outline = OutlineSchema(
        title="Psychologia podejmowania decyzji",
        chapters=[
            ChapterSchema(
                id="chapter_1",
                title="Heurystyki i błędy poznawcze",
                sections=[
                    SectionSchema(id="chapter_1_section_1", title="Efekt kotwiczenia"),
                    SectionSchema(id="chapter_1_section_2", title="Heurystyka dostępności"),
                ],
                key_points=[
                    "Definicja heurystyki",
                    "Badania Tversky'ego i Kahnemana",
                    "Praktyczne konsekwencje",
                ],
            )
        ],
    )

    state_outline = outline.to_state_outline()
    assert isinstance(state_outline, list)
    assert state_outline[0]["id"] == "chapter_1"
    assert len(state_outline[0]["sections"]) == 2
    print(f"  Outline: '{outline.title}'")
    print(f"  Rozdziały: {len(state_outline)}")
    print(f"  Sekcje w rozdz. 1: {len(state_outline[0]['sections'])}")
    print("  to_state_outline() -> list[dict]: OK\n")


def test_web_search_live() -> None:
    print("=== Test 3: Live web_search() z Google Search Grounding ===")
    from app.tools import web_search

    query = "What are the key findings of Kahneman's dual-process theory of thinking?"
    print(f"  Zapytanie: {query}\n")
    result = web_search(query)

    print("--- Odpowiedź modelu ---")
    print(result)
    print("--- Koniec odpowiedzi ---\n")

    assert len(result) > 100, "Odpowiedź jest podejrzanie krótka"
    print("  Test live: OK\n")


if __name__ == "__main__":
    test_imports()
    test_schemas()

    api_key = os.getenv("GEMINI_API_KEY") or ""
    # Wczytaj z .env jeśli istnieje
    if not api_key:
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY") or ""

    if api_key:
        test_web_search_live()
    else:
        print("=== Test 3: POMINIĘTY (brak GEMINI_API_KEY w środowisku / .env) ===")
        print("  Uzupełnij plik .env i uruchom ponownie, aby przetestować web_search().\n")

    print("Wszystkie dostępne testy zakończone sukcesem.")
