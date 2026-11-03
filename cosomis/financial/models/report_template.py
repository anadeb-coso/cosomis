"""Configurable periodic reports (sent by email on a weekly or monthly schedule)."""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from cosomis.models_base import BaseModel
from reports.financial_reports import ReportType  # noqa: F401 (report choices live in reports)


class ReportTemplate(BaseModel):
    class Periodicity(models.TextChoices):
        NONE = 'NONE', _('On demand only')
        WEEKLY = 'WEEKLY', _('Weekly (every Monday)')
        MONTHLY = 'MONTHLY', _('Monthly (on the 1st)')

    class FileFormat(models.TextChoices):
        PDF = 'PDF', _('PDF')
        WORD = 'WORD', _('Word')
        EXCEL = 'EXCEL', _('Excel')
        BOTH = 'BOTH', _('PDF and Excel')
        ALL = 'ALL', _('PDF, Word and Excel')

    title = models.CharField(max_length=255, verbose_name=_("Report title"))
    report_type = models.CharField(max_length=20, choices=ReportType.choices, default=ReportType.SUMMARY,
                                   verbose_name=_("Report type"))
    introduction = models.TextField(null=True, blank=True, verbose_name=_("Introduction text"))
    recipient_mention = models.CharField(max_length=255, null=True, blank=True, verbose_name=_("Recipient mention"),
                                         help_text=_("E.g. “For the attention of the National Coordinator”."))
    signatory = models.CharField(max_length=255, null=True, blank=True, verbose_name=_("Signatory / issuing department"))
    project = models.ForeignKey('subprojects.Project', null=True, blank=True, on_delete=models.SET_NULL,
                                verbose_name=_("Limit to the IDA project"))
    funding = models.ForeignKey('financial.Funding', null=True, blank=True, on_delete=models.SET_NULL,
                                verbose_name=_("Limit to the credit / grant"))
    year = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Limit to the year"))
    periodicity = models.CharField(max_length=20, choices=Periodicity.choices, default=Periodicity.NONE,
                                   verbose_name=_("Periodicity"))
    file_format = models.CharField(max_length=10, choices=FileFormat.choices, default=FileFormat.PDF,
                                   verbose_name=_("Format"))
    language = models.CharField(max_length=10, choices=settings.LANGUAGES, default='fr', verbose_name=_("Report language"))
    recipients = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='received_report_templates',
                                        verbose_name=_("Recipients (accounts)"))
    other_emails = models.TextField(null=True, blank=True, verbose_name=_("Other recipients (emails)"),
                                    help_text=_("One email address per line."))
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))
    last_sent = models.DateTimeField(null=True, blank=True, editable=False, verbose_name=_("Last sent"))

    class Meta:
        verbose_name = _("Report template")
        verbose_name_plural = _("Report templates")
        ordering = ['title']

    def __str__(self):
        return self.title

    @property
    def emails(self):
        addresses = [u.email for u in self.recipients.filter(is_active=True) if u.email]
        addresses += [line.strip() for line in (self.other_emails or '').splitlines() if '@' in line]
        return sorted(set(addresses))
