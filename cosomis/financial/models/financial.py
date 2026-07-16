from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from cosomis.models_base import BaseModel, ExternalIdMixin, SoftDeleteMixin
from cosomis.customers_fields import CustomerFloatRangeField
from financial.models.allocation import AdministrativeLevelAllocation
from financial.models.account import Account
from financial.models.funding import Funding
from financial.models.supporting_document import SupportingDocument


class BankTransfer(ExternalIdMixin, SoftDeleteMixin, BaseModel):
    class Level(models.TextChoices):
        LEVEL_1_PROJECT = 'LEVEL_1_PROJECT', _('Level 1 - Project')
        LEVEL_2_REGIONAL_OFFICE = 'LEVEL_2_REGIONAL_OFFICE', _('Level 2 - Regional office')
        LEVEL_3_TOWN_HALL = 'LEVEL_3_TOWN_HALL', _('Level 3 - Town hall')
        LEVEL_4_CVD = 'LEVEL_4_CVD', _('Level 4 - CVD')

    class PaymentMethod(models.TextChoices):
        BANK_TRANSFER = 'BANK_TRANSFER', _('Bank transfer')
        CHEQUE = 'CHEQUE', _('Cheque')

    class Direction(models.TextChoices):
        FORWARD = 'FORWARD', _('Sender to recipient')
        RETURN = 'RETURN', _('Recipient to sender (return)')

    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        EXECUTED = 'EXECUTED', _('Executed')
        CANCELLED = 'CANCELLED', _('Cancelled')

    # Level -> (expected sender account_type, allowed recipient account_types)
    TRANSFER_RULES = {
        Level.LEVEL_1_PROJECT: (
            Account.AccountType.PROJECT,
            {Account.AccountType.REGIONAL_OFFICE, Account.AccountType.TOWN_HALL,
             Account.AccountType.PROJECT_SPECIALIST, Account.AccountType.SERVICE_PROVIDER},
        ),
        Level.LEVEL_2_REGIONAL_OFFICE: (
            Account.AccountType.REGIONAL_OFFICE,
            {Account.AccountType.TOWN_HALL, Account.AccountType.CVD,
             Account.AccountType.PROJECT_SPECIALIST, Account.AccountType.SERVICE_PROVIDER},
        ),
        Level.LEVEL_3_TOWN_HALL: (
            Account.AccountType.TOWN_HALL,
            {Account.AccountType.SERVICE_PROVIDER},
        ),
        Level.LEVEL_4_CVD: (
            Account.AccountType.CVD,
            {Account.AccountType.SERVICE_PROVIDER},
        ),
    }

    project = models.ForeignKey('subprojects.Project', on_delete=models.CASCADE, null=True, blank=True, verbose_name=_("Project"))
    funding = models.ForeignKey(Funding, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Credit/Grant"))
    disbursement = models.ForeignKey('financial.Disbursement', on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Related disbursement"))
    sender = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Sender"), related_name='sent_bank_transfers')
    recipient = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Recipient"), related_name='received_bank_transfers')
    level = models.CharField(max_length=30, choices=Level.choices, null=True, blank=True, verbose_name=_("Level"))
    direction = models.CharField(max_length=10, choices=Direction.choices, default=Direction.FORWARD, verbose_name=_("Direction"))
    amount_transferred = CustomerFloatRangeField(verbose_name=_("Amount transferred"), min_value=0)
    amount_transferred_in_dollars = CustomerFloatRangeField(verbose_name=_("Amount transferred in dollars"), min_value=0, null=True, blank=True)
    transfer_date = models.DateField(verbose_name=_("Transfer date"), null=True)
    motif = models.CharField(max_length=255, verbose_name=_("Motif"), null=True, blank=True)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.BANK_TRANSFER, verbose_name=_("Payment method"))
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, verbose_name=_("Status"))
    supporting_documents = models.ManyToManyField(SupportingDocument, blank=True, verbose_name=_("Supporting documents"))
    description = models.TextField(verbose_name=_("Description"), null=True, blank=True)
    linked_to_allocation = models.ForeignKey(AdministrativeLevelAllocation, on_delete=models.SET_NULL, verbose_name=_("Linked to allocation"), null=True, blank=True)

    class Meta(object):
        app_label = 'financial'
        db_table = 'financial_bank_transfer'
        base_manager_name = 'objects'

    @property
    def year(self):
        return self.transfer_date.year if self.transfer_date else None

    def clean(self):
        if self.sender_id and self.recipient_id:
            sender_type = self.sender.account_type
            recipient_type = self.recipient.account_type

            if self.direction == self.Direction.RETURN:
                effective_sender_type, effective_recipient_type = recipient_type, sender_type
            else:
                effective_sender_type, effective_recipient_type = sender_type, recipient_type

            matching_level = next(
                (level for level, (expected_sender_type, _allowed) in self.TRANSFER_RULES.items()
                 if expected_sender_type == effective_sender_type),
                None
            )

            if matching_level is None:
                raise ValidationError(
                    _("Account type %(sender_type)s is not allowed to initiate a bank transfer.") %
                    {'sender_type': effective_sender_type}
                )

            _expected_sender_type, allowed_recipient_types = self.TRANSFER_RULES[matching_level]
            if effective_recipient_type not in allowed_recipient_types:
                raise ValidationError(
                    _("A transfer from %(sender_type)s to %(recipient_type)s is not authorized by the transfer rules.") %
                    {'sender_type': effective_sender_type, 'recipient_type': effective_recipient_type}
                )

            if not self.level:
                self.level = matching_level
            elif self.level != matching_level:
                raise ValidationError(
                    _("The selected level does not match the sender's account type.")
                )

        super().clean()


class DisbursementRequest(ExternalIdMixin, SoftDeleteMixin, BaseModel):
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        FULLY_VALIDATED = 'FULLY_VALIDATED', _('Fully validated')
        PARTIALLY_VALIDATED = 'PARTIALLY_VALIDATED', _('Partially validated')
        REJECTED = 'REJECTED', _('Rejected')

    project = models.ForeignKey('subprojects.Project', on_delete=models.CASCADE, verbose_name=_("Project"))
    funding_type = models.CharField(max_length=10, choices=Funding.FundingType.choices, null=True, blank=True, verbose_name=_("Type (Credit/Grant)"))
    funding = models.ForeignKey(Funding, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Credit/Grant"))
    amount_requested = CustomerFloatRangeField(verbose_name=_("Amount requested"), min_value=0)
    amount_requested_in_dollars = CustomerFloatRangeField(verbose_name=_("Amount requested in dollars"), min_value=0)
    requested_date = models.DateField(verbose_name=_("Request date"))
    motif = models.CharField(max_length=255, verbose_name=_("Motif"), null=True, blank=True)
    description = models.TextField(verbose_name=_("Description"), null=True, blank=True)
    first_response_date = models.DateField(verbose_name=_("Date of first response"), null=True, blank=True)
    comment_linked_to_reply = models.TextField(verbose_name=_("Comment related to the request response"), null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, verbose_name=_("Status"))

    class Meta(object):
        app_label = 'financial'
        db_table = 'financial_disbursement_request'
        base_manager_name = 'objects'

    def __str__(self):
        return f'{self.project}/{self.requested_date.strftime("%d-%m-%Y")}/{self.amount_requested}'

    @property
    def year(self):
        return self.requested_date.year if self.requested_date else None

    @property
    def amount_validated(self):
        """Computed from DisbursementRequestValidation - never stored directly, so
        it can never drift from the validation-round history."""
        return self.validations.aggregate(total=models.Sum('amount_validated'))['total'] or 0

    @property
    def total_disbursed(self):
        return sum((disbursement.amount_disbursed or 0) for disbursement in self.disbursement_set.all())

    @property
    def available_balance(self):
        return self.amount_validated - self.total_disbursed


class DisbursementRequestValidation(ExternalIdMixin, SoftDeleteMixin, BaseModel):
    """History of validation rounds for a fund request: a request can be validated
    partially, then later receive the rest of what was originally requested in a
    separate round - each round is logged here so that history isn't lost.
    `DisbursementRequest.amount_validated` is entirely computed from these rows
    (see the property above); `status` is auto-derived to FULLY_VALIDATED/
    PARTIALLY_VALIDATED from the cumulative total vs. amount_requested whenever a
    round is added (see DisbursementRequestValidationCreateView) - manual edits to
    DisbursementRequest can only choose PENDING/REJECTED."""

    disbursement_request = models.ForeignKey(DisbursementRequest, on_delete=models.CASCADE, related_name='validations', verbose_name=_("Fund request"))
    validation_date = models.DateField(verbose_name=_("Validation date"))
    amount_validated = CustomerFloatRangeField(verbose_name=_("Amount validated (this round)"), min_value=0)
    status_after = models.CharField(max_length=20, choices=DisbursementRequest.Status.choices, verbose_name=_("Status after this validation"))
    comment = models.TextField(null=True, blank=True, verbose_name=_("Comment"))

    class Meta(object):
        app_label = 'financial'
        db_table = 'financial_disbursement_request_validation'
        ordering = ['validation_date']
        verbose_name = _("Fund request validation")
        verbose_name_plural = _("Fund request validations")
        base_manager_name = 'objects'

    def __str__(self):
        return f'{self.disbursement_request}/{self.validation_date.strftime("%d-%m-%Y")}/{self.amount_validated}'


class Disbursement(ExternalIdMixin, SoftDeleteMixin, BaseModel):
    class JustificationStatus(models.TextChoices):
        NOT_JUSTIFIED = 'NOT_JUSTIFIED', _('Not justified')
        PARTIALLY_JUSTIFIED = 'PARTIALLY_JUSTIFIED', _('Partially justified')
        FULLY_JUSTIFIED = 'FULLY_JUSTIFIED', _('Fully justified')

    disbursement_request = models.ForeignKey(DisbursementRequest, on_delete=models.CASCADE, verbose_name=_("This disbursement is related to the following request"))
    amount_disbursed = CustomerFloatRangeField(verbose_name=_("Amount disbursed"), min_value=0)
    amount_disbursed_in_dollars = CustomerFloatRangeField(verbose_name=_("Amount disbursed in dollars"), min_value=0)
    disbursement_date = models.DateField(verbose_name=_("Disbursement date"))
    description = models.TextField(verbose_name=_("Description"), null=True, blank=True)
    notes = models.TextField(verbose_name=_("Observations"), null=True, blank=True)
    justification_status = models.CharField(max_length=20, choices=JustificationStatus.choices, default=JustificationStatus.NOT_JUSTIFIED, verbose_name=_("Justification status"))

    class Meta(object):
        app_label = 'financial'
        db_table = 'financial_disbursement'
        base_manager_name = 'objects'

    def __str__(self):
        return f'{self.disbursement_request.project}/{self.disbursement_date.strftime("%d-%m-%Y")}/{self.amount_disbursed}' + (
            f' - {self.description}' if self.description else ''
        )

    @property
    def project(self):
        return self.disbursement_request.project if self.disbursement_request_id else None

    @property
    def funding(self):
        return self.disbursement_request.funding if self.disbursement_request_id else None

    @property
    def year(self):
        return self.disbursement_date.year if self.disbursement_date else None

    @property
    def justified_amount(self):
        return sum((doc.total_justified_amount or 0) for doc in self.supportingdocument_set.all())

    @property
    def justification_gap(self):
        return (self.amount_disbursed or 0) - self.justified_amount
