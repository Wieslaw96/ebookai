"""
app/ui.py – Streamlit Web UI for EbookAI.

Run with:
    poetry run streamlit run app/ui.py
"""

# ── Ensure project root is on sys.path when Streamlit runs ui.py directly ─
import sys as _sys
import os as _os
_PROJECT_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _PROJECT_ROOT not in _sys.path:
    _sys.path.insert(0, _PROJECT_ROOT)

# ── Environment must be loaded before any app.* import ────────────────────
import logging
import os
import queue as _queue_mod
import traceback
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── Streamlit (page config must be the very first st call) ─────────────────
import streamlit as st

st.set_page_config(
    page_title="Fabryka Ebooków AI",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── Silence noisy third-party loggers at import time ──────────────────────
for _lib in ("httpx", "httpcore", "google", "langgraph", "urllib3", "asyncio"):
    logging.getLogger(_lib).setLevel(logging.WARNING)


# ══════════════════════════════════════════════════════════════════════════════
# Log streaming infrastructure
# ══════════════════════════════════════════════════════════════════════════════


class _QueueHandler(logging.Handler):
    """Thread-safe logging handler: pushes formatted records into a Queue."""

    def __init__(self, q: "_queue_mod.Queue[str]") -> None:
        super().__init__()
        self.q = q

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.q.put_nowait(self.format(record))
        except _queue_mod.Full:
            pass


def _drain(q: "_queue_mod.Queue[str]", target: list) -> bool:
    changed = False
    while True:
        try:
            target.append(q.get_nowait())
            changed = True
        except _queue_mod.Empty:
            break
    return changed


# ══════════════════════════════════════════════════════════════════════════════
# Pipeline runner
# ══════════════════════════════════════════════════════════════════════════════


def _execute_pipeline(
    topic: str,
    max_chapters: int,
    log_placeholder: "st.delta_generator.DeltaGenerator",
    outline: list[dict] | None = None,
) -> tuple[str | None, str | None]:
    from app.graph import run_ebook_factory

    log_q: "_queue_mod.Queue[str]" = _queue_mod.Queue(maxsize=2_000)
    handler = _QueueHandler(log_q)
    handler.setFormatter(
        logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
    )
    app_logger = logging.getLogger("app")
    app_logger.setLevel(logging.INFO)
    app_logger.addHandler(handler)

    path: str | None = None
    error: str | None = None
    try:
        path = run_ebook_factory(
            topic=topic,
            output_dir=".",
            max_chapters=max_chapters,
            outline=outline,
        )
    except Exception:
        error = traceback.format_exc()
    finally:
        app_logger.removeHandler(handler)

    log_lines: list[str] = []
    _drain(log_q, log_lines)
    if log_lines:
        log_placeholder.code("\n".join(log_lines), language=None)

    return path, error


# ══════════════════════════════════════════════════════════════════════════════
# Session state
# ══════════════════════════════════════════════════════════════════════════════


def _init_session() -> None:
    defaults: dict = {
        "stage": "input",        # input | titles | outline | generating | done
        "topic": "",
        "max_chapters": 2,
        "generated_titles": [],
        "selected_title": "",
        "generated_outline": [],
        "ebook_result": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def _reset() -> None:
    for key in list(st.session_state.keys()):
        del st.session_state[key]


# ══════════════════════════════════════════════════════════════════════════════
# Stage: input
# ══════════════════════════════════════════════════════════════════════════════


def _stage_input() -> None:
    topic = st.text_area(
        label="📚 Temat lub opis ebooka",
        placeholder="np. Krótka historia i ewolucja kodu kreskowego",
        height=110,
        help="Im bardziej szczegółowy opis, tym trafniejszy research i outline.",
    )

    col_slide, col_badge = st.columns([3, 1])
    with col_slide:
        max_chapters = st.slider(
            label="Liczba rozdziałów",
            min_value=0,
            max_value=10,
            value=2,
            help=(
                "**0** = brak limitu (model sam decyduje).  \n"
                "**1–3** = tryb testowy.  \n"
                "**4–10** = tryb produkcyjny."
            ),
        )
    with col_badge:
        if max_chapters == 0:
            badge_val, badge_delta = "Auto", "bez limitu"
        elif max_chapters <= 3:
            badge_val, badge_delta = "Testowy", f"{max_chapters} rozdz."
        else:
            badge_val, badge_delta = "Produkcja", f"{max_chapters} rozdz."
        st.metric("Tryb", badge_val, badge_delta)

    st.divider()

    if st.button(
        "💡 Zaproponuj tytuły",
        type="primary",
        use_container_width=True,
        disabled=not topic.strip(),
    ):
        with st.spinner("Generuję 5 propozycji tytułów…"):
            from app.proposals import generate_titles
            titles = generate_titles(topic.strip())
        st.session_state.topic = topic.strip()
        st.session_state.max_chapters = max_chapters
        st.session_state.generated_titles = titles
        st.session_state.stage = "titles"
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# Stage: titles
# ══════════════════════════════════════════════════════════════════════════════


def _stage_titles() -> None:
    st.subheader("Krok 1 z 2 — Wybierz tytuł ebooka")
    st.caption(f"Temat: *{st.session_state.topic}*")
    st.divider()

    selected = st.radio(
        "Propozycje tytułów:",
        st.session_state.generated_titles,
        index=0,
    )

    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        if st.button("← Zmień temat", use_container_width=True):
            st.session_state.stage = "input"
            st.rerun()

    with col2:
        if st.button(
            "Wybierz i generuj rozdziały →",
            type="primary",
            use_container_width=True,
        ):
            with st.spinner("Tworzę propozycję rozdziałów…"):
                from app.proposals import generate_outline
                outline = generate_outline(
                    title=selected,
                    topic=st.session_state.topic,
                    max_chapters=st.session_state.max_chapters,
                )
            st.session_state.selected_title = selected
            st.session_state.generated_outline = outline
            st.session_state.stage = "outline"
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# Stage: outline
# ══════════════════════════════════════════════════════════════════════════════


def _stage_outline() -> None:
    st.subheader("Krok 2 z 2 — Zatwierdź spis treści")
    st.markdown(f"**Tytuł:** {st.session_state.selected_title}")
    st.divider()

    for i, chapter in enumerate(st.session_state.generated_outline):
        st.markdown(f"**{i + 1}. {chapter['title']}**")
        for section in chapter.get("sections", []):
            st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;• {section['title']}")
        st.write("")

    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔄 Zaproponuj inne rozdziały", use_container_width=True):
            with st.spinner("Generuję nowy spis treści…"):
                from app.proposals import generate_outline
                new_outline = generate_outline(
                    title=st.session_state.selected_title,
                    topic=st.session_state.topic,
                    max_chapters=st.session_state.max_chapters,
                )
            st.session_state.generated_outline = new_outline
            st.rerun()

    with col2:
        if st.button(
            "✅ Zatwierdź i pisz ebook",
            type="primary",
            use_container_width=True,
        ):
            st.session_state.stage = "generating"
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# Stage: generating
# ══════════════════════════════════════════════════════════════════════════════


def _stage_generating() -> None:
    st.subheader("📡 Logi agentów")
    st.caption(
        "Każda linia = jeden krok agenta. "
        "Weryfikator może odesłać rozdział do poprawek — to normalne."
    )
    log_placeholder = st.empty()

    with st.spinner("Agenci pracują… research → pisanie → weryfikacja"):
        output_path, error = _execute_pipeline(
            topic=st.session_state.selected_title,
            max_chapters=st.session_state.max_chapters,
            log_placeholder=log_placeholder,
            outline=st.session_state.generated_outline,
        )

    if error:
        st.error(f"**Pipeline zakończył się błędem.**\n\n```\n{error}\n```")
        if st.button("← Wróć do spisu treści"):
            st.session_state.stage = "outline"
            st.rerun()
        return

    if output_path:
        content = Path(output_path).read_text(encoding="utf-8")
        from app.pdf_utils import markdown_to_pdf_bytes
        try:
            pdf_bytes: bytes | None = markdown_to_pdf_bytes(content)
        except Exception:
            pdf_bytes = None
        st.session_state.ebook_result = {
            "path": output_path,
            "filename": Path(output_path).name,
            "content": content,
            "pdf_bytes": pdf_bytes,
            "topic": st.session_state.selected_title,
        }
        st.session_state.stage = "done"
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# Stage: done
# ══════════════════════════════════════════════════════════════════════════════


def _stage_done() -> None:
    result = st.session_state.ebook_result
    st.divider()
    st.success(f"✅ Ebook **\"{result['topic']}\"** wygenerowany pomyślnie!")

    content: str = result["content"]
    word_count = len(content.split())
    size_kb = len(content.encode("utf-8")) / 1024

    c1, c2, c3 = st.columns(3)
    c1.metric("Słowa", f"~{word_count:,}")
    c2.metric("Rozmiar", f"{size_kb:.1f} KB")
    c3.metric("Plik", result["filename"])

    col_md, col_pdf = st.columns(2)
    with col_md:
        st.download_button(
            label="📥 Pobierz (.md)",
            data=content,
            file_name=result["filename"],
            mime="text/markdown",
            use_container_width=True,
        )
    with col_pdf:
        pdf_bytes = result.get("pdf_bytes")
        if pdf_bytes:
            st.download_button(
                label="📄 Pobierz (.pdf)",
                data=pdf_bytes,
                file_name=result["filename"].replace(".md", ".pdf"),
                mime="application/pdf",
                use_container_width=True,
                type="primary",
            )
        else:
            st.button("📄 PDF niedostępny", disabled=True, use_container_width=True)

    with st.expander("👁 Podgląd ebooka"):
        preview = content[:4_000]
        if len(content) > 4_000:
            preview += "\n\n*… (skrócono dla podglądu)*"
        st.markdown(preview)

    st.divider()
    if st.button("🔄 Wygeneruj nowy ebook", use_container_width=True):
        _reset()
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════


def main() -> None:
    _init_session()

    st.title("🤖 Fabryka Ebooków Non-Fiction")
    st.caption(
        "Wieloagentowy system AI: "
        "**Tytuł** → **Rozdziały** → **Research** → **Pisanie** → **Weryfikacja**"
    )
    st.divider()

    if not os.getenv("GEMINI_API_KEY", "").strip():
        st.warning(
            "**Brak klucza GEMINI_API_KEY.**\n\n"
            "1. Skopiuj `.env.example` → `.env`\n"
            "2. Wpisz: `GEMINI_API_KEY=twój_klucz_tu`\n"
            "3. Zrestartuj aplikację."
        )
        st.stop()

    stage = st.session_state.stage

    if stage == "input":
        _stage_input()
    elif stage == "titles":
        _stage_titles()
    elif stage == "outline":
        _stage_outline()
    elif stage == "generating":
        _stage_generating()
    elif stage == "done":
        _stage_done()


main()
