from django.core.exceptions import ValidationError
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
        # Only top-level activities: a parent activity's effective_amount already
        # cumulates its children's, so summing every row would double-count them.
        return sum((activity.effective_amount or 0) for activity in self.activity_set.filter(parent__isnull=True))

    @property
    def justified_amount(self):
        return sum((activity.justified_amount or 0) for activity in self.activity_set.all())

    @property
    def available_amount(self):
        return (self.budgeted_amount or 0) - self.justified_amount


class Tag(SoftDeleteMixin, BaseModel):
    """A free-form label for an activity's responsible/involved structure (e.g. a
    ministry directorate, a town hall, an NGO...) - not tied to any existing
    referential model, since the reference workbook itself only ever lists these
    as loose bullet-point text ("- Structure A") with no ID of their own. Shared
    by both Activity.structures_responsables and .structures_impliquees, so the
    same Tag can be reused across activities and across either relation."""

    name = models.CharField(max_length=255, unique=True, verbose_name=_("Name"))

    class Meta(object):
        app_label = 'financial'
        db_table = 'financial_tag'
        verbose_name = _("Tag")
        verbose_name_plural = _("Tags")
        ordering = ['name']
        base_manager_name = 'objects'

    def __str__(self):
        return self.name


class Activity(ExternalIdMixin, SoftDeleteMixin, BaseModel):
    class Status(models.TextChoices):
        NOT_STARTED = 'NOT_STARTED', _('Not started')
        IN_PROGRESS = 'IN_PROGRESS', _('In progress')
        INTERRUPTED = 'INTERRUPTED', _('Interrupted')
        ABANDONED = 'ABANDONED', _('Abandoned')
        COMPLETED = 'COMPLETED', _('Completed')

    component = models.ForeignKey('subprojects.Component', on_delete=models.CASCADE, verbose_name=_("Component / Sub-component"))
    annual_work_plan = models.ForeignKey(AnnualWorkPlan, on_delete=models.CASCADE, verbose_name=_("Annual work plan"))
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True, related_name='children',
        verbose_name=_("Parent activity"),
        help_text=_("A parent activity's amount is the cumulative total of its child activities."),
    )
    code = models.CharField(max_length=50, null=True, blank=True, verbose_name=_("Code"))
    name = models.CharField(max_length=255, verbose_name=_("Label"))
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOT_STARTED, verbose_name=_("Status"))
    amount = models.FloatField(null=True, blank=True, verbose_name=_("Amount"))
    budget_previsionnel = models.FloatField(null=True, blank=True, verbose_name=_("Projected budget"))
    target = models.TextField(null=True, blank=True, verbose_name=_("Target(s)"))
    resultats = models.TextField(null=True, blank=True, verbose_name=_("Results"))
    indicateurs = models.TextField(null=True, blank=True, verbose_name=_("Indicators"))
    unite = models.TextField(null=True, blank=True, verbose_name=_("Unit"))
    valeur_cible = models.TextField(null=True, blank=True, verbose_name=_("Target value"))
    structures_responsables = models.ManyToManyField(Tag, blank=True, related_name='responsible_activities', verbose_name=_("Responsible structures"))
    structures_impliquees = models.ManyToManyField(Tag, blank=True, related_name='involved_activities', verbose_name=_("Involved structures"))
    # blank=True is required here, not just default=False: without it Django's
    # ModelForm makes each checkbox "required", so leaving a month unchecked (the
    # normal case for most activities) would fail form validation entirely.
    month_jan = models.BooleanField(default=False, blank=True, verbose_name=_("Jan."))
    month_feb = models.BooleanField(default=False, blank=True, verbose_name=_("Feb."))
    month_mar = models.BooleanField(default=False, blank=True, verbose_name=_("Mar."))
    month_apr = models.BooleanField(default=False, blank=True, verbose_name=_("Apr."))
    month_may = models.BooleanField(default=False, blank=True, verbose_name=_("May"))
    month_jun = models.BooleanField(default=False, blank=True, verbose_name=_("Jun."))
    month_jul = models.BooleanField(default=False, blank=True, verbose_name=_("Jul."))
    month_aug = models.BooleanField(default=False, blank=True, verbose_name=_("Aug."))
    month_sep = models.BooleanField(default=False, blank=True, verbose_name=_("Sep."))
    month_oct = models.BooleanField(default=False, blank=True, verbose_name=_("Oct."))
    month_nov = models.BooleanField(default=False, blank=True, verbose_name=_("Nov."))
    month_dec = models.BooleanField(default=False, blank=True, verbose_name=_("Dec."))

    class Meta(object):
        app_label = 'financial'
        db_table = 'financial_activity'
        verbose_name = _("Activity")
        verbose_name_plural = _("Activities")
        base_manager_name = 'objects'
        constraints = [
            models.UniqueConstraint(fields=['annual_work_plan', 'code'], name='unique_activity_code_per_annual_work_plan'),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        if self.parent_id:
            if self.parent_id == self.id:
                raise ValidationError(_("An activity cannot be its own parent."))
            # annual_work_plan isn't a form field (it's fixed from the URL and only
            # assigned on the instance after the form validates - see
            # ActivityCreateView.post()), so it's still unset at validation time on
            # create; only enforce the match once both sides are actually known.
            if self.annual_work_plan_id and self.parent.annual_work_plan_id != self.annual_work_plan_id:
                raise ValidationError(_("A parent activity must belong to the same annual work plan."))
        super().clean()

    def save(self, *args, **kwargs):
        # Blank submitted as '' (not None) would otherwise count as a real value for
        # the unique_activity_code_per_annual_work_plan constraint (MySQL only treats
        # NULL, not '', as exempt from uniqueness) - normalize so multiple activities
        # can still be left without a code.
        if self.code == '':
            self.code = None
        super().save(*args, **kwargs)

    @property
    def effective_amount(self):
        """Own amount, unless this activity has children - then it's the
        cumulative total of its children's own effective_amount (mirrors
        Component.effective_amount's "own value unless it has children" rule)."""
        if self.pk:
            children = list(self.children.all())
            if children:
                return sum((child.effective_amount or 0) for child in children)
        return self.amount or 0

    @property
    def justified_amount(self):
        return sum((line.allocated_amount or 0) for line in self.supportingdocumentactivity_set.all())

    @property
    def balance_to_justify(self):
        return (self.effective_amount or 0) - self.justified_amount


class ActivityFunding(ExternalIdMixin, SoftDeleteMixin, BaseModel):
    """How much of an Activity's cost is imputed to a given Funding (§
    Activités-CréditDon) - an activity may be financed by 0, 1 or several
    Crédits & Dons of its project, each with its own amount."""

    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, verbose_name=_("Activity"))
    funding = models.ForeignKey('financial.Funding', on_delete=models.CASCADE, verbose_name=_("Credit/Grant"))
    amount = models.FloatField(verbose_name=_("Amount"))

    class Meta(object):
        app_label = 'financial'
        db_table = 'financial_activity_funding'
        verbose_name = _("Activity / Funding allocation")
        verbose_name_plural = _("Activity / Funding allocations")
        base_manager_name = 'objects'
        unique_together = [['activity', 'funding']]

    def __str__(self):
        return f'{self.activity} / {self.funding} / {self.amount}'
