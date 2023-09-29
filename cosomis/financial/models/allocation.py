from django.db import models
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum, Q

from administrativelevels.models import AdministrativeLevel, CVD
from subprojects.models import Project, Component
from cosomis.customers_fields import CustomerFloatRangeField
from cosomis.models_base import BaseModel


    
class AdministrativeLevelAllocation(BaseModel):
    administrative_level = models.ForeignKey(AdministrativeLevel, on_delete=models.CASCADE, verbose_name=_("Administrative level"), null=True, blank=True)
    cvd = models.ForeignKey(CVD, on_delete=models.CASCADE, verbose_name=_("CVD"), null=True, blank=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, verbose_name=_("Project"))
    component = models.ForeignKey(Component, on_delete=models.CASCADE, verbose_name=_("Component (Subcomponent)"), null=True, blank=True)
    amount = CustomerFloatRangeField(verbose_name=_("Amount allocated"), min_value=0)
    amount_in_dollars = CustomerFloatRangeField(verbose_name=_("Amount allocated in dollars"), min_value=0)
    allocation_date = models.DateField(verbose_name=_("Allocation Date"), null=True, blank=True)
    amount_after_signature_of_contracts = CustomerFloatRangeField(verbose_name=_("Amount allocated after signature of contract(s) (This is only necessary if it's a CVD)"), min_value=0, null=True, blank=True)
    amount_in_dollars_after_signature_of_contracts = CustomerFloatRangeField(verbose_name=_("Amount allocated in dollars after signature of contract(s) (This is only necessary if it's a CVD)"), min_value=0, null=True, blank=True)
    allocation_date_after_signature_of_contracts = models.DateField(verbose_name=_("Allocation Date after signature of contract(s) (This is only necessary if it's a CVD)"), null=True, blank=True)
    description = models.TextField(verbose_name=_("Description"), null=True, blank=True)

    
    class Meta(object):
        app_label = 'financial'
        db_table = 'financial_administrativeLevel_allocation'
    
    def __str__(self) -> str:
        _str = ""
        if self.administrative_level:
            _str = f"{self.project}.ADL.{self.administrative_level}.{self.amount}"
        elif self.cvd:
            _str = f"{self.project}.CVD.{self.cvd}.{self.amount}"
        if _str:
            if self.allocation_date:
                return _str + f"{self.allocation_date.year}\
                    {self.allocation_date.month if self.allocation_date.year > 9 else ('0' + str(self.allocation_date.month))}\
                    {self.allocation_date.day if self.allocation_date.day > 9 else ('0' + str(self.allocation_date.day))}"
            return _str
        return self.amount

    def sum_amount_by_administrative_level(self):
        return AdministrativeLevelAllocation.objects.filter(
            Q(cvd_id=self.cvd.id) if self.cvd else Q(administrative_level_id=self.administrative_level.id)
        ).aggregate(Sum('amount'))['amount__sum']

    def sum_amount_in_dollars_by_administrative_level(self):
        return AdministrativeLevelAllocation.objects.filter(
            Q(cvd_id=self.cvd.id) if self.cvd else Q(administrative_level_id=self.administrative_level.id)
        ).aggregate(Sum('amount_in_dollars'))['amount_in_dollars__sum']

    def sum_amount_by_administrative_level_and_component(self, component_id):
        return AdministrativeLevelAllocation.objects.filter(
            Q(cvd_id=self.cvd.id) if self.cvd else Q(administrative_level_id=self.administrative_level.id),
            component_id=component_id
        ).aggregate(Sum('amount'))['amount__sum']

    def sum_amount_in_dollars_by_administrative_level_and_component(self, component_id):
        return AdministrativeLevelAllocation.objects.filter(
            Q(cvd_id=self.cvd.id) if self.cvd else Q(administrative_level_id=self.administrative_level.id),
            component_id=component_id
        ).aggregate(Sum('amount_in_dollars'))['amount_in_dollars__sum']

