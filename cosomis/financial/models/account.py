from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from cosomis.models_base import BaseModel, ExternalIdMixin, SoftDeleteMixin


class Account(ExternalIdMixin, SoftDeleteMixin, BaseModel):
    class AccountType(models.TextChoices):
        PROJECT = 'PROJECT', _('Project')
        REGIONAL_OFFICE = 'REGIONAL_OFFICE', _('Regional office')
        TOWN_HALL = 'TOWN_HALL', _('Town hall')
        CVD = 'CVD', _('CVD')
        PROJECT_SPECIALIST = 'PROJECT_SPECIALIST', _('Project specialist')
        SERVICE_PROVIDER = 'SERVICE_PROVIDER', _('Service provider')

    class AccountCategory(models.TextChoices):
        MAIN_ACCOUNT = 'MAIN_ACCOUNT', _('Main account')
        SUB_ACCOUNT = 'SUB_ACCOUNT', _('Sub-account')

    name = models.CharField(max_length=255, verbose_name=_("Name"))
    account_type = models.CharField(max_length=30, choices=AccountType.choices, verbose_name=_("Account type"))
    account_category = models.CharField(max_length=20, choices=AccountCategory.choices, verbose_name=_("Account category"))
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sub_accounts', verbose_name=_("Parent account"),
    )
    account_number = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("Account number"))
    contact = models.CharField(max_length=255, null=True, blank=True, verbose_name=_("Contact"))
    bank = models.ForeignKey('financial.Bank', on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Bank"))
    administrative_level = models.ForeignKey('administrativelevels.AdministrativeLevel', on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Administrative level"))
    cvd = models.ForeignKey('administrativelevels.CVD', on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("CVD"))
    notes = models.TextField(null=True, blank=True, verbose_name=_("Observations"))

    class Meta(object):
        app_label = 'financial'
        db_table = 'financial_account'
        verbose_name = _("Account")
        verbose_name_plural = _("Accounts")
        ordering = ['name']
        base_manager_name = 'objects'

    def __str__(self):
        return f"{self.get_account_type_display()}: {self.name} ({self.account_number})"

    def clean(self):
        if self.parent_id:
            if self.account_category != self.AccountCategory.SUB_ACCOUNT:
                raise ValidationError({'parent': _("Only a sub-account can have a parent account.")})
            if self.parent_id == self.pk:
                raise ValidationError({'parent': _("An account cannot be its own parent.")})
            if self.parent.account_category != self.AccountCategory.MAIN_ACCOUNT:
                raise ValidationError({'parent': _("The parent account must be a main account.")})
        super().clean()

    def balance_breakdown(self, year=None):
        """Full breakdown behind §2.14 "Soldes des comptes", matching the reference
        workbook's "Soldes des comptes" sheet columns exactly: total received,
        total sent, returned to sender, and available balance.

        For a PROJECT-type account, "total received" is the total amount
        disbursed for the project (there's no bank transfer *into* the project
        account in this workbook - money flows out from there) rather than
        incoming bank transfers. For every other actor type, "total received"
        is the sum of bank transfers received.

        `direction` only labels *why* a transfer happened (forward disbursement vs.
        contract-cancellation return) - the actual money movement is always
        sender -> recipient, so both directions count the same way for
        received/sent: a RETURN transfer is an outflow for its `sender` and an
        inflow for its `recipient`, exactly like a FORWARD one. `returned_to_sender`
        isolates the RETURN-direction outflows specifically (the amount this
        account has given back to whoever originally sent it funds).

        `available_balance` = total received - total sent (simplified - there is
        no more pending/executed/cancelled distinction now that BankTransfer has
        no status field)."""
        from django.db.models import Sum
        from financial.models.financial import BankTransfer, Disbursement

        sent_qs = BankTransfer.objects.filter(sender=self)
        returned_qs = BankTransfer.objects.filter(sender=self, direction=BankTransfer.Direction.RETURN)
        if year:
            sent_qs = sent_qs.filter(transfer_date__year=year)
            returned_qs = returned_qs.filter(transfer_date__year=year)
        total_sent = sent_qs.aggregate(total=Sum('amount_transferred'))['total'] or 0
        returned_to_sender = returned_qs.aggregate(total=Sum('amount_transferred'))['total'] or 0

        if self.account_type == self.AccountType.PROJECT:
            disbursements_qs = Disbursement.objects.all()
            if year:
                disbursements_qs = disbursements_qs.filter(disbursement_date__year=year)
            total_received = disbursements_qs.aggregate(total=Sum('amount_disbursed'))['total'] or 0
        else:
            received_qs = BankTransfer.objects.filter(recipient=self)
            if year:
                received_qs = received_qs.filter(transfer_date__year=year)
            total_received = received_qs.aggregate(total=Sum('amount_transferred'))['total'] or 0

        return {
            'total_received': total_received,
            'total_sent': total_sent,
            'returned_to_sender': returned_to_sender,
            'available_balance': total_received - total_sent,
        }

    def available_balance(self, year=None):
        return self.balance_breakdown(year=year)['available_balance']

    def allocation_summary(self, year=None):
        """Amount still owed to this account based on its administrative-level/CVD
        allocation (§2.14) vs. what's already been transferred to it - None if
        this account isn't linked to an administrative level or a CVD
        (allocations are never made directly to other actor types)."""
        from django.db.models import Sum
        from financial.models.allocation import AdministrativeLevelAllocation

        if self.administrative_level_id:
            allocation_qs = AdministrativeLevelAllocation.objects.filter(administrative_level_id=self.administrative_level_id)
        elif self.cvd_id:
            allocation_qs = AdministrativeLevelAllocation.objects.filter(cvd_id=self.cvd_id)
        else:
            return None

        if year:
            allocation_qs = allocation_qs.filter(allocation_date__year=year)

        allocated_amount = allocation_qs.aggregate(total=Sum('amount'))['total'] or 0
        transferred_amount = self.balance_breakdown(year=year)['total_received']
        return {
            'allocated_amount': allocated_amount,
            'transferred_amount': transferred_amount,
            'remaining_to_transfer': allocated_amount - transferred_amount,
        }
