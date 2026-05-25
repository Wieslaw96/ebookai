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

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D102
        try:
            self.q.put_nowait(self.format(record))
        except _queue_mod.Full:
            pass


def _drain(q: "_queue_mod.Queue[str]", target: list) -> bool:
    """Move all available items from *q* into *target*. Returns True if any."""
    changed = False
    while True:
        try:
            target.append(q.get_nowait())
            changed = True
        except _queue_mod.Empty:
            break
    return changed


# ══════════════════════════════════════════════════════════════════════════════
# Pipeline runner (called from the Streamlit main thread)
# ══════════════════════════════════════════════════════════════════════════════


def _execute_pipeline(
    topic: str,
    max_chapters: int,
    log_placeholder: "st.delta_generator.DeltaGenerator",
) -> tuple[str | None, str | None]:
    """Run ``run_ebook_factory`` in the main Streamlit thread.

    Logs are captured into a queue and displayed all at once when the
    pipeline finishes.  Running directly in the main thread avoids the
    sleep-poll loop that froze Streamlit's render cycle on Windows.

    Args:
        topic:           The ebook subject.
        max_chapters:    Chapter cap (0 = unlimited).
        log_placeholder: ``st.empty()`` element for log output.

    Returns:
        ``(output_path, None)`` on success or ``(None, traceback_str)`` on
        error.
    """
    from app.graph import run_ebook_factory  # noqa: PLC0415

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
        path = run_ebook_factory(topic=topic, output_dir=".", max_chapters=max_chapters)
    except Exception:  # noqa: BLE001
        error = traceback.format_exc()
    finally:
        app_logger.removeHandler(handler)

    log_lines: list[str] = []
    _drain(log_q, log_lines)
    if log_lines:
        log_placeholder.code("\n".join(log_lines), language=None)

    return path, error


# ══════════════════════════════════════════════════════════════════════════════
# UI
# ══════════════════════════════════════════════════════════════════════════════


def _init_session() -> None:
    defaults = {"ebook_result": None, "running": False}
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def _show_result(result: dict) -> None:
    """Render the success panel and download button."""
    st.divider()
    st.success(f"✅ Ebook **{result['topic']!r}** wygenerowany pomyślnie!")

    content: str = result["content"]
    word_count = len(content.split())
    size_kb = len(content.encode("utf-8")) / 1024

    c1, c2, c3 = st.columns(3)
    c1.metric("Słowa", f"~{word_count:,}")
    c2.metric("Rozmiar", f"{size_kb:.1f} KB")
    c3.metric("Plik", result["filename"])

    st.download_button(
        label="📥 Pobierz ebook (.md)",
        data=content,
        file_name=result["filename"],
        mime="text/markdown",
        use_container_width=True,
        type="primary",
    )

    with st.expander("👁 Podgląd ebooka"):
        preview = content[:4_000]
        if len(content) > 4_000:
            preview += "\n\n*… (skrócono dla podglądu)*"
        st.markdown(preview)


def main() -> None:  # noqa: C901
    _init_session()

    # ── Header ────────────────────────────────────────────────────────────
    st.title("🤖 Fabryka Ebooków Non-Fiction")
    st.caption(
        "Wieloagentowy system AI: "
        "**Research** → **Outline** → **Pisanie** → **Weryfikacja**"
    )
    st.divider()

    # ── API key guard ─────────────────────────────────────────────────────
    if not os.getenv("GEMINI_API_KEY", "").strip():
        st.warning(
            "**Brak klucza GEMINI_API_KEY.**\n\n"
            "1. Skopiuj `.env.example` → `.env`\n"
            "2. Wpisz: `GEMINI_API_KEY=twój_klucz_tu`\n"
            "3. Zrestartuj aplikację (`Ctrl+C`, potem `poetry run streamlit run app/ui.py`)."
        )
        st.stop()

    # ── Controls ──────────────────────────────────────────────────────────
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
                "**0** = brak limitu (model sam decyduje — może wygenerować 8–12).  \n"
                "**1–3** = tryb testowy, szybkie generowanie.  \n"
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

    btn_disabled = not topic.strip() or st.session_state.running
    btn_label = "⏳ Trwa generowanie..." if st.session_state.running else "🚀 Uruchom produkcję"

    clicked = st.button(
        btn_label,
        type="primary",
        use_container_width=True,
        disabled=btn_disabled,
    )

    # ── Pipeline execution ────────────────────────────────────────────────
    if clicked and topic.strip():
        st.session_state.running = True
        st.session_state.ebook_result = None

        st.subheader("📡 Logi agentów (na żywo)")
        st.caption(
            "Każda linia = jeden krok agenta. "
            "Weryfikator może odesłać rozdział do poprawek — to normalne."
        )
        log_placeholder = st.empty()

        with st.spinner(
            "Agenci pracują… research → outline → pisanie → weryfikacja"
        ):
            output_path, error = _execute_pipeline(
                topic.strip(), max_chapters, log_placeholder
            )

        st.session_state.running = False

        if error:
            st.error(
                "**Pipeline zakończył się błędem.**\n\n"
                f"```\n{error}\n```"
            )
        elif output_path:
            content = Path(output_path).read_text(encoding="utf-8")
            st.session_state.ebook_result = {
                "path": output_path,
                "filename": Path(output_path).name,
                "content": content,
                "topic": topic.strip(),
            }

    # ── Persistent result panel ───────────────────────────────────────────
    if st.session_state.ebook_result:
        _show_result(st.session_state.ebook_result)


main()
