from django.utils.translation import gettext_lazy as _
from django.contrib import admin
from django import forms
from .models import *
from administrativelevels.widgets import AdministrativeLevelSelectWidget
from administrativelevels.models import AdministrativeLevel
from administrativelevels.functions_adl import (
    get_cascade_villages_ids_by_administrative_level_id, 
    get_multiple_administrative_hierarchies,
    get_multiple_administrative_hierarchies_ids
)
from cosomis import FORM_FIELDS_TO_EXCLUDE
from django.db import connection


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        exclude = FORM_FIELDS_TO_EXCLUDE

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # self.fields['administrative_levels'].widget = CustomAdminWidget()
    
    def clean_administrative_levels(self):
        administrative_levels = self.cleaned_data['administrative_levels']
        # villages_ids = []
        if administrative_levels:
            # villages_ids = get_cascade_villages_ids_by_administrative_level_id([o.id for o in administrative_levels])
            administrative_levels = get_multiple_administrative_hierarchies([o.id for o in administrative_levels])
        
        # return AdministrativeLevel.objects.filter(id__in=villages_ids)
        return administrative_levels

    # def save(self, commit=True):
    #     instance = super(ProjectForm, self).save(commit=False)

    #     if commit:
    #         self.save_m2m()
    #     instance = instance.save_and_return_object()

    #     if instance.id and instance.administrative_levels.all().exists():
    #         cycle = Cycle.objects.filter(project_id=instance.id).first()
    #         if not cycle:
    #             cycle = Cycle.objects.create(
    #                 name="Cycle 1",
    #                 description=f"Cycle 1 du projet ({instance.name})",
    #                 project_id=instance.id
    #             )
    #             cycle.administrative_levels.set(instance.administrative_levels.all())
    #             cycle.save()

    #     return instance
    

class ProjectFormAdmin(admin.ModelAdmin):
    form = ProjectForm
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ("name", "description", "parent", "financiers", "administrative_levels"),
        }),
    )
    fieldsets = (
        (None, {
            'fields': ("name", "description", "parent", "financiers", "administrative_levels")
        }),
    )
    list_display = ("name", "description", "parent")

    search_fields = ("id", "name", "description", "parent", "financiers", "administrative_levels"),
    
    # raw_id_fields = (
    #     'administrative_levels',
    # )
    # autocomplete_fields = ['administrative_levels']
    filter_horizontal  = ['administrative_levels']

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "administrative_levels":
            kwargs["queryset"] = AdministrativeLevel.objects.all().order_by('name')
            # kwargs['label_from_instance '] = lambda obj: f"{obj.name} ({obj.name})"
        return super().formfield_for_manytomany(db_field, request, **kwargs)





class CycleForm(forms.ModelForm):
    class Meta:
        model = Cycle
        exclude = FORM_FIELDS_TO_EXCLUDE

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def clean_administrative_levels(self):
        project = self.cleaned_data['project']
        administrative_levels = self.cleaned_data['administrative_levels']

        project_administrative_levels = set(project.administrative_levels.values_list('id', flat=True))

        common_cycle_adl_ids = []
        if administrative_levels:
            descendant_ids, ancestor_ids, level_ids = get_multiple_administrative_hierarchies_ids([o.id for o in administrative_levels])
            cycle_administrative_levels = set(descendant_ids + ancestor_ids + level_ids) #set(get_cascade_villages_ids_by_administrative_level_id([o.id for o in administrative_levels]))

            # Identifier les ID présents dans le cycle mais pas dans le projet
            common_cycle_adl_ids = project_administrative_levels & cycle_administrative_levels
        else:
            common_cycle_adl_ids = project_administrative_levels

        return AdministrativeLevel.objects.filter(id__in=common_cycle_adl_ids)

class CycleFormAdmin(admin.ModelAdmin):
    form = CycleForm
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ("name", "description", "project", "administrative_levels"),
        }),
    )
    fieldsets = (
        (None, {
            'fields': ("name", "description", "project", "administrative_levels")
        }),
    )
    list_display = ("name", "description", "project")

    search_fields = ("id", "name", "description", "project", "administrative_levels"),
    
    filter_horizontal  = ['administrative_levels']

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "administrative_levels":
            kwargs["queryset"] = AdministrativeLevel.objects.all().order_by('name')
        return super().formfield_for_manytomany(db_field, request, **kwargs)

"""
wording = models.CharField(max_length=200, verbose_name=_("Wording"))
    percent = CustomerFloatRangeField(null=True, blank=True, verbose_name=_("Percent"), min_value=0, max_value=100)
    description = models.TextField(null=True, blank=True, verbose_name=_("Description"))
    ranking = models.FloatField(default=0, verbose_name=_("Ranking"))
    amount_spent_at_this_step = models.FloatField(null=True, blank=True, verbose_name=_("Amount spent at this stage"))
    total_amount_spent = models.FloatField(null=True, blank=True, verbose_name=_("Total amount spent"))
    has_levels = models.BooleanField(default=False, verbose_name=_("Has levels"))
    color = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("Color (hexadecimal)"))
    
"""
class StepAdmin(admin.ModelAdmin):
    fields = (
        'wording',
        'percent',
        'description',
        'ranking',
        'amount_spent_at_this_step',
        'total_amount_spent',
        'has_levels',
        'color',
        'next_steps'
    )
    autocomplete_fields = ['next_steps']
    list_display = (
        'id',
        'wording',
        'percent',
        'description',
        'ranking',
        'amount_spent_at_this_step',
        'total_amount_spent',
        'has_levels',
        'color'
    )
    search_fields = (
        'id',
        'wording',
        'percent',
        'description',
        'ranking',
        'has_levels',
        'color'
    )

    def get_queryset(self, request):
        return super().get_queryset(request).order_by('ranking')
    

# Register your models here.
admin.site.register([
    Subproject, 
    VulnerableGroup,
    VillagePriority,
    VillageMeeting,
    Component,
    VillageObstacle,
    VillageGoal,
    Financier,
    SubprojectSector,
    SubprojectType    
])

admin.site.register(Project, ProjectFormAdmin)
admin.site.register(Cycle, CycleFormAdmin)
admin.site.register(Step, StepAdmin)