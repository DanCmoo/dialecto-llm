"""Build the IEEE LaTeX source and its PDF rendition from one local text source.

Use a Python installation with ReportLab. No network or run data is accessed.
Supported Markdown: title/subtitle, headings, paragraphs, and pipe tables.
"""
from __future__ import annotations

import argparse
import html
import re
from pathlib import Path


def read_report(path: Path):
    chunks = re.split(r"\n\s*\n", path.read_text(encoding="utf-8-sig").strip())
    front = chunks.pop(0).splitlines()
    if len(front) != 2 or not front[0].startswith("# "):
        raise ValueError("El informe debe comenzar con un título y una línea de autoría.")
    blocks = []
    for chunk in chunks:
        if chunk.startswith("## "):
            blocks.append(("section", chunk[3:]))
        elif chunk.startswith("### "):
            blocks.append(("subsection", chunk[4:]))
        elif chunk.startswith("| "):
            table = [[cell.strip() for cell in line.strip("|").split("|")]
                     for line in chunk.splitlines()]
            if len(table) < 3 or any(len(row) != len(table[0]) for row in table):
                raise ValueError("Tabla sin filas de datos o con columnas irregulares.")
            blocks.append(("table", [table[0], *table[2:]]))
        else:
            blocks.append(("paragraph", " ".join(chunk.splitlines())))
    return front[0][2:], front[1], blocks


def latex_text(value):
    special = dict(zip("&%$#_{}~^\\", (
        r"\&", r"\%", r"\$", r"\#", r"\_", r"\{", r"\}",
        r"\textasciitilde{}", r"\textasciicircum{}", r"\textbackslash{}",
    )))
    special.update({"−": r"\ensuremath{-}", "–": "--"})
    return "".join(special.get(char, char) for char in value)


def latex_report(path: Path, title, byline, blocks):
    preamble = r"""\documentclass[conference]{IEEEtran}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[spanish,es-nodecimaldot]{babel}
\usepackage{booktabs,tabularx}
"""
    tex = ["% Generado por src/render_informe.py; editar informe_proyecto.md.", preamble,
           r"\title{" + latex_text(title) + "}",
           r"\author{\IEEEauthorblockN{" + latex_text(byline) + "}}",
           r"\begin{document}", r"\maketitle"]
    caption = None
    bibliography = False
    for kind, data in blocks:
        if kind == "section" and data == "Referencias":
            tex.append(r"\begin{thebibliography}{99}")
            bibliography = True
        elif bibliography:
            number, reference = data[1:].split("] ", 1)
            tex.append(r"\bibitem{r" + number + "} " + latex_text(reference))
        elif kind in ("section", "subsection"):
            tex.append("\\" + kind + "{" + latex_text(data) + "}")
        elif kind == "table":
            cells = len(data[0])
            spec = r">{\raggedright\arraybackslash}X" * cells
            tex.extend([r"\begin{table}[!t]", r"\centering"])
            if caption:
                tex.append(r"\caption{" + latex_text(caption.split(". ", 1)[1]) + "}")
            tex.extend([r"\footnotesize", r"\begin{tabularx}{\columnwidth}{" + spec + "}", r"\toprule"])
            for index, row in enumerate(data):
                tex.append(" & ".join(map(latex_text, row)) + r" \\")
                if not index:
                    tex.append(r"\midrule")
            tex.extend([r"\bottomrule", r"\end{tabularx}", r"\end{table}"])
            caption = None
        elif data.startswith("Resumen. "):
            tex.extend([r"\begin{abstract}", latex_text(data.removeprefix("Resumen. ")), r"\end{abstract}"])
        elif data.startswith("Palabras clave. "):
            tex.extend([r"\begin{IEEEkeywords}", latex_text(data.removeprefix("Palabras clave. ")),
                        r"\end{IEEEkeywords}"])
        elif re.match(r"Tabla \d+\. ", data):
            caption = data
        else:
            tex.extend([latex_text(data), ""])
    if bibliography:
        tex.append(r"\end{thebibliography}")
    tex.append(r"\end{document}")
    path.write_text("\n".join(tex) + "\n", encoding="utf-8")


def pdf_report(path: Path, title, byline, blocks):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import (
        BaseDocTemplate, Frame, FrameBreak, KeepTogether, PageTemplate,
        Paragraph, Table, TableStyle,
    )

    width, height = letter
    margin, bottom, gutter, mast = 17 * mm, 16 * mm, 5 * mm, 82
    textwidth = width - 2 * margin
    col = (textwidth - gutter) / 2
    navy = colors.HexColor("#172638")
    line = colors.HexColor("#b4bdc8")

    def frame(x, y, w, h):
        return Frame(x, y, w, h, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)

    def columns(top):
        return [frame(margin, bottom, col, top - bottom),
                frame(margin + col + gutter, bottom, col, top - bottom)]

    def footer(canvas, doc):
        canvas.setStrokeColor(line)
        canvas.setLineWidth(.35)
        canvas.line(margin, bottom - 8, width - margin, bottom - 8)
        canvas.setFillColor(navy)
        canvas.setFont("Helvetica", 7)
        canvas.drawString(margin, bottom - 18, "DIALECTO-LLM / GRUPO 3")
        canvas.drawRightString(width - margin, bottom - 18, str(doc.page))

    doc = BaseDocTemplate(str(path), pagesize=letter, title=title, author="Grupo 3",
                          subject="Informe del proyecto y resultados exploratorios")
    top = height - 17 * mm
    doc.addPageTemplates([
        PageTemplate(id="first", frames=[frame(margin, top - mast, textwidth, mast), *columns(top - mast)],
                     onPage=footer, autoNextPageTemplate="rest"),
        PageTemplate(id="rest", frames=columns(top), onPage=footer),
    ])
    body = ParagraphStyle("body", fontName="Times-Roman", fontSize=9.7, leading=11.5,
                          spaceAfter=5, alignment=TA_JUSTIFY)
    styles = {
        "title": ParagraphStyle("title", parent=body, fontName="Times-Bold", fontSize=19,
                                leading=21, alignment=TA_CENTER, spaceAfter=4, textColor=navy),
        "byline": ParagraphStyle("byline", parent=body, fontSize=10, alignment=TA_CENTER),
        "section": ParagraphStyle("section", parent=body, fontName="Times-Bold", fontSize=10.6,
                                  spaceBefore=6, spaceAfter=3, keepWithNext=True, textColor=navy),
        "subsection": ParagraphStyle("subsection", parent=body, fontName="Times-Italic", fontSize=10.3,
                                     spaceBefore=3, spaceAfter=3, keepWithNext=True),
        "caption": ParagraphStyle("caption", parent=body, fontName="Helvetica-Bold", fontSize=7.7,
                                  leading=9, spaceBefore=3, spaceAfter=4, keepWithNext=True, textColor=navy),
        "table": ParagraphStyle("table", parent=body, fontSize=8.3, leading=10, alignment=0),
        "tablehead": ParagraphStyle("tablehead", parent=body, fontName="Times-Bold", fontSize=8.3,
                                    leading=10, alignment=0, textColor=navy),
        "reference": ParagraphStyle("reference", parent=body, fontSize=8.9, leading=10.3,
                                    spaceAfter=3, alignment=0),
    }
    def pdf_text(value):
        return html.escape(value.replace("−", "-"))

    story = [Paragraph(html.escape(title), styles["title"]),
             Paragraph(html.escape(byline), styles["byline"]), FrameBreak()]
    roman = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII")
    number = 0
    caption = None
    for kind, data in blocks:
        if kind == "table":
            cols = len(data[0])
            fractions = {2: (.30, .70), 3: (.55, .225, .225), 4: (.25, .23, .25, .27)}
            widths = [col * x for x in fractions.get(cols, (1 / cols,) * cols)]
            cells = [[Paragraph(pdf_text(c), styles["tablehead" if index == 0 else "table"])
                      for c in row] for index, row in enumerate(data)]
            table = Table(cells, colWidths=widths, repeatRows=1, spaceAfter=6, hAlign="LEFT")
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eaf0f7")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6f9")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LINEBELOW", (0, -1), (-1, -1), .4, line),
            ]))
            components = [Paragraph(pdf_text(caption), styles["caption"]), table] if caption else [table]
            story.append(KeepTogether(components))
            caption = None
            continue
        value = pdf_text(data)
        if kind == "section" and data != "Referencias":
            value = roman[number] + ". " + value
            number += 1
        style = styles.get(kind, body)
        if re.match(r"Tabla \d+\. ", data):
            caption = data
            continue
        elif re.match(r"\[\d+\] ", data):
            style = styles["reference"]
        elif kind == "paragraph" and data.startswith(("Resumen. ", "Palabras clave. ")):
            prefix, rest = value.split(". ", 1)
            value = f"<b>{prefix}.</b> {rest}"
        story.append(Paragraph(value, style))
    doc.build(story)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    report = read_report(args.source)
    latex_report(args.source.with_suffix(".tex"), *report)
    pdf_report(args.source.with_suffix(".pdf"), *report)


if __name__ == "__main__":
    main()
