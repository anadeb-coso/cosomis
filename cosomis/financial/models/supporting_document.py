from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from cosomis.models_base import BaseModel, ExternalIdMixin, SoftDeleteMixin


class SupportingDocument(ExternalIdMixin, SoftDeleteMixin, BaseModel):
    class DocumentType(models.TextChoices):
        INVOICE = 'INVOICE', _('Invoice')
        RECEIPT = 'RECEIPT', _('Receipt')
        CONTRACT = 'CONTRACT', _('Contract')
        MINUTES = 'MINUTES', _('Minutes')
        PURCHASE_ORDER = 'PURCHASE_ORDER', _('Purchase order')
        OTHER = 'OTHER', _('Other')

    disbursement = models.ForeignKey('financial.Disbursement', on_delete=models.CASCADE, null=True, blank=True, verbose_name=_("Related disbursement"))
    disbursement_request = models.ForeignKey('financial.DisbursementRequest', on_delete=models.CASCADE, null=True, blank=True, verbose_name=_("Related fund request"))
    document_type = models.CharField(max_length=20, choices=DocumentType.choices, verbose_name=_("Document type"))
    reference = models.CharField(max_length=255, verbose_name=_("Document reference"))
    document_date = models.DateField(verbose_name=_("Document date"))
    file = models.FileField(upload_to='financial/supporting_documents/%Y/%m/', max_length=500, null=True, blank=True, verbose_name=_("File"))
    file_name = models.CharField(max_length=255, null=True, blank=True, verbose_name=_("File display name"))
    notes = models.TextField(null=True, blank=True, verbose_name=_("Observations"))

    class Meta(object):
        app_label = 'financial'
        db_table = 'financial_supporting_document'
        verbose_name = _("Supporting document")
        verbose_name_plural = _("Supporting documents")
        base_manager_name = 'objects'

    def __str__(self):
        return self.reference

    def clean(self):
        if bool(self.disbursement_id) == bool(self.disbursement_request_id):
            raise ValidationError(
                _("Attach the supporting document to either a disbursement or a fund request, never both, never neither.")
            )
        super().clean()

    @property
    def project(self):
        if self.disbursement_id:
            return self.disbursement.project
        if self.disbursement_request_id:
            return self.disbursement_request.project
        return None

    @property
    def total_justified_amount(self):
        return sum((line.allocated_amount or 0) for line in self.supportingdocumentactivity_set.all())


class SupportingDocumentActivity(ExternalIdMixin, BaseModel):
    supporting_document = models.ForeignKey(SupportingDocument, on_delete=models.CASCADE, verbose_name=_("Supporting document"))
    activity = models.ForeignKey('financial.Activity', on_delete=models.CASCADE, verbose_name=_("Activity"))
    allocated_amount = models.FloatField(verbose_name=_("Allocated amount"))
    notes = models.TextField(null=True, blank=True, verbose_name=_("Observations"))

    class Meta(object):
        app_label = 'financial'
        db_table = 'financial_supporting_document_activity'
        verbose_name = _("Supporting document / Activity allocation")
        verbose_name_plural = _("Supporting document / Activity allocations")

    def __str__(self):
        return f'{self.supporting_document} / {self.activity} / {self.allocated_amount}'
