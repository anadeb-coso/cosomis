from django.contrib import admin

from .models.allocation import AdministrativeLevelAllocation
from .models.bank import Bank
from .models.account import Account
from .models.funding import Funding
from .models.planning import AnnualWorkPlan, Activity
from .models.supporting_document import SupportingDocument, SupportingDocumentActivity
from .models.financial import BankTransfer, DisbursementRequest, DisbursementRequestValidation, Disbursement
# Register your models here.

class AdministrativeLevelAllocationAdmin(admin.ModelAdmin):
    fields = (
        'administrative_level',
        'project',
        'amount',
        'allocation_date',
        'description'
    )

    raw_id_fields = (
        'administrative_level',
    )
    list_display = (
        'id',
        'administrative_level',
        'project',
        'amount',
        'allocation_date'
    )
    search_fields = (
        'id',
        'administrative_level__name',
        'administrative_level__type',
        'project__name',
        'amount',
        'allocation_date',
        'description'
    )


class AccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'account_type', 'account_category', 'parent', 'account_number')
    list_filter = ('account_type', 'account_category')
    search_fields = ('name', 'account_number')
    raw_id_fields = ('parent', 'administrative_level', 'cvd')


admin.site.register(AdministrativeLevelAllocation, AdministrativeLevelAllocationAdmin)
admin.site.register(Bank)
admin.site.register(Account, AccountAdmin)
admin.site.register([
    Funding,
    AnnualWorkPlan,
    Activity,
    SupportingDocument,
    SupportingDocumentActivity,
    BankTransfer,
    DisbursementRequest,
    DisbursementRequestValidation,
    Disbursement,
])