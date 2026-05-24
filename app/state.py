from typing import Any

from pydantic import BaseModel, Field


class EbookState(BaseModel):
    # Główny temat lub opis ebooka dostarczony przez użytkownika jako dane wejściowe do grafu.
    topic: str = ""

    # Materiały badawcze zebrane przez Agenta Badacza, pogrupowane tematycznie.
    # Klucz: identyfikator tematu/sekcji (np. "chapter_1_intro"),
    # wartość: lista faktów, cytatów i notatek źródłowych.
    research_data: dict[str, list[str]] = Field(default_factory=dict)

    # Struktura ebooka wygenerowana przez Agenta Architekta (Outlinera).
    # Każdy element listy reprezentuje jeden rozdział i zawiera pola:
    #   - "id": unikalny identyfikator (np. "chapter_1")
    #   - "title": tytuł rozdziału
    #   - "sections": lista podrozdziałów (każdy z własnym "id" i "title")
    #   - "key_points": lista kluczowych tez/zagadnień do omówienia w rozdziale
    outline: list[dict[str, Any]] = Field(default_factory=list)

    # Indeks rozdziału aktualnie przetwarzanego przez Agenta Pisarza (0-based).
    # Wzrasta po każdorazowym zaakceptowaniu draftu przez Agenta Weryfikatora.
    current_chapter_index: int = 0

    # Roboczy szkic aktualnie pisanej sekcji, przekazywany do Agenta Weryfikatora.
    # Resetowany do pustego stringu po zaakceptowaniu i przeniesieniu do completed_chapters.
    current_draft: str = ""

    # Uwagi i korekty od Agenta Weryfikatora dla bieżącego draftu.
    # Puste oznacza akceptację – system przechodzi do kolejnego rozdziału.
    # Niepuste oznacza, że Agent Pisarz musi przepisać sekcję z uwzględnieniem feedbacku.
    feedback: str = ""

    # Zaakceptowane rozdziały gotowe do złożenia w finalny dokument.
    # Klucz: identyfikator rozdziału (np. "chapter_1"), wartość: ostateczny tekst rozdziału.
    completed_chapters: dict[str, str] = Field(default_factory=dict)

    # Opcjonalne ograniczenie liczby rozdziałów przekazywane przez punkt wejścia.
    # 0 = brak limitu (model decyduje), >0 = dokładna liczba rozdziałów do wygenerowania.
    # Używane przez Architekta do skrócenia outline'u np. podczas testów.
    max_chapters: int = 0
