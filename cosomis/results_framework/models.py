"""Results framework: output, outcome and impact indicators per IDA project, and their measurements."""
from django.db import models
from django.utils.translation import gettext_lazy as _

from cosomis.models_base import BaseModel, SoftDeleteMixin


class ResultIndicator(SoftDeleteMixin, BaseModel):
    class IndicatorType(models.TextChoices):
        OUTPUT = 'OUTPUT', _('Output indicator')
        OUTCOME = 'OUTCOME', _('Outcome indicator')
        IMPACT = 'IMPACT', _('Impact indicator')

    project = models.ForeignKey('subprojects.Project', on_delete=models.CASCADE, related_name='result_indicators',
                                verbose_name=_("IDA project"))
    component = models.ForeignKey('subprojects.Component', null=True, blank=True, on_delete=models.SET_NULL,
                                  related_name='result_indicators', verbose_name=_("Component"))
    code = models.CharField(max_length=50, null=True, blank=True, verbose_name=_("Code"))
    label = models.CharField(max_length=500, verbose_name=_("Label"))
    indicator_type = models.CharField(max_length=20, choices=IndicatorType.choices, verbose_name=_("Type"))
    unit = models.CharField(max_length=50, null=True, blank=True, verbose_name=_("Unit"))
    baseline_value = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True, verbose_name=_("Baseline value"))
    baseline_year = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Baseline year"))
    target = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True, verbose_name=_("Target"))
    target_year = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Target year"))
    means_of_verification = models.TextField(null=True, blank=True, verbose_name=_("Means of verification"))
    frequency = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("Collection frequency"))
    responsible = models.CharField(max_length=255, null=True, blank=True, verbose_name=_("Responsible for collection"))
    description = models.TextField(null=True, blank=True, verbose_name=_("Definition"))

    class Meta:
        verbose_name = _("Results framework indicator")
        verbose_name_plural = _("Results framework indicators")
        ordering = ['project', 'indicator_type', 'code']
        base_manager_name = 'objects'

    def __str__(self):
        return f"{self.code} - {self.label}" if self.code else self.label

    @property
    def latest_measurement(self):
        return self.measurements.order_by('-date').first()

    @property
    def achievement_rate(self):
        """(Achieved - baseline) / (target - baseline), in %."""
        measurement = self.latest_measurement
        if measurement is None or self.target is None:
            return None
        baseline = self.baseline_value or 0
        if self.target == baseline:
            return None
        return round((measurement.value - baseline) / (self.target - baseline) * 100, 1)


class IndicatorMeasurement(BaseModel):
    indicator = models.ForeignKey(ResultIndicator, on_delete=models.CASCADE, related_name='measurements',
                                  verbose_name=_("Indicator"))
    date = models.DateField(verbose_name=_("Measurement date"))
    value = models.DecimalField(max_digits=18, decimal_places=2, verbose_name=_("Achieved value"))
    source = models.TextField(null=True, blank=True, verbose_name=_("Source"))
    comment = models.TextField(null=True, blank=True, verbose_name=_("Comment"))

    class Meta:
        verbose_name = _("Indicator measurement")
        verbose_name_plural = _("Indicator measurements")
        ordering = ['indicator', '-date']
        constraints = [models.UniqueConstraint(fields=['indicator', 'date'], name='unique_measurement_per_date')]

    def __str__(self):
        return f"{self.indicator} : {self.value} ({self.date:%d/%m/%Y})"
