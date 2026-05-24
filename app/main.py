"""
app/main.py – Entry point for the EbookAI multi-agent generation system.

Usage:
    poetry run python app/main.py

Requires GEMINI_API_KEY to be set in a .env file (copy from .env.example).
"""

import logging
import os
import sys
from pathlib import Path

# Ensure project root is importable when running as `python app/main.py`
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ── Load .env before any app import so get_client() finds the key ─────────
from dotenv import load_dotenv

load_dotenv()


# ── Logging setup ──────────────────────────────────────────────────────────

def _setup_logging() -> None:
    """Configure console logging: verbose for our agents, silent for libraries."""
    # Suppress noisy third-party loggers
    for noisy in ("httpx", "httpcore", "google", "langgraph", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    fmt = logging.Formatter(
        fmt="[%(asctime)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(fmt)

    # Route only our `app.*` loggers through this handler
    app_logger = logging.getLogger("app")
    app_logger.setLevel(logging.INFO)
    app_logger.addHandler(handler)
    app_logger.propagate = False


# ── API-key guard ──────────────────────────────────────────────────────────

def _check_api_key() -> None:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        print(
            "\n[BŁĄD] Brak klucza GEMINI_API_KEY w środowisku.\n"
            "  1. Skopiuj plik .env.example → .env\n"
            "  2. Uzupełnij: GEMINI_API_KEY=twój_klucz\n"
            "  3. Uruchom ponownie.\n"
        )
        sys.exit(1)


# ── Markdown assembly helper ───────────────────────────────────────────────

def _assemble_markdown(
    topic: str,
    outline: list[dict],
    completed: dict[str, str],
) -> str:
    """Compose the final book document from completed chapters.

    Chapters are placed in outline order.  Missing chapters (if any) are
    marked with a placeholder so the document structure is always complete.

    Args:
        topic:     Book title / topic string.
        outline:   Ordered list of chapter dicts from ``EbookState.outline``.
        completed: Accepted chapter texts from ``EbookState.completed_chapters``.

    Returns:
        Full Markdown string ready to write to disk.
    """
    lines: list[str] = [
        f"# {topic}",
        "",
        "> *Wygenerowano automatycznie przez system EbookAI*",
        "",
        "---",
        "",
        "## Spis treści",
        "",
    ]

    # Table of contents
    for i, ch in enumerate(outline):
        title = ch.get("title", f"Rozdział {i + 1}")
        lines.append(f"{i + 1}. {title}")

    lines += ["", "---", ""]

    # Chapter bodies
    for i, ch in enumerate(outline):
        chapter_id = ch["id"]
        title = ch.get("title", f"Rozdział {i + 1}")
        body = completed.get(chapter_id, "*(rozdział nie został wygenerowany)*")

        lines += [
            f"## Rozdział {i + 1}: {title}",
            "",
            body,
            "",
            "---",
            "",
        ]

    return "\n".join(lines)


# ── Main ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _setup_logging()
    _check_api_key()

    # Delayed import: graph compilation and client init happen only when running
    from app.graph import app_graph, run_ebook_factory

    # ── Test configuration ─────────────────────────────────────────────────
    TOPIC = "Krótka historia i ewolucja kodu kreskowego"
    MAX_CHAPTERS = 2        # keeps the test fast and economical
    OUTPUT_DIR = str(Path(__file__).parent.parent)  # project root

    # ── Banner ─────────────────────────────────────────────────────────────
    print()
    print("=" * 62)
    print("  EbookAI – Wieloagentowy system generowania ebooków")
    print("=" * 62)
    print(f"  Temat       : {TOPIC}")
    print(f"  Rozdzialy   : max {MAX_CHAPTERS} (tryb testowy)")
    print(f"  Katalog wyj.: {OUTPUT_DIR}")
    print("=" * 62)
    print()

    # ── Run pipeline ───────────────────────────────────────────────────────
    output_path_str = run_ebook_factory(
        topic=TOPIC,
        output_dir=OUTPUT_DIR,
        max_chapters=MAX_CHAPTERS,
    )

    # ── Summary ────────────────────────────────────────────────────────────
    output_path = Path(output_path_str)
    content = output_path.read_text(encoding="utf-8")
    word_count = len(content.split())
    size_kb = output_path.stat().st_size / 1024

    print()
    print("=" * 62)
    print("  Ebook wygenerowany pomyslnie!")
    print(f"  Plik    : {output_path.name}")
    print(f"  Slowa   : ~{word_count:,}")
    print(f"  Rozmiar : {size_kb:.1f} KB")
    print(f"  Sciezka : {output_path.resolve()}")
    print("=" * 62)
    print()
