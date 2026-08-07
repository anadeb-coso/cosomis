from django.db import models
from django.utils.translation import gettext_lazy as _

from cosomis.customers_fields import CustomerFloatRangeField
from cosomis.models_base import BaseModel, ExternalIdMixin, SoftDeleteMixin


class Funding(ExternalIdMixin, SoftDeleteMixin, BaseModel):
    class FundingType(models.TextChoices):
        CREDIT = 'CREDIT', _('Credit')
        GRANT = 'GRANT', _('Grant')

    class Financier(models.TextChoices):
        WORLD_BANK = 'WORLD_BANK', _('World Bank')
        UN = 'UN', _('UN')
        STATE = 'STATE', _('State')
        OTHER = 'OTHER', _('Other')

    project = models.ForeignKey('subprojects.Project', on_delete=models.CASCADE, verbose_name=_("IDA Project"))
    funding_type = models.CharField(max_length=10, choices=FundingType.choices, verbose_name=_("Type"))
    financier = models.CharField(max_length=20, choices=Financier.choices, null=True, blank=True, verbose_name=_("Financier"))
    identification_number = models.CharField(max_length=100, verbose_name=_("IDA identification number"))
    label = models.CharField(max_length=255, verbose_name=_("Label"))
    initial_amount = CustomerFloatRangeField(verbose_name=_("Initial amount"), min_value=0)
    notes = models.TextField(null=True, blank=True, verbose_name=_("Observations"))

    class Meta(object):
        app_label = 'financial'
        db_table = 'financial_funding'
        verbose_name = _("Funding")
        verbose_name_plural = _("Fundings")
        ordering = ['label']
        base_manager_name = 'objects'

    def __str__(self):
        return f'{self.label} ({self.identification_number})'

    @property
    def total_validated(self):
        from financial.models.financial import DisbursementRequest
        return sum((r.amount_validated or 0) for r in DisbursementRequest.objects.filter(funding=self))

    @property
    def total_disbursed(self):
        from financial.models.financial import Disbursement, DisbursementRequest
        requests_qs = DisbursementRequest.objects.filter(funding=self)
        return sum((d.amount_disbursed or 0) for d in Disbursement.objects.filter(disbursement_request__in=requests_qs))

    @property
    def available_balance(self):
        """Amount currently available: initial amount minus what's been disbursed."""
        return (self.initial_amount or 0) - (self.total_disbursed or 0)
