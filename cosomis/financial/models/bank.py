from django.db import models
from django.utils.translation import gettext_lazy as _
from cosomis.models_base import BaseModel, SoftDeleteMixin



class Bank(SoftDeleteMixin, BaseModel):
    name = models.CharField(max_length=255, verbose_name=_("Name"))
    abbreviation = models.CharField(max_length=255, verbose_name=_("Abbreviation"))
    description = models.TextField(verbose_name=_("Description"), null=True, blank=True)

    class Meta(object):
        app_label = 'financial'
        db_table = 'financial_bank'
        unique_together = [['name'], ['abbreviation']]
        base_manager_name = 'objects'


    def __str__(self):
        return self.abbreviation

    @property
    def accounts_count(self):
        return self.account_set.count()

    def indicators(self, year=None):
        """Aggregate balance across every account held at this bank (§2.14
        'Soldes des comptes', rolled up per bank rather than per account)."""
        accounts = list(self.account_set.all())
        totals = {
            'accounts_count': len(accounts),
            'main_accounts_count': sum(1 for a in accounts if a.account_category == a.AccountCategory.MAIN_ACCOUNT),
            'sub_accounts_count': sum(1 for a in accounts if a.account_category == a.AccountCategory.SUB_ACCOUNT),
            'total_received': 0,
            'received_executed': 0,
            'total_sent': 0,
            'sent_executed': 0,
            'returned_to_sender': 0,
            'available_balance': 0,
        }
        for account in accounts:
            breakdown = account.balance_breakdown(year=year)
            for key in ('total_received', 'received_executed', 'total_sent', 'sent_executed', 'returned_to_sender', 'available_balance'):
                totals[key] += breakdown[key] or 0
        return totals