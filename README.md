# EbookAI

Wieloagentowy system do generowania długich ebooków non-fiction (100–200 stron) oparty na rzeczywistej wiedzy pobranej ze źródeł sieciowych.

## Stack techniczny

- **Backend:** [LangGraph](https://github.com/langchain-ai/langgraph) — orkiestracja grafu agentów
- **Model AI:** Google Gemini (przez `google-genai` SDK) z wyszukiwaniem Google Search Grounding
- **Frontend:** [Streamlit](https://streamlit.io) — interfejs webowy z live logowaniem
- **Walidacja danych:** Pydantic v2

## Architektura agentów

```
START → Manager → Researcher
                      ↓ (brak outline)
                  Architect → Researcher (per-chapter loop)
                      ↓ (outline gotowy)
                   Writer → Verifier
                               ↓ (REVISION_NEEDED)
                            Writer (rewizja)
                               ↓ (APPROVED + więcej rozdziałów)
                            Researcher → Writer
                               ↓ (APPROVED + koniec)
                             END
```

## Uruchomienie lokalne

**Wymagania:** Python 3.12+, klucz API Gemini

```bash
# 1. Zainstaluj zależności
pip install -r requirements.txt

# 2. Skonfiguruj klucz API
cp .env.example .env
# Edytuj .env i wklej swój GEMINI_API_KEY

# 3. Uruchom interfejs webowy
streamlit run app/ui.py
```

Aplikacja będzie dostępna pod adresem `http://localhost:8501`.

## Wdrożenie na Streamlit Community Cloud

1. Sforkuj lub wypchnij to repozytorium na GitHub
2. Wejdź na [share.streamlit.io](https://share.streamlit.io)
3. Połącz repozytorium, ustaw `app/ui.py` jako główny plik
4. W ustawieniach aplikacji dodaj sekret: `GEMINI_API_KEY = "twój_klucz"`
