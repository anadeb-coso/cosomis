from django.db import models
from django.utils.translation import gettext_lazy as _

from cosomis.models_base import BaseModel, ExternalIdMixin, SoftDeleteMixin


class AnnualWorkPlan(ExternalIdMixin, SoftDeleteMixin, BaseModel):
    project = models.ForeignKey('subprojects.Project', on_delete=models.CASCADE, verbose_name=_("IDA Project"))
    period = models.IntegerField(verbose_name=_("Period (year)"))
    name = models.CharField(max_length=255, verbose_name=_("Label"))
    notes = models.TextField(null=True, blank=True, verbose_name=_("Observations"))

    class Meta(object):
        app_label = 'financial'
        db_table = 'financial_annual_work_plan'
        verbose_name = _("Annual work plan")
        verbose_name_plural = _("Annual work plans")
        base_manager_name = 'objects'

    def __str__(self):
        return f'{self.name} ({self.period})'

    @property
    def budgeted_amount(self):
        return sum((activity.amount or 0) for activity in self.activity_set.all())

    @property
    def justified_amount(self):
        return sum((activity.justified_amount or 0) for activity in self.activity_set.all())

    @property
    def available_amount(self):
        return (self.budgeted_amount or 0) - self.justified_amount


class Activity(ExternalIdMixin, SoftDeleteMixin, BaseModel):
    component = models.ForeignKey('subprojects.Component', on_delete=models.CASCADE, verbose_name=_("Component / Sub-component"))
    annual_work_plan = models.ForeignKey(AnnualWorkPlan, on_delete=models.CASCADE, verbose_name=_("Annual work plan"))
    name = models.CharField(max_length=255, verbose_name=_("Label"))
    amount = models.FloatField(verbose_name=_("Amount"))
    target = models.TextField(null=True, blank=True, verbose_name=_("Target(s)"))

    class Meta(object):
        app_label = 'financial'
        db_table = 'financial_activity'
        verbose_name = _("Activity")
        verbose_name_plural = _("Activities")
        base_manager_name = 'objects'

    def __str__(self):
        return self.name

    @property
    def justified_amount(self):
        return sum((line.allocated_amount or 0) for line in self.supportingdocumentactivity_set.all())

    @property
    def balance_to_justify(self):
        return (self.amount or 0) - self.justified_amount
