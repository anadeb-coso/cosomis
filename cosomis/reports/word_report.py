"""Word (.docx) version of the financial reports, on the COSO/MFB letterhead.

The letterhead is a full-page image: its top part (logos) goes in the page header and
its bottom band (address) in the page footer, so it appears on every page."""
import os
from io import BytesIO

from django.utils import timezone
from django.utils.translation import gettext

from reports.financial_reports import (GREEN, GREY, LETTERHEAD_BOTTOM_SHARE, LETTERHEAD_TOP_SHARE, SOFT_GREEN,
                                       compute, letterhead_parts)

def word(p):
    from docx import Document
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor

    data = compute(p)
    green = RGBColor.from_string(GREEN.lstrip('#'))
    dark = RGBColor.from_string(GREY.lstrip('#'))
    white = RGBColor(0xFF, 0xFF, 0xFF)
    document = Document()
    document.styles['Normal'].font.name = 'Arial'
    document.styles['Normal'].font.size = Pt(9)

    section = document.sections[0]
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    margin = Cm(1.8)
    section.left_margin = section.right_margin = margin
    # Small top margin: on the first page, the taller letterhead header pushes the text down.
    section.top_margin, section.bottom_margin = Cm(1.5), Cm(3.6)
    section.header_distance = section.footer_distance = Cm(0)
    # Letterhead header (logos) on the first page only; footer band (address) on every page.
    section.different_first_page_header_footer = True

    top, bottom = letterhead_parts()
    placements = [(section.first_page_header, top, LETTERHEAD_TOP_SHARE),
                  (section.first_page_footer, bottom, LETTERHEAD_BOTTOM_SHARE),
                  (section.footer, bottom, LETTERHEAD_BOTTOM_SHARE)]
    for container, picture, share in placements:
        if picture is None:
            continue
        picture.seek(0)
        paragraph = container.paragraphs[0]
        # Full page width: the picture extends over the left and right margins.
        paragraph.paragraph_format.left_indent = -margin
        paragraph.paragraph_format.right_indent = -margin
        paragraph.paragraph_format.space_after = Pt(0)
        paragraph.add_run().add_picture(picture, width=Cm(21), height=Cm(29.7 * share))

    def shade(cell, color):
        fill = OxmlElement('w:shd')
        fill.set(qn('w:val'), 'clear')
        fill.set(qn('w:color'), 'auto')
        fill.set(qn('w:fill'), color.lstrip('#'))
        cell._tc.get_or_add_tcPr().append(fill)

    def write(cell, text, bold=False, color=None, size=8, align=None):
        cell.text = ''
        paragraph = cell.paragraphs[0]
        paragraph.paragraph_format.space_after = Pt(0)
        if align is not None:
            paragraph.alignment = align
        run = paragraph.add_run(str(text))
        run.bold, run.font.size = bold, Pt(size)
        if color is not None:
            run.font.color.rgb = color

    def text(content, size=9, bold=False, color=None, align=None, before=0, after=4):
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.space_before, paragraph.paragraph_format.space_after = Pt(before), Pt(after)
        if align is not None:
            paragraph.alignment = align
        run = paragraph.add_run(content)
        run.bold, run.font.size = bold, Pt(size)
        if color is not None:
            run.font.color.rgb = color
        return paragraph

    def heading(content):
        text(content, size=11, bold=True, color=green, before=10)

    if p.recipient_mention:
        text(p.recipient_mention, align=WD_ALIGN_PARAGRAPH.RIGHT)
    text('', after=6)  # breathing room below the letterhead header
    text(p.display_title(), size=15, bold=True, color=green, align=WD_ALIGN_PARAGRAPH.CENTER, after=2)
    text(gettext("{scope} — situation as of {now:%d/%m/%Y %H:%M}").format(scope=p.scope(), now=timezone.localtime()),
         color=dark, align=WD_ALIGN_PARAGRAPH.CENTER, after=8)
    if p.introduction:
        text(p.introduction)

    heading(gettext("Key figures"))
    kpis = data['kpis']
    table = document.add_table(rows=0, cols=5)
    table.style = 'Table Grid'
    for start in range(0, len(kpis), 5):
        labels, values = table.add_row().cells, table.add_row().cells
        for index, (label, value) in enumerate(kpis[start:start + 5]):
            write(labels[index], label, color=dark, size=7.5)
            write(values[index], value, bold=True, size=10)

    for block in data['sections']:
        heading(f"{block['title']} ({len(block['rows'])})")
        if not block['rows']:
            text(gettext("No data for this selection."))
            continue
        table = document.add_table(rows=1, cols=len(block['headers']))
        table.style = 'Table Grid'
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        for index, header in enumerate(block['headers']):
            cell = table.rows[0].cells[index]
            write(cell, header, bold=True, color=white, size=7.5)
            shade(cell, GREEN)
        # Repeat the header row at the top of every page.
        repeat = OxmlElement('w:tblHeader')
        repeat.set(qn('w:val'), 'true')
        table.rows[0]._tr.get_or_add_trPr().append(repeat)
        for row_number, row in enumerate(block['rows']):
            cells = table.add_row().cells
            for index, value in enumerate(row):
                write(cells[index], value, size=7.5,
                      align=WD_ALIGN_PARAGRAPH.RIGHT if index in block['numeric'] else None)
                if row_number % 2:
                    shade(cells[index], SOFT_GREEN)

    if p.signatory:
        text(p.signatory, align=WD_ALIGN_PARAGRAPH.RIGHT, before=16)

    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()
