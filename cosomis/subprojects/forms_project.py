"""Formulaire complet d'un projet (création et modification) : page « Projets IDA » et admin.

En plus des champs du projet (nom, description, projet parent, statut, financeurs, niveaux administratifs), il
lie le projet aux facilitateurs et aux utilisateurs (tables du DCC, cf. project_links.py) : ce sont eux qui voient le
projet dans le DCC et dans COSOMIS.
"""
from django import forms
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from administrativelevels.functions_adl import get_multiple_administrative_hierarchies
from administrativelevels.models import AdministrativeLevel
from authentication.models import Facilitator
from cosomis import FORM_FIELDS_TO_EXCLUDE_WITH_EXTERNAL_ID

from .models import Financier, Project, sync_project_cycles
from .project_links import linked_ids, set_links


class FacilitatorChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        name = obj.name or obj.username
        return f"{name} ({obj.email})" if obj.email else name


class UserChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        name = obj.get_full_name() or obj.username
        return f"{name} ({obj.email})" if obj.email else name


def descendant_project_ids(project):
    """Le projet et tous ses sous-projets (un projet ne peut pas devenir le parent de l'un d'eux)."""
    ids, frontier = {project.pk}, [project.pk]
    while frontier:
        frontier = list(Project.objects.filter(parent_id__in=frontier).exclude(pk__in=ids).values_list('pk', flat=True))
        ids.update(frontier)
    return ids


class ProjectFullForm(forms.ModelForm):
    facilitators = FacilitatorChoiceField(
        queryset=Facilitator.objects.none(), required=False, label=_("Facilitators"),
        help_text=_("Facilitators working on this project (they see it in the DCC mobile app)."))
    users = UserChoiceField(
        queryset=User.objects.none(), required=False, label=_("Users"),
        help_text=_("Users who can select this project in the DCC and COSOMIS."))
    inherit_from_parent = forms.BooleanField(
        required=False, label=_("Also link the facilitators and users of the parent project"))

    class Meta:
        model = Project
        exclude = FORM_FIELDS_TO_EXCLUDE_WITH_EXTERNAL_ID
        labels = {'financiers': _("Financiers"), 'parent': _("Parent project")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = self.instance
        parents = Project.objects.all().order_by('name')
        if instance.pk:
            parents = parents.exclude(pk__in=descendant_project_ids(instance))
        self.fields['parent'].queryset = parents
        self.fields['financiers'].queryset = Financier.objects.all().order_by('name')
        self.fields['administrative_levels'].queryset = AdministrativeLevel.objects.select_related('parent').order_by('name')
        self.fields['administrative_levels'].help_text = _(
            "The villages of the chosen cantons and the parents of the chosen levels are added automatically; "
            "the cycles of the project follow these levels.")

        facilitator_ids = linked_ids(instance.pk, 'facilitators')
        user_ids = linked_ids(instance.pk, 'users')
        # comptes réels actifs, plus ceux déjà liés (même inactifs : ne pas les retirer sans le vouloir)
        self.fields['facilitators'].queryset = Facilitator.objects.filter(
            Q(active=True, develop_mode=False, training_mode=False) | Q(pk__in=facilitator_ids)).order_by('name', 'username')
        self.fields['users'].queryset = User.objects.filter(Q(is_active=True) | Q(pk__in=user_ids)).order_by(
            'first_name', 'last_name', 'username')
        if instance.pk:
            self.initial.setdefault('facilitators', facilitator_ids)
            self.initial.setdefault('users', user_ids)
        else:
            self.initial.setdefault('inherit_from_parent', True)
        self.inherited = {'facilitators': 0, 'users': 0}

    def clean_administrative_levels(self):
        levels = self.cleaned_data['administrative_levels']
        if levels:
            # villages des cantons + parents de chaque niveau, comme dans l'admin des projets
            levels = get_multiple_administrative_hierarchies([o.id for o in levels])
        return levels

    def clean(self):
        cleaned = super().clean()
        parent = cleaned.get('parent')
        if parent and cleaned.get('inherit_from_parent'):
            for kind, model in (('facilitators', Facilitator), ('users', User)):
                chosen = {o.pk for o in cleaned.get(kind) or []}
                extra = set(linked_ids(parent.pk, kind)) - chosen
                if extra:
                    cleaned[kind] = list(cleaned.get(kind) or []) + list(model.objects.filter(pk__in=extra))
                    self.inherited[kind] = len(extra)
        return cleaned

    def save_links(self, project):
        """Après l'enregistrement du projet et de ses champs multiples : facilitateurs, utilisateurs, cycles."""
        set_links(project.pk, 'facilitators', [o.pk for o in self.cleaned_data.get('facilitators') or []])
        set_links(project.pk, 'users', [o.pk for o in self.cleaned_data.get('users') or []])
        sync_project_cycles(project)
