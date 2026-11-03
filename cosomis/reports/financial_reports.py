"""Predefined financial reports (PDF on the COSO/MFB letterhead, or Excel).

Every figure comes from FinancialDashboardView's own aggregation, so a report can
never disagree with the financial dashboard for the same filters.
"""
import os
import re
from dataclasses import dataclass
from io import BytesIO
from types import SimpleNamespace

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext, gettext_lazy as _

LETTERHEAD = os.path.join(settings.BASE_DIR, 'static', 'images', 'entete_coso_mfb.jpg')
GREEN = '#0B7A3E'
# Share of the letterhead image height taken by its header (logos) and its footer band.
LETTERHEAD_TOP_SHARE = 0.185
LETTERHEAD_BOTTOM_SHARE = 0.105


def letterhead_parts():
    """Top (logos) and bottom (address band) parts of the full-page letterhead, as PNG streams."""
    from PIL import Image

    if not os.path.exists(LETTERHEAD):
        return None, None
    image = Image.open(LETTERHEAD).convert('RGB')
    width, height = image.size
    parts = []
    for box in ((0, 0, width, int(height * LETTERHEAD_TOP_SHARE)),
                (0, int(height * (1 - LETTERHEAD_BOTTOM_SHARE)), width, height)):
        stream = BytesIO()
        image.crop(box).save(stream, format='PNG')
        stream.seek(0)
        parts.append(stream)
    return parts


SOFT_GREEN = '#EAF5EE'
GREY = '#2F3740'  # dark grey: secondary text must stay readable once printed


class ReportType(models.TextChoices):
    SUMMARY = 'SUMMARY', _('Summary of the financial situation')
    BY_PROJECT = 'BY_PROJECT', _('Situation by IDA project')
    BY_FUNDING = 'BY_FUNDING', _('Situation by credit / grant')
    FUND_REQUESTS = 'FUND_REQUESTS', _('List of fund requests')
    DISBURSEMENTS = 'DISBURSEMENTS', _('List of disbursements')
    BANK_TRANSFERS = 'BANK_TRANSFERS', _('List of bank transfers')
    ACCOUNT_BALANCES = 'ACCOUNT_BALANCES', _('Account balances')


@dataclass
class ReportParameters:
    report_type: str = ReportType.SUMMARY
    title: str = ''
    project: object = None
    funding: object = None
    year: int = None
    introduction: str = ''
    recipient_mention: str = ''
    signatory: str = ''

    @classmethod
    def from_template(cls, template):
        return cls(report_type=template.report_type, title=template.title, project=template.project,
                   funding=template.funding, year=template.year, introduction=template.introduction or '',
                   recipient_mention=template.recipient_mention or '', signatory=template.signatory or '')

    def scope(self):
        criteria = []
        if self.project:
            criteria.append(gettext("Project: {value}").format(value=self.project))
        if self.funding:
            criteria.append(gettext("Credit/Grant: {value}").format(value=self.funding))
        if self.year:
            criteria.append(gettext("Year: {value}").format(value=self.year))
        return " · ".join(criteria) or gettext("All projects")

    def display_title(self):
        return str(self.title or dict(ReportType.choices)[self.report_type])


def amount(value):
    return f"{(value or 0):,.0f}".replace(',', ' ')


def percent(value):
    return f"{(value or 0) * 100:.1f} %".replace('.', ',')


def _dashboard_context(p):
    from financial.views_dashboard import FinancialDashboardView

    view = FinancialDashboardView()
    view.request = SimpleNamespace(GET={
        'project': str(p.project.pk) if p.project else '',
        'funding': str(p.funding.pk) if p.funding else '',
        'year': str(p.year) if p.year else '',
    })
    view.kwargs = {}
    return view.get_context_data()


def _section(title, headers, rows, numeric=()):
    """A generic table, rendered the same way in PDF and Excel. `numeric` = indexes
    of the amount columns (right-aligned, numbers in Excel)."""
    return {'title': str(title), 'headers': [str(h) for h in headers], 'rows': rows, 'numeric': set(numeric)}


def compute(p):
    """Report data, independent of the output format."""
    from financial.models.financial import BankTransfer, Disbursement, DisbursementRequest

    ctx = _dashboard_context(p)
    fr, dis, bt = ctx['fund_requests'], ctx['disbursements'], ctx['bank_transfers']
    kpis = [
        (gettext("Fund requests"), fr['count']),
        (gettext("Amount requested"), amount(fr['total_requested'])),
        (gettext("Amount validated"), amount(fr['total_validated'])),
        (gettext("Validation rate"), percent(fr['validation_rate'])),
        (gettext("Available on the project account"), amount(ctx['available_balance_project'])),
        (gettext("Disbursements"), dis['count']),
        (gettext("Amount disbursed"), amount(dis['total_disbursed'])),
        (gettext("Amount justified"), amount(dis['total_justified'])),
        (gettext("Justification gap"), amount(dis['justification_gap'])),
        (gettext("Bank transfers"), f"{bt['count']} / {amount(bt['total_transferred'])}"),
    ]

    funding_headers = [_("Requests"), _("Requested"), _("Validated"), _("Validation rate"), _("Disbursed"), _("Available")]

    def by_project():
        rows = []
        for r in ctx['project_breakdown']:
            if p.project and r['project'].pk != p.project.pk:
                continue
            rows.append([r['project'].name, amount(r['total_amount']), r['count'], amount(r['total_requested']),
                         amount(r['total_validated']), percent(r['validation_rate']), amount(r['total_disbursed']),
                         amount(r['available_balance'])])
        return _section(_("Situation by IDA project"), [_("IDA project"), _("Total amount")] + funding_headers,
                        rows, numeric=range(1, 8))

    def by_funding():
        rows = []
        for r in ctx['funding_breakdown']:
            if p.funding and r['funding'].pk != p.funding.pk:
                continue
            rows.append([str(r['funding']), amount(r['funding'].initial_amount), r['count'], amount(r['total_requested']),
                         amount(r['total_validated']), percent(r['validation_rate']), amount(r['total_disbursed']),
                         amount(r['available_balance'])])
        return _section(_("Situation by credit / grant"), [_("Credit / Grant"), _("Initial amount")] + funding_headers,
                        rows, numeric=range(1, 8))

    def balances():
        rows = [[r['account'].name if hasattr(r['account'], 'name') else str(r['account']),
                 r['account'].get_account_type_display(), amount(r['total_received']), amount(r['total_sent']),
                 amount(r['returned_to_sender']), amount(r['available_balance'])] for r in ctx['account_balances']]
        return _section(_("Account balances"), [_("Account"), _("Type"), _("Received"), _("Sent"),
                                                _("Returned to sender"), _("Available")], rows, numeric=range(2, 6))

    def requests_qs():
        qs = DisbursementRequest.objects.select_related('project', 'funding').prefetch_related('validations', 'disbursement_set')
        if p.project:
            qs = qs.filter(project=p.project)
        if p.funding:
            qs = qs.filter(funding=p.funding)
        if p.year:
            qs = qs.filter(requested_date__year=p.year)
        return qs.order_by('requested_date')

    def fund_requests():
        rows = [[f"{r.requested_date:%d/%m/%Y}", str(r.project), str(r.funding or '-'), amount(r.amount_requested),
                 amount(r.amount_validated), amount(r.total_disbursed), r.get_status_display()] for r in requests_qs()]
        return _section(_("List of fund requests"), [_("Date"), _("Project"), _("Credit / Grant"), _("Requested"),
                                                     _("Validated"), _("Disbursed"), _("Status")], rows, numeric=(3, 4, 5))

    def disbursements():
        qs = (Disbursement.objects.filter(disbursement_request__in=requests_qs())
              .select_related('disbursement_request__project', 'disbursement_request__funding').order_by('disbursement_date'))
        rows = [[f"{d.disbursement_date:%d/%m/%Y}", str(d.project), str(d.funding or '-'), amount(d.amount_disbursed),
                 amount(d.justified_amount), amount(d.justification_gap), d.get_justification_status_display()] for d in qs]
        return _section(_("List of disbursements"), [_("Date"), _("Project"), _("Credit / Grant"), _("Disbursed"),
                                                     _("Justified"), _("Gap"), _("Justification")], rows, numeric=(3, 4, 5))

    def transfers():
        qs = BankTransfer.objects.select_related('sender', 'recipient').order_by('transfer_date')
        if p.year:
            qs = qs.filter(transfer_date__year=p.year)
        rows = [[f"{t.transfer_date:%d/%m/%Y}" if t.transfer_date else '-', str(t.sender or '-'), str(t.recipient or '-'),
                 t.get_level_display() or '-', t.get_direction_display(), amount(t.amount_transferred), t.motif or '']
                for t in qs]
        return _section(_("List of bank transfers"), [_("Date"), _("Sender"), _("Recipient"), _("Level"), _("Direction"),
                                                      _("Amount"), _("Motif")], rows, numeric=(5,))

    builders = {
        ReportType.SUMMARY: [by_project, by_funding, balances],
        ReportType.BY_PROJECT: [by_project],
        ReportType.BY_FUNDING: [by_funding],
        ReportType.FUND_REQUESTS: [fund_requests],
        ReportType.DISBURSEMENTS: [disbursements],
        ReportType.BANK_TRANSFERS: [transfers],
        ReportType.ACCOUNT_BALANCES: [balances],
    }
    return {'kpis': kpis, 'sections': [build() for build in builders[p.report_type]]}


# --------------------------------------------------------------------------- PDF
def pdf(p):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    data = compute(p)
    buffer = BytesIO()
    green = colors.HexColor(GREEN)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('t', parent=styles['Title'], textColor=green, fontSize=15, spaceAfter=2)
    subtitle = ParagraphStyle('st', parent=styles['Normal'], textColor=colors.HexColor(GREY), fontSize=9, alignment=1)
    h2 = ParagraphStyle('h2', parent=styles['Heading2'], textColor=green, fontSize=11, spaceBefore=10, spaceAfter=4)
    normal = ParagraphStyle('n', parent=styles['Normal'], fontSize=8.5)
    cell = ParagraphStyle('c', parent=styles['Normal'], fontSize=7.5, leading=9, textColor=colors.black)
    head_cell = ParagraphStyle('hc', parent=cell, textColor=colors.white, fontName='Helvetica-Bold')

    from reportlab.lib.utils import ImageReader

    top, bottom = letterhead_parts()
    top = ImageReader(top) if top else None
    bottom = ImageReader(bottom) if bottom else None

    def page_decoration(canvas, doc, first_page):
        # Letterhead header (logos) on the first page only; footer band (address) on every page.
        canvas.saveState()
        width, height = doc.pagesize
        if first_page and top:
            canvas.drawImage(top, 0, height * (1 - LETTERHEAD_TOP_SHARE), width=width, height=height * LETTERHEAD_TOP_SHARE)
        if bottom:
            canvas.drawImage(bottom, 0, 0, width=width, height=height * LETTERHEAD_BOTTOM_SHARE)
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor(GREY))
        canvas.drawRightString(width - 1.8 * cm, height - (4.6 if first_page else 1.0) * cm,
                               gettext("Page {page}").format(page=doc.page))
        canvas.restoreState()

    # Small top margin on every page; the first page adds a spacer below its letterhead header.
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.5 * cm,
                            bottomMargin=3.4 * cm, title=p.display_title(), author="COSO")
    width = A4[0] - 3.6 * cm
    elements = [Paragraph(p.display_title(), title_style),
                Paragraph(gettext("{scope} — situation as of {now:%d/%m/%Y %H:%M}").format(
                    scope=p.scope(), now=timezone.localtime()), subtitle), Spacer(1, 6)]
    if p.recipient_mention:
        elements.insert(0, Paragraph(p.recipient_mention, ParagraphStyle('m', parent=normal, alignment=2)))
    if p.introduction:
        elements += [Paragraph(p.introduction.replace('\n', '<br/>'), normal), Spacer(1, 4)]

    elements.append(Paragraph(gettext("Key figures"), h2))
    kpis = data['kpis']
    rows = []
    for start in range(0, len(kpis), 5):
        chunk = kpis[start:start + 5]
        rows.append([Paragraph(label, cell) for label, _v in chunk])
        rows.append([str(v) for _l, v in chunk])
    kpi_table = Table(rows, colWidths=[width / 5] * 5)
    kpi_table.setStyle(TableStyle([
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor(GREY)), ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
        ('FONTNAME', (0, 3), (-1, 3), 'Helvetica-Bold'), ('FONTSIZE', (0, 1), (-1, 1), 10), ('FONTSIZE', (0, 3), (-1, 3), 10),
        ('TEXTCOLOR', (0, 1), (-1, 1), colors.black), ('TEXTCOLOR', (0, 3), (-1, 3), colors.black),
        ('BOTTOMPADDING', (0, 1), (-1, 1), 8), ('BOX', (0, 0), (-1, -1), 0.5, green), ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    elements.append(kpi_table)

    for section in data['sections']:
        elements.append(Paragraph(f"{section['title']} ({len(section['rows'])})", h2))
        if not section['rows']:
            elements.append(Paragraph(gettext("No data for this selection."), normal))
            continue
        columns = len(section['headers'])
        first = width * (0.26 if columns > 6 else 0.3)
        col_widths = [first] + [(width - first) / (columns - 1)] * (columns - 1)
        lines = [[Paragraph(h, head_cell) for h in section['headers']]]
        for row in section['rows']:
            lines.append([str(v) if i in section['numeric'] else Paragraph(str(v), cell) for i, v in enumerate(row)])
        table = Table(lines, colWidths=col_widths, repeatRows=1)
        style = [
            ('BACKGROUND', (0, 0), (-1, 0), green), ('FONTSIZE', (0, 1), (-1, -1), 7.5),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor(SOFT_GREEN)]),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#C9D6CE')), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]
        style += [('ALIGN', (i, 1), (i, -1), 'RIGHT') for i in section['numeric']]
        table.setStyle(TableStyle(style))
        elements.append(table)

    if p.signatory:
        elements += [Spacer(1, 16), Paragraph(p.signatory, ParagraphStyle('s', parent=normal, alignment=2))]
    elements.insert(0, Spacer(1, 3.7 * cm))
    doc.build(elements, onFirstPage=lambda c, d: page_decoration(c, d, True),
              onLaterPages=lambda c, d: page_decoration(c, d, False))
    return buffer.getvalue()


# ------------------------------------------------------------------------- Excel
def excel(p):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    data = compute(p)
    workbook = Workbook()
    header_font, header_fill = Font(bold=True, color='FFFFFF'), PatternFill('solid', fgColor=GREEN.lstrip('#'))

    def sheet_title(ws, text):
        ws.append([text])
        ws['A1'].font = Font(bold=True, size=13, color=GREEN.lstrip('#'))
        ws.append([gettext("{scope} — situation as of {now:%d/%m/%Y %H:%M}").format(scope=p.scope(), now=timezone.localtime())])
        ws.append([])

    def to_number(value):
        try:
            return float(str(value).replace(' ', '').replace(',', '.').replace('%', ''))
        except ValueError:
            return value

    ws = workbook.active
    ws.title = gettext("Key figures")[:31]
    sheet_title(ws, p.display_title())
    for label, value in data['kpis']:
        ws.append([label, value])
    ws.column_dimensions['A'].width, ws.column_dimensions['B'].width = 40, 28

    for section in data['sections']:
        # Excel forbids : \ / ? * [ ] in sheet names and limits them to 31 characters.
        name = re.sub(r'[:\\/?*\[\]]', '-', section['title'])[:31]
        ws = workbook.create_sheet(name)
        sheet_title(ws, section['title'])
        ws.append(section['headers'])
        for c in ws[ws.max_row]:
            c.font, c.fill, c.alignment = header_font, header_fill, Alignment(wrap_text=True, vertical='center')
        for row in section['rows']:
            ws.append([to_number(v) if i in section['numeric'] else v for i, v in enumerate(row)])
            for i in section['numeric']:
                ws.cell(row=ws.max_row, column=i + 1).number_format = '#,##0.0' if '%' in str(row[i]) else '#,##0'
        for index in range(len(section['headers'])):
            ws.column_dimensions[chr(65 + index)].width = 38 if index == 0 else 18

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
