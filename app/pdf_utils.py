import io
import os
import re

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

_DEJAVU_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
_DEJAVU_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _setup_fonts() -> tuple[str, str]:
    """Register DejaVu (full Unicode incl. Polish) when available on Linux."""
    if os.path.exists(_DEJAVU_REGULAR) and os.path.exists(_DEJAVU_BOLD):
        pdfmetrics.registerFont(TTFont("DejaVuSans", _DEJAVU_REGULAR))
        pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", _DEJAVU_BOLD))
        return "DejaVuSans", "DejaVuSans-Bold"
    return "Helvetica", "Helvetica-Bold"


def _escape_xml(text: str) -> str:
    """Escape characters that ReportLab's Paragraph XML parser would choke on."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _inline_markup(text: str) -> str:
    """Convert **bold** and *italic* Markdown to ReportLab XML tags."""
    text = _escape_xml(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    return text


def markdown_to_pdf_bytes(content: str) -> bytes:
    """Convert a Markdown ebook string to PDF bytes using ReportLab.

    Handles: # h1, ## h2, --- horizontal rules, paragraphs, **bold**, *italic*.
    Uses DejaVu Sans on Linux (Streamlit Cloud) for full Unicode / Polish support,
    falls back to Helvetica on other platforms.
    """
    font_regular, font_bold = _setup_fonts()

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "EbookTitle",
        parent=styles["Normal"],
        fontName=font_bold,
        fontSize=22,
        leading=28,
        spaceAfter=14,
        textColor=colors.HexColor("#1a1a2e"),
    )
    h2_style = ParagraphStyle(
        "EbookH2",
        parent=styles["Normal"],
        fontName=font_bold,
        fontSize=14,
        leading=18,
        spaceBefore=18,
        spaceAfter=8,
        textColor=colors.HexColor("#16213e"),
    )
    body_style = ParagraphStyle(
        "EbookBody",
        parent=styles["Normal"],
        fontName=font_regular,
        fontSize=11,
        leading=17,
        spaceAfter=7,
    )

    story = []
    para_lines: list[str] = []

    def flush_para() -> None:
        if para_lines:
            text = _inline_markup(" ".join(para_lines))
            story.append(Paragraph(text, body_style))
            para_lines.clear()

    for raw_line in content.splitlines():
        line = raw_line.rstrip()

        if line.startswith("# "):
            flush_para()
            story.append(Paragraph(_escape_xml(line[2:]), title_style))

        elif line.startswith("## "):
            flush_para()
            story.append(Paragraph(_escape_xml(line[3:]), h2_style))

        elif line == "---":
            flush_para()
            story.append(Spacer(1, 0.25 * cm))
            story.append(
                HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc"))
            )
            story.append(Spacer(1, 0.25 * cm))

        elif line.strip():
            para_lines.append(line.strip())

        else:
            flush_para()

    flush_para()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2.5 * cm,
        rightMargin=2.5 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
        title=content.splitlines()[0].lstrip("# ") if content else "Ebook",
    )
    doc.build(story)
    return buffer.getvalue()
