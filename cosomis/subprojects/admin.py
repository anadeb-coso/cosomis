from django.utils.translation import gettext_lazy as _
from django.contrib import admin, messages
from django import forms
from .models import *
from administrativelevels.widgets import AdministrativeLevelSelectWidget
from administrativelevels.models import AdministrativeLevel
from administrativelevels.functions_adl import (
    get_cascade_villages_ids_by_administrative_level_id, 
    get_multiple_administrative_hierarchies,
    get_multiple_administrative_hierarchies_ids
)
from cosomis import FORM_FIELDS_TO_EXCLUDE, FORM_FIELDS_TO_EXCLUDE_WITH_EXTERNAL_ID
from .forms_project import ProjectFullForm
from django.db import connection
from django.db.models import Count


class ProjectFormAdmin(admin.ModelAdmin):
    # Formulaire complet partagé avec la page « Projets IDA » (subprojects/forms_project.py) : statut,
    # facilitateurs et utilisateurs liés en plus des champs du projet.
    form = ProjectFullForm
    fieldsets = (
        (None, {
            'fields': ("name", "description", "parent", "status", "financiers", "administrative_levels")
        }),
        (_("Facilitators and users"), {
            'fields': ("facilitators", "users", "inherit_from_parent")
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
            kwargs["queryset"] = AdministrativeLevel.objects.select_related('parent').order_by('name')
            # kwargs['label_from_instance '] = lambda obj: f"{obj.name} ({obj.name})"
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # même sélecteur à deux listes que les niveaux administratifs (filter_horizontal)
        from django.contrib.admin.widgets import FilteredSelectMultiple
        import copy
        for name in ('facilitators', 'users'):
            # copie : le champ déclaré est partagé avec le formulaire de la page « Projets IDA »
            field = form.base_fields[name] = copy.deepcopy(form.base_fields[name])
            field.widget = FilteredSelectMultiple(field.label, False)
        return form

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.save_links(form.instance)
        if form.inherited['facilitators'] or form.inherited['users']:
            messages.info(request, _("%(facilitators)s facilitator(s) and %(users)s user(s) of the parent project were "
                                     "also linked.") % form.inherited)





class CycleForm(forms.ModelForm):
    """Niveaux administratifs d'un cycle : seulement ceux de son projet.
    - un canton AJOUTÉ apporte tous ses villages ; un canton déjà dans le cycle n'en rajoute pas (on peut donc retirer
      un village sans qu'il revienne) ;
    - les parents des niveaux choisis (canton, commune... jusqu'à la région) sont ajoutés ;
    - aucun niveau choisi : tous les niveaux du projet.
    Auparavant, les niveaux hors du projet étaient écartés sans message et chaque canton du cycle remettait tous ses
    villages : l'enregistrement annonçait un succès sans rien changer."""
    class Meta:
        model = Cycle
        exclude = FORM_FIELDS_TO_EXCLUDE

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # niveaux ajoutés d'office, et sélection vide remplacée par tout le projet : signalés après l'enregistrement
        self.auto_added_levels = []
        self.whole_project_assigned = False
        if 'administrative_levels' in self.fields:
            self.fields['administrative_levels'].help_text = _(
                "Only the administrative levels of the project. A canton added to the cycle brings all its villages; "
                "the parents of the chosen levels are added automatically. No level chosen: all the levels of the project.")

    def clean_administrative_levels(self):
        project = self.cleaned_data.get('project')
        administrative_levels = self.cleaned_data['administrative_levels']
        if project is None:
            return administrative_levels  # erreur déjà signalée sur le projet

        project_administrative_levels = set(project.administrative_levels.values_list('id', flat=True))
        if not project_administrative_levels:
            raise forms.ValidationError(_(
                "The project %(project)s has no administrative level: add its administrative levels to the project "
                "first, then to the cycle."), params={'project': project.name})

        if not administrative_levels:
            self.whole_project_assigned = True
            return AdministrativeLevel.objects.filter(id__in=project_administrative_levels)

        selected_ids = {o.id for o in administrative_levels}
        outside = [o for o in administrative_levels if o.id not in project_administrative_levels]
        if outside:
            names = ', '.join(f'{o.name} ({o.type})' for o in sorted(outside, key=lambda o: o.name)[:15])
            raise forms.ValidationError(_(
                "%(count)s administrative level(s) are not part of the project %(project)s: %(names)s. Add them to the "
                "project first, or remove them from the cycle."),
                params={'count': len(outside), 'project': project.name, 'names': names + (' …' if len(outside) > 15 else '')})

        previous_ids = set(self.instance.administrative_levels.values_list('id', flat=True)) if self.instance.pk else set()
        added_cantons = [o.id for o in administrative_levels if o.type == 'Canton' and o.id not in previous_ids]
        villages_of_added_cantons = get_multiple_administrative_hierarchies_ids(added_cantons)[0] if added_cantons else []
        ancestor_ids = get_multiple_administrative_hierarchies_ids(list(selected_ids), search_descendants_for=[])[1]

        cycle_ids = (selected_ids | set(villages_of_added_cantons) | set(ancestor_ids)) & project_administrative_levels
        self.auto_added_levels = sorted(cycle_ids - selected_ids)
        return AdministrativeLevel.objects.filter(id__in=cycle_ids)

class CycleFormAdmin(admin.ModelAdmin):
    form = CycleForm
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            # `order` : unique par projet (Cycle.Meta.unique_together) ; absent du formulaire, il valait toujours 1 et un
            # deuxième cycle du projet provoquait une erreur 500 au lieu d'un message
            'fields': ("name", "description", "project", "order", "administrative_levels"),
        }),
    )
    fieldsets = (
        (None, {
            'fields': ("name", "description", "project", "order", "administrative_levels")
        }),
    )
    list_display = ("name", "description", "project")

    search_fields = ("id", "name", "description", "project", "administrative_levels"),
    
    filter_horizontal  = ['administrative_levels']

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "administrative_levels":
            kwargs["queryset"] = AdministrativeLevel.objects.all().order_by('name')
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        if getattr(form, 'whole_project_assigned', False):
            messages.info(request, _("No administrative level chosen: all the administrative levels of the project "
                                     "%(project)s were assigned to the cycle.") % {'project': form.instance.project.name})
        elif getattr(form, 'auto_added_levels', None):
            messages.info(request, _("%(count)s administrative level(s) added automatically: villages of the added "
                                     "cantons and parents of the chosen levels.") % {'count': len(form.auto_added_levels)})

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
    CategoryIDA,
    VillageObstacle,
    VillageGoal,
    Financier,
])


class SubprojectReferenceValueAdmin(admin.ModelAdmin):
    """Listes de référence des sous-projets : renommer une valeur la renomme sur ses sous-projets ; une valeur
    utilisée ne peut pas être supprimée."""
    exclude = FORM_FIELDS_TO_EXCLUDE
    search_fields = ('name',)
    list_display = ('name', 'subprojects_count')

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_subprojects_count=Count('subprojects'))

    @admin.display(description=_("Subprojects"), ordering='_subprojects_count')
    def subprojects_count(self, obj):
        return obj._subprojects_count


class SubprojectSectorAdmin(SubprojectReferenceValueAdmin):
    list_display = ('name', 'color', 'subprojects_count')


class SubprojectTypeAdmin(SubprojectReferenceValueAdmin):
    list_display = ('name', 'sector', 'beneficiary_sector', 'regroup', 'estimated_cost', 'color', 'subprojects_count')
    list_filter = ('sector', 'beneficiary_sector', 'regroup', 'donation_certificate')
    list_select_related = ('sector', 'beneficiary_sector', 'regroup')
    search_fields = ('name', 'name_fr', 'old_name')


class SubprojectTypeRegroupAdmin(admin.ModelAdmin):
    exclude = FORM_FIELDS_TO_EXCLUDE
    search_fields = ('name',)
    list_display = ('name', 'types_count')

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_types_count=Count('subproject_types'))

    @admin.display(description=_("Types of structure"), ordering='_types_count')
    def types_count(self, obj):
        return obj._types_count


admin.site.register(SubprojectSector, SubprojectSectorAdmin)
admin.site.register(SubprojectType, SubprojectTypeAdmin)
admin.site.register(SubprojectTypeRegroup, SubprojectTypeRegroupAdmin)
admin.site.register(WorksType, SubprojectReferenceValueAdmin)
admin.site.register(SubprojectTypeDesignation, SubprojectReferenceValueAdmin)

admin.site.register(Project, ProjectFormAdmin)
admin.site.register(Cycle, CycleFormAdmin)
admin.site.register(Step, StepAdmin)