"""Render the project's Markdown documentation to PDF.

Written for this project rather than adopting a converter, because the
alternatives either need a headless browser (heavy, and awkward on Windows) or
a LaTeX toolchain. This is estimation mitigation M4: it cost 1.5 hours, it is
reusable, and unlike hand-formatting in a word processor it keeps a single
source of truth in `docs/*.md`.

Supports the Markdown subset the documents actually use: headings, paragraphs,
bullet and numbered lists, tables, fenced code, block quotes, horizontal rules,
images (including SVG), and inline bold/italic/code/links.

    python tools/md2pdf.py                 # render everything to Submission/
    python tools/md2pdf.py docs/SRS.md     # render one file
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
OUT = ROOT / "Submission"

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm
CONTENT_W = PAGE_W - 2 * MARGIN

INK = colors.HexColor("#202124")
MUTED = colors.HexColor("#5f6368")
RULE = colors.HexColor("#dadce0")
ACCENT = colors.HexColor("#1a73e8")
CODE_BG = colors.HexColor("#f5f6f8")
HEAD_BG = colors.HexColor("#eef1f5")
ZEBRA = colors.HexColor("#fafbfc")


# ---------------------------------------------------------------------------
# Fonts. The documents use arrows, set membership, superscripts and dashes, so
# a Unicode TrueType face is registered where one is available; the built-in
# Type 1 faces would drop those glyphs silently.
# ---------------------------------------------------------------------------

def register_fonts() -> tuple[str, str, str, str]:
    candidates = [
        ("Body", "arial.ttf", "arialbd.ttf", "ariali.ttf", "arialbi.ttf"),
        ("Body", "DejaVuSans.ttf", "DejaVuSans-Bold.ttf",
         "DejaVuSans-Oblique.ttf", "DejaVuSans-BoldOblique.ttf"),
        ("Body", "segoeui.ttf", "segoeuib.ttf", "segoeuii.ttf", "segoeuiz.ttf"),
    ]
    font_dirs = [Path("C:/Windows/Fonts"), Path("/usr/share/fonts/truetype/dejavu"),
                 Path("/Library/Fonts"), Path("/usr/share/fonts")]

    for name, regular, bold, italic, bolditalic in candidates:
        for directory in font_dirs:
            path = directory / regular
            if not path.exists():
                continue
            try:
                pdfmetrics.registerFont(TTFont(name, str(path)))
                for suffix, filename in (("-B", bold), ("-I", italic), ("-BI", bolditalic)):
                    candidate = directory / filename
                    pdfmetrics.registerFont(
                        TTFont(name + suffix, str(candidate if candidate.exists() else path)))
                pdfmetrics.registerFontFamily(
                    name, normal=name, bold=name + "-B", italic=name + "-I",
                    boldItalic=name + "-BI")

                mono = "Mono"
                for mono_file in ("consola.ttf", "DejaVuSansMono.ttf", "cour.ttf"):
                    mono_path = directory / mono_file
                    if mono_path.exists():
                        pdfmetrics.registerFont(TTFont(mono, str(mono_path)))
                        bold_mono = {"consola.ttf": "consolab.ttf",
                                     "DejaVuSansMono.ttf": "DejaVuSansMono-Bold.ttf",
                                     "cour.ttf": "courbd.ttf"}[mono_file]
                        bold_path = directory / bold_mono
                        pdfmetrics.registerFont(
                            TTFont(mono + "-B", str(bold_path if bold_path.exists() else mono_path)))
                        pdfmetrics.registerFontFamily(mono, normal=mono, bold=mono + "-B",
                                                      italic=mono, boldItalic=mono + "-B")
                        return name, name + "-B", name + "-I", mono
                return name, name + "-B", name + "-I", "Courier"
            except Exception:  # noqa: BLE001 - fall through to the next candidate
                continue

    return "Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Courier"


BODY, BODY_B, BODY_I, MONO = register_fonts()

# Glyphs that even a Unicode face may lack in a given install.
GLYPH_FALLBACK = {"⦿": "(*)", "⁹": "^9", "⇒": "=>"}


def styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()["BodyText"]
    common = dict(fontName=BODY, textColor=INK, alignment=TA_LEFT)
    return {
        "body": ParagraphStyle("body", parent=base, fontSize=9.6, leading=14.2,
                               spaceAfter=6, **common),
        "h1": ParagraphStyle("h1", parent=base, fontName=BODY_B, fontSize=19, leading=23,
                             spaceBefore=6, spaceAfter=10, textColor=INK),
        "h2": ParagraphStyle("h2", parent=base, fontName=BODY_B, fontSize=14.5, leading=18,
                             spaceBefore=15, spaceAfter=7, textColor=ACCENT),
        "h3": ParagraphStyle("h3", parent=base, fontName=BODY_B, fontSize=11.6, leading=15,
                             spaceBefore=11, spaceAfter=5, textColor=INK),
        "h4": ParagraphStyle("h4", parent=base, fontName=BODY_B, fontSize=10.2, leading=13.5,
                             spaceBefore=9, spaceAfter=4, textColor=MUTED),
        "bullet": ParagraphStyle("bullet", parent=base, fontSize=9.6, leading=13.8,
                                 spaceAfter=3, leftIndent=12, bulletIndent=3, **common),
        "number": ParagraphStyle("number", parent=base, fontSize=9.6, leading=13.8,
                                 spaceAfter=3, leftIndent=16, bulletIndent=3, **common),
        "quote": ParagraphStyle("quote", parent=base, fontSize=9.6, leading=14,
                                leftIndent=12, rightIndent=6, spaceBefore=5, spaceAfter=7,
                                borderPadding=(6, 6, 6, 8), backColor=colors.HexColor("#fef7e0"),
                                borderColor=colors.HexColor("#b06000"), borderWidth=0,
                                **common),
        "code": ParagraphStyle("code", parent=base, fontName=MONO, fontSize=7.6, leading=10.2,
                               textColor=INK, backColor=CODE_BG, borderPadding=(5, 5, 5, 6),
                               spaceBefore=4, spaceAfter=8),
        "cell": ParagraphStyle("cell", parent=base, fontSize=8.1, leading=10.8,
                               spaceAfter=0, **common),
        "cellhead": ParagraphStyle("cellhead", parent=base, fontName=BODY_B, fontSize=8.1,
                                   leading=10.8, spaceAfter=0, textColor=INK),
        "caption": ParagraphStyle("caption", parent=base, fontSize=8.2, leading=11,
                                  textColor=MUTED, spaceBefore=3, spaceAfter=10,
                                  alignment=1, fontName=BODY_I),
        "title": ParagraphStyle("title", parent=base, fontName=BODY_B, fontSize=26, leading=31,
                                alignment=1, textColor=INK, spaceAfter=8),
        "subtitle": ParagraphStyle("subtitle", parent=base, fontSize=13, leading=18,
                                   alignment=1, textColor=MUTED, spaceAfter=26),
        "meta": ParagraphStyle("meta", parent=base, fontSize=9.6, leading=15,
                               alignment=1, textColor=INK),
    }


S = styles()


# ---------------------------------------------------------------------------
# Inline formatting
# ---------------------------------------------------------------------------

_CODE = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*(.+?)\*\*", re.S)
_ITALIC = re.compile(r"(?<![\*\w])\*([^*\n]+?)\*(?!\*)")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def inline(text: str) -> str:
    """Convert an inline Markdown run to ReportLab's mini-HTML."""
    for bad, good in GLYPH_FALLBACK.items():
        text = text.replace(bad, good)

    # Protect code spans from the other transforms.
    spans: list[str] = []

    def stash(match: re.Match) -> str:
        spans.append(match.group(1))
        return f"\x00{len(spans) - 1}\x00"

    text = _CODE.sub(stash, text)
    text = html.escape(text, quote=False)
    text = _LINK.sub(
        lambda m: f'<a href="{html.escape(m.group(2), quote=True)}" color="#1a73e8">{m.group(1)}</a>',
        text)
    text = _BOLD.sub(lambda m: f"<b>{m.group(1)}</b>", text)
    text = _ITALIC.sub(lambda m: f"<i>{m.group(1)}</i>", text)

    def restore(match: re.Match) -> str:
        code = html.escape(spans[int(match.group(1))], quote=False)
        return (f'<font face="{MONO}" size="8.4" backColor="#f1f3f4">\u2009{code}\u2009</font>')

    return re.sub(r"\x00(\d+)\x00", restore, text)


# ---------------------------------------------------------------------------
# Block parsing
# ---------------------------------------------------------------------------

@dataclass
class Doc:
    title: str
    subtitle: str
    flowables: list


def svg_flowable(path: Path, max_width: float) -> list:
    """Embed an SVG, scaled to fit the text column."""
    from svglib.svglib import svg2rlg

    drawing = svg2rlg(str(path))
    if drawing is None:
        raise ValueError(f"could not parse {path}")
    max_height = PAGE_H - 2 * MARGIN - 40
    scale = min(max_width / drawing.width, max_height / drawing.height, 1.0)
    drawing.scale(scale, scale)
    drawing.width *= scale
    drawing.height *= scale
    drawing.hAlign = "CENTER"
    return [drawing]


def image_flowable(path: Path, max_width: float) -> list:
    if path.suffix.lower() == ".svg":
        return svg_flowable(path, max_width)
    image = Image(str(path))
    scale = min(max_width / image.imageWidth, 1.0)
    image.drawWidth = image.imageWidth * scale
    image.drawHeight = image.imageHeight * scale
    image.hAlign = "CENTER"
    return [image]


def build_table(rows: list[list[str]]) -> Table:
    """Render a Markdown table, sizing columns from content weight."""
    header, *body = rows
    columns = len(header)

    weights = []
    for index in range(columns):
        longest = max(
            [len(re.sub(r"[*`\[\]]", "", (row[index] if index < len(row) else "")))
             for row in rows] + [1])
        weights.append(max(longest, 4) ** 0.72)      # damped so one long cell cannot dominate
    total = sum(weights)
    widths = [max(CONTENT_W * w / total, 20) for w in weights]
    overflow = sum(widths) - CONTENT_W
    if overflow > 0:
        widths = [w - overflow * w / sum(widths) for w in widths]

    data = [[Paragraph(inline(cell), S["cellhead"]) for cell in header]]
    for row in body:
        padded = row + [""] * (columns - len(row))
        data.append([Paragraph(inline(cell), S["cell"]) for cell in padded[:columns]])

    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), HEAD_BG),
        ("LINEBELOW", (0, 0), (-1, 0), 0.9, colors.HexColor("#9aa0a6")),
        ("GRID", (0, 0), (-1, -1), 0.3, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 4.5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4.5),
    ]
    for index in range(1, len(data)):
        if index % 2 == 0:
            style.append(("BACKGROUND", (0, index), (-1, index), ZEBRA))
    table.setStyle(TableStyle(style))
    return table


def parse(md_path: Path) -> Doc:
    lines = md_path.read_text(encoding="utf-8").splitlines()
    flow: list = []
    title = md_path.stem.replace("_", " ")
    subtitle = ""
    seen_h1 = False

    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        # Fenced code
        if stripped.startswith("```"):
            index += 1
            block: list[str] = []
            while index < len(lines) and not lines[index].strip().startswith("```"):
                block.append(lines[index])
                index += 1
            index += 1
            text = "\n".join(block).replace("\t", "    ")
            for bad, good in GLYPH_FALLBACK.items():
                text = text.replace(bad, good)
            flow.append(Preformatted(text, S["code"]))
            continue

        # Table
        if stripped.startswith("|") and index + 1 < len(lines) and \
                re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[index + 1]):
            rows: list[list[str]] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                raw = lines[index].strip()
                if not re.match(r"^\|[\s:|-]+\|$", raw):
                    cells = [c.strip() for c in raw.strip("|").split("|")]
                    rows.append(cells)
                index += 1
            if rows:
                flow.append(Spacer(1, 3))
                flow.append(build_table(rows))
                flow.append(Spacer(1, 9))
            continue

        # Image
        image_match = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$", stripped)
        if image_match:
            caption, target = image_match.group(1), image_match.group(2)
            path = (md_path.parent / target).resolve()
            if path.exists():
                try:
                    parts = image_flowable(path, CONTENT_W)
                    if caption:
                        parts.append(Paragraph(inline(caption), S["caption"]))
                    flow.append(Spacer(1, 6))
                    flow.extend(parts)
                    flow.append(Spacer(1, 4))
                except Exception as exc:  # noqa: BLE001
                    print(f"    ! image failed {target}: {exc}")
            else:
                print(f"    ! image missing: {target}")
            index += 1
            continue

        # Headings
        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading:
            level, text = len(heading.group(1)), heading.group(2).strip()
            if level == 1 and not seen_h1:
                title = re.sub(r"[*`]", "", text)
                seen_h1 = True
            elif level == 2 and seen_h1 and not subtitle and not flow:
                subtitle = re.sub(r"[*`]", "", text)
            else:
                if level == 1:
                    flow.append(PageBreak())
                flow.append(Paragraph(inline(text), S[f"h{min(level, 4)}"]))
            index += 1
            continue

        # Horizontal rule
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
            flow.append(Spacer(1, 4))
            flow.append(HRFlowable(width="100%", thickness=0.6, color=RULE,
                                   spaceBefore=2, spaceAfter=8))
            index += 1
            continue

        # Block quote
        if stripped.startswith(">"):
            block = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                block.append(lines[index].strip().lstrip(">").strip())
                index += 1
            flow.append(Paragraph(inline(" ".join(block)), S["quote"]))
            continue

        # Bullet list
        if re.match(r"^[-*+]\s+", stripped):
            items = []
            while index < len(lines) and re.match(r"^\s*[-*+]\s+", lines[index]):
                items.append(re.sub(r"^\s*[-*+]\s+", "", lines[index]).strip())
                index += 1
                while index < len(lines) and lines[index].startswith("   ") \
                        and lines[index].strip() and not re.match(r"^\s*[-*+0-9]", lines[index].strip()):
                    items[-1] += " " + lines[index].strip()
                    index += 1
            for item in items:
                flow.append(Paragraph(inline(item), S["bullet"], bulletText="\u2022"))
            flow.append(Spacer(1, 5))
            continue

        # Numbered list
        if re.match(r"^\d+\.\s+", stripped):
            counter = 0
            while index < len(lines) and re.match(r"^\s*\d+\.\s+", lines[index]):
                counter += 1
                item = re.sub(r"^\s*\d+\.\s+", "", lines[index]).strip()
                index += 1
                while index < len(lines) and lines[index].startswith("   ") \
                        and lines[index].strip() and not re.match(r"^\s*\d+\.", lines[index]):
                    item += " " + lines[index].strip()
                    index += 1
                flow.append(Paragraph(inline(item), S["number"], bulletText=f"{counter}."))
            flow.append(Spacer(1, 5))
            continue

        # Blank
        if not stripped:
            index += 1
            continue

        # Paragraph
        block = []
        while index < len(lines) and lines[index].strip() and \
                not re.match(r"^(#{1,6}\s|>|```|\||[-*+]\s|\d+\.\s|!\[)", lines[index].strip()) and \
                not re.match(r"^(-{3,}|\*{3,}|_{3,})$", lines[index].strip()):
            block.append(lines[index].strip())
            index += 1
        if block:
            flow.append(Paragraph(inline(" ".join(block)), S["body"]))

    return Doc(title=title, subtitle=subtitle, flowables=flow)


# ---------------------------------------------------------------------------
# Document assembly
# ---------------------------------------------------------------------------

class NumberedDoc(BaseDocTemplate):
    def __init__(self, filename: str, doc_title: str, **kw):
        super().__init__(filename, pagesize=A4,
                         leftMargin=MARGIN, rightMargin=MARGIN,
                         topMargin=MARGIN, bottomMargin=MARGIN + 6, **kw)
        self.doc_title = doc_title
        frame = Frame(MARGIN, MARGIN + 6, CONTENT_W,
                      PAGE_H - 2 * MARGIN - 6, id="body")
        self.addPageTemplates([PageTemplate(id="main", frames=[frame],
                                            onPage=self._decorate)])

    def _decorate(self, canvas, doc):
        canvas.saveState()
        if doc.page > 1:
            canvas.setFont(BODY, 7.5)
            canvas.setFillColor(MUTED)
            canvas.drawString(MARGIN, PAGE_H - MARGIN + 5, "Clinicue")
            canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - MARGIN + 5, self.doc_title)
            canvas.setStrokeColor(RULE)
            canvas.setLineWidth(0.4)
            canvas.line(MARGIN, PAGE_H - MARGIN, PAGE_W - MARGIN, PAGE_H - MARGIN)
        canvas.setFont(BODY, 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawCentredString(PAGE_W / 2, MARGIN - 4, str(doc.page))
        canvas.restoreState()


def title_page(doc: Doc, student: str, student_id: str) -> list:
    return [
        Spacer(1, 58 * mm),
        Paragraph("Clinicue", S["title"]),
        Paragraph(doc.subtitle or "Outpatient Appointment &amp; Queue Management System",
                  S["subtitle"]),
        HRFlowable(width="55%", thickness=1.1, color=ACCENT, spaceAfter=22, hAlign="CENTER"),
        Paragraph(f"<b>{html.escape(doc.title)}</b>", S["meta"]),
        Spacer(1, 20),
        Paragraph(html.escape(student), S["meta"]),
        Paragraph(f"Student ID: {html.escape(student_id)}", S["meta"]),
        Spacer(1, 14),
        Paragraph("Advanced Software Engineering", S["meta"]),
        Paragraph("13 August 2026", S["meta"]),
        PageBreak(),
    ]


def render(md_path: Path, out_path: Path, student: str, student_id: str) -> None:
    doc = parse(md_path)
    body = list(doc.flowables)

    # The title page already ends with a PageBreak, so a leading one from the
    # document's first H1 would leave a blank sheet.
    if body and isinstance(body[0], PageBreak):
        body.pop(0)

    story = title_page(doc, student, student_id) + body
    out_path.parent.mkdir(parents=True, exist_ok=True)
    NumberedDoc(str(out_path), doc.title).build(story)


DEFAULT_SET = [
    ("Project_Documentation.md", "Project_Documentation.pdf"),
    ("SRS.md", "SRS.pdf"),
    ("Effort_Estimation.md", "Effort_Estimation.pdf"),
    ("System_Design.md", "System_Design.pdf"),
    ("Testing_Report.md", "Testing_Report.pdf"),
    ("Technical_Debt_Plan.md", "Technical_Debt_Plan.pdf"),
    ("User_Manual.md", "User_Manual.pdf"),
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sources", nargs="*", help="Markdown files (default: the whole set)")
    parser.add_argument("--out", default=str(OUT))
    parser.add_argument("--student", default="[STUDENT NAME]")
    parser.add_argument("--student-id", default="[STUDENT ID]")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    jobs = ([(Path(s), Path(s).stem + ".pdf") for s in args.sources]
            if args.sources else [(DOCS / src, dst) for src, dst in DEFAULT_SET])

    failures = 0
    print(f"Fonts: body={BODY}  mono={MONO}\n")
    for source, target in jobs:
        if not source.exists():
            print(f"  ! missing {source}")
            failures += 1
            continue
        destination = out_dir / target
        try:
            render(source, destination, args.student, args.student_id)
            size = destination.stat().st_size / 1024
            print(f"  ok  {source.name:<32} -> {target:<32} {size:7.1f} KB")
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL {source.name}: {type(exc).__name__}: {exc}")
            failures += 1

    print()
    if failures:
        print(f"{failures} document(s) failed")
        return 1
    print(f"{len(jobs)} documents written to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
