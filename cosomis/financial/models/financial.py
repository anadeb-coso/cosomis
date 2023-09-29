from django.db import models
from django.utils.translation import gettext_lazy as _

from administrativelevels.models import CVD, AdministrativeLevel
from cosomis.models_base import BaseModel
from subprojects.models import Project
from cosomis.customers_fields import CustomerFloatRangeField
from financial.models.allocation import AdministrativeLevelAllocation


class BankTransfer(BaseModel):
    administrative_level = models.ForeignKey(AdministrativeLevel, on_delete=models.CASCADE, verbose_name=_("Administrative level"), null=True, blank=True)
    cvd = models.ForeignKey(CVD, on_delete=models.CASCADE, verbose_name=_("CVD"), null=True, blank=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, verbose_name=_("Project"))
    amount_transferred = CustomerFloatRangeField(verbose_name=_("Amount transferred"), min_value=0)
    amount_transferred_in_dollars = CustomerFloatRangeField(verbose_name=_("Amount transferred in dollars"), min_value=0, null=True, blank=True)
    transfer_date = models.DateField(verbose_name=_("Transfer date"), null=True)
    motif = models.DateField(max_length=255, verbose_name=_("Motif"), null=True, blank=True)
    description = models.TextField(verbose_name=_("Description"), null=True, blank=True)
    linked_to_allocation = models.ForeignKey(AdministrativeLevelAllocation, on_delete=models.CASCADE, verbose_name=_("Linked to allocation"), null=True, blank=True)

    
    class Meta(object):
        app_label = 'financial'
        db_table = 'financial_bank_transfer'


class DisbursementRequest(BaseModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, verbose_name=_("Project"))
    amount_requested = CustomerFloatRangeField(verbose_name=_("Amount requested"), min_value=0)
    amount_requested_in_dollars = CustomerFloatRangeField(verbose_name=_("Amount requested in dollars"), min_value=0)
    requested_date = models.DateField(verbose_name=_("Request date"))
    motif = models.DateField(max_length=255, verbose_name=_("Motif"), null=True, blank=True)
    description = models.TextField(verbose_name=_("Description"), null=True, blank=True)
    reply_date = models.DateField(verbose_name=_("Reply date"), null=True, blank=True)
    comment_linked_to_reply = models.TextField(verbose_name=_("Comment related to the request response"), null=True, blank=True)

    
    class Meta(object):
        app_label = 'financial'
        db_table = 'financial_disbursement_request'

    
    def __str__(self):
        return f'{self.project}/{self.requested_date.strftime("%d-%m-%Y")}/{self.amount_requested}'


class Disbursement(BaseModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, verbose_name=_("Project"))
    disbursement_request = models.ForeignKey(DisbursementRequest, on_delete=models.CASCADE, verbose_name=_("This disbursement is related to the following request"))
    amount_disbursed = CustomerFloatRangeField(verbose_name=_("Amount disbursed"), min_value=0)
    amount_disbursed_in_dollars = CustomerFloatRangeField(verbose_name=_("Amount disbursed in dollars"), min_value=0)
    disbursement_date = models.DateField(verbose_name=_("Disbursement date"))
    description = models.TextField(verbose_name=_("Description"), null=True, blank=True)

    
    class Meta(object):
        app_label = 'financial'
        db_table = 'financial_disbursement'
