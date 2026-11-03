"""Email sending of periodic reports (weekly on Mondays, monthly on the 1st)."""
from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone, translation
from django.utils.translation import gettext

from reports.financial_reports import ReportParameters, excel, pdf
from reports.word_report import word
from financial.models.report_template import ReportTemplate

DOCX = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


def send(template, user=None):
    """Sends the report to its recipients now. Returns the number of recipients."""
    emails = template.emails
    if not emails:
        return 0
    with translation.override(template.language or 'fr'):
        parameters = ReportParameters.from_template(template)
        stamp = f"{timezone.localdate():%Y%m%d}"
        message = EmailMessage(
            subject=f"[COSO] {template.title}",
            body=gettext("Please find attached the report “{title}” as of {date:%d/%m/%Y}.\n\n"
                         "This message is sent automatically by the COSO MIS.").format(
                title=template.title, date=timezone.localdate()),
            from_email=settings.DEFAULT_FROM_EMAIL, to=emails)
        if template.file_format in (ReportTemplate.FileFormat.PDF, ReportTemplate.FileFormat.BOTH, ReportTemplate.FileFormat.ALL):
            message.attach(f"rapport_{template.pk}_{stamp}.pdf", pdf(parameters), 'application/pdf')
        if template.file_format in (ReportTemplate.FileFormat.WORD, ReportTemplate.FileFormat.ALL):
            message.attach(f"rapport_{template.pk}_{stamp}.docx", word(parameters), DOCX)
        if template.file_format in (ReportTemplate.FileFormat.EXCEL, ReportTemplate.FileFormat.BOTH,
                                    ReportTemplate.FileFormat.ALL):
            message.attach(f"rapport_{template.pk}_{stamp}.xlsx", excel(parameters), XLSX)
    message.send()
    template.last_sent = timezone.now()
    template.save_and_return_object(user) if user else template.save()
    return len(emails)


def is_due(template, now):
    today = timezone.localtime(now).date()
    already_sent_today = template.last_sent and timezone.localtime(template.last_sent).date() == today
    if already_sent_today:
        return False
    if template.periodicity == ReportTemplate.Periodicity.WEEKLY:
        return today.weekday() == 0
    if template.periodicity == ReportTemplate.Periodicity.MONTHLY:
        return today.day == 1
    return False


def send_due_reports(now=None):
    """To be run once a day. Returns the number of reports sent."""
    now = now or timezone.now()
    sent = 0
    for template in ReportTemplate.objects.filter(is_active=True).exclude(periodicity=ReportTemplate.Periodicity.NONE):
        if is_due(template, now) and send(template):
            sent += 1
    return sent
