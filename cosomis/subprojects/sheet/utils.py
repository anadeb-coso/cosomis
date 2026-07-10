from django.db.models.fields.related import ForeignKey, ManyToManyField
from django.db.models import Field, NOT_PROVIDED
from django.apps import apps
from subprojects.models import Subproject
from cosomis import TABLE_SHEET_FIELDS_TO_EXCLUDE, FORM_FIELDS_TO_EXCLUDE


subproject_fields = Subproject._meta.get_fields()

# Récupération des champs obligatoires

subproject_required_fields = [
    (f.name, f.verbose_name) for f in subproject_fields
    if isinstance(f, Field) and (
        (
            f.blank is False and f.null is False and f.default in [NOT_PROVIDED, None]
        ) 
        # or (
        #     f.name in [
        #         'number',
        #         'joint_subproject_number',
        #         'projects',
        #         'location_subproject_realized',
        #         'subproject_type_designation',
        #         'works_type',
        #         'estimated_cost',
        #         'current_status_of_the_site',
        #         'component'
        #     ]
        # )
    )
]

# Récupération des champs ForeignKey
fk_fields = [(f.name, f.related_model.__name__, 'ForeignKey') for f in subproject_fields if isinstance(f, ForeignKey) and f.name not in TABLE_SHEET_FIELDS_TO_EXCLUDE]
subproject_fk_fields_names = [f_name_fk[0] for f_name_fk in fk_fields]

# Récupération des champs ManyToManyField
m2m_fields = [(f.name, f.related_model.__name__, 'ManyToManyField') for f in subproject_fields if isinstance(f, ManyToManyField) and f.name not in TABLE_SHEET_FIELDS_TO_EXCLUDE]
subproject_m2m_fields_names = [f_name_m2m[0] for f_name_m2m in m2m_fields]

# On garde les noms des champs FK ID
base_fields_to_include = [f.name for f in Subproject._meta.concrete_fields if not isinstance(f, ForeignKey) and f.name not in (TABLE_SHEET_FIELDS_TO_EXCLUDE+FORM_FIELDS_TO_EXCLUDE)]

# ['location_subproject_realized', 'cvd', 'canton', 'link_to_subproject', 'component']
# # Liste des champs liés à ajouter
model_has_parent_attribute = []
final_fk_fields = []
for fk_name, fk_model_name, fk_type in fk_fields:
    if fk_model_name.lower() == 'Subproject'.lower():
        base_fields_to_include += [
            f"{fk_name}__location_subproject_realized__name", 
            f"{fk_name}__location_subproject_realized__parent__name"
        ]
    
    related_field_name = f"{fk_name}__id"
    if related_field_name not in base_fields_to_include:
        base_fields_to_include.append(related_field_name)

    ClassModal = None
    for app_conf in apps.get_app_configs():
        try:
            ClassModal = app_conf.get_model(fk_model_name)
            break # stop as soon as it is found
        except LookupError:
            # no such model in this application
            pass
    
    if ClassModal:
        name = 'name'
        if hasattr(ClassModal, 'full_title_of_approved_subproject'):
            name = 'full_title_of_approved_subproject'
        elif hasattr(ClassModal, 'wording'):
            name = 'wording'
        elif hasattr(ClassModal, 'libelle'):
            name = 'libelle'
        
        if hasattr(ClassModal, 'parent'):
            base_fields_to_include.append(f"{fk_name}__parent__{name}")
            model_has_parent_attribute.append(fk_model_name)

        related_field_name = f"{fk_name}__{name}"
        if related_field_name not in base_fields_to_include:
            base_fields_to_include.append(related_field_name)
        
        final_fk_fields.append((fk_name, fk_model_name, fk_type, related_field_name))

fields_list = list(set(base_fields_to_include))
m2m_fields_names = [f_name_m2m[0] for f_name_m2m in m2m_fields]






