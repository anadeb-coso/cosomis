"""Listes de référence des sous-projets : secteur (SubprojectSector, déjà créé en 0041 mais jamais utilisé), type
d'ouvrage (SubprojectType, idem), type de travaux (WorksType) et désignation (SubprojectTypeDesignation).

Les champs de Subproject deviennent des clés étrangères vers `name`, dans la MÊME colonne : les textes déjà rangés ne
changent pas (seul '' devient NULL). Chaque liste est remplie avec les valeurs réellement présentes dans les
sous-projets (plus les choix fixes du type de travaux et de la désignation), avant la pose des contraintes."""
from django.db import migrations, models
from django.db.models import F
import django.db.models.deletion

# Choix fixes au moment de la migration (subprojects/__init__.py : WORKS_TYPE_OF_SUB_PROJECT, SUB_PROJECT_TYPE_DESIGNATION)
WORKS_TYPES = [
    'Construction', 'Construction et équipement', 'Construction, réhabilitation et équipement', 'Equipement',
    'Réhabilitation', 'Réhabilitation et équipement',
]
DESIGNATIONS = ['Subproject', 'Infrastructure']


def check_pending_constraints(schema_editor):
    """PostgreSQL refuse un ALTER TABLE sur une table modifiée dans la même transaction tant que des contraintes
    différées (clés étrangères) restent à vérifier : on les vérifie maintenant, puis on revient au mode différé."""
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute('SET CONSTRAINTS ALL IMMEDIATE')
        schema_editor.execute('SET CONSTRAINTS ALL DEFERRED')


def make_existing_names_unique(apps, schema_editor):
    """`name` devient unique : un doublon déjà saisi (admin) reçoit le suffixe « (id) »."""
    db = schema_editor.connection.alias
    for model_name in ('SubprojectSector', 'SubprojectType'):
        Model = apps.get_model('subprojects', model_name)
        seen = set()
        for row in Model.objects.using(db).order_by('id'):
            if row.name in seen:
                row.name = f"{row.name} ({row.id})"
                row.save(update_fields=['name'])
            seen.add(row.name)
    check_pending_constraints(schema_editor)


def fill_reference_lists(apps, schema_editor):
    db = schema_editor.connection.alias
    Subproject = apps.get_model('subprojects', 'Subproject')
    for field in ('subproject_sector', 'type_of_subproject', 'works_type', 'subproject_type_designation'):
        Subproject.objects.using(db).filter(**{field: ''}).update(**{field: None})

    try:
        from cosomis.constants import SUB_PROJECT_SECTORS_COLOR, TYPES_OF_SUB_PROJECT_COLOR
    except ImportError:
        SUB_PROJECT_SECTORS_COLOR, TYPES_OF_SUB_PROJECT_COLOR = {}, {}

    for model_name, field, fixed, colors in (
        ('SubprojectSector', 'subproject_sector', [], SUB_PROJECT_SECTORS_COLOR),
        ('SubprojectType', 'type_of_subproject', [], TYPES_OF_SUB_PROJECT_COLOR),
        ('WorksType', 'works_type', WORKS_TYPES, None),
        ('SubprojectTypeDesignation', 'subproject_type_designation', DESIGNATIONS, None),
    ):
        Model = apps.get_model('subprojects', model_name)
        used = set(Subproject.objects.using(db).exclude(**{f'{field}__isnull': True}).values_list(field, flat=True).distinct())
        for name in sorted(used | set(fixed)):
            row, created = Model.objects.using(db).get_or_create(name=name)
            if colors is not None and created and colors.get(name):
                row.color = colors[name]
                row.save(update_fields=['color'])

    # secteur d'un type d'ouvrage : seulement s'il n'est utilisé que dans un secteur
    SubprojectSector = apps.get_model('subprojects', 'SubprojectSector')
    SubprojectType = apps.get_model('subprojects', 'SubprojectType')
    sectors_by_type = {}
    for type_name, sector_name in Subproject.objects.using(db).exclude(type_of_subproject__isnull=True).exclude(
            subproject_sector__isnull=True).values_list('type_of_subproject', 'subproject_sector').distinct():
        sectors_by_type.setdefault(type_name, set()).add(sector_name)
    for type_name, sector_names in sectors_by_type.items():
        if len(sector_names) == 1:
            SubprojectType.objects.using(db).filter(name=type_name, sector__isnull=True).update(
                sector=SubprojectSector.objects.using(db).get(name=next(iter(sector_names))))
    check_pending_constraints(schema_editor)


def restore_empty_texts(apps, schema_editor):
    """Retour arrière : les colonnes du sous-projet et name_fr / color des listes redeviennent non nulles (les valeurs
    des listes sont gardées)."""
    db = schema_editor.connection.alias
    Subproject = apps.get_model('subprojects', 'Subproject')
    for field in ('subproject_sector', 'type_of_subproject'):
        Subproject.objects.using(db).filter(**{f'{field}__isnull': True}).update(**{field: ''})
    for model_name in ('SubprojectSector', 'SubprojectType'):
        Model = apps.get_model('subprojects', model_name)
        Model.objects.using(db).filter(name_fr__isnull=True).update(name_fr=F('name'))
        Model.objects.using(db).filter(color__isnull=True).update(color='')
    check_pending_constraints(schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ('subprojects', '0073_project_db_table_process_manager'),
    ]

    operations = [
        migrations.RunPython(make_existing_names_unique, migrations.RunPython.noop),
        migrations.AlterModelOptions(
            name='subprojectsector',
            options={'ordering': ['name'], 'verbose_name': 'Subproject sector', 'verbose_name_plural': 'Subproject sectors'},
        ),
        migrations.AlterModelOptions(
            name='subprojecttype',
            options={'ordering': ['name'], 'verbose_name': 'Type of structure', 'verbose_name_plural': 'Types of structure'},
        ),
        migrations.AlterField(
            model_name='subprojectsector',
            name='name',
            field=models.CharField(max_length=255, unique=True, verbose_name='Name'),
        ),
        migrations.AlterField(
            model_name='subprojectsector',
            name='name_fr',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='subprojectsector',
            name='color',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Color'),
        ),
        migrations.AlterField(
            model_name='subprojecttype',
            name='name',
            field=models.CharField(max_length=255, unique=True, verbose_name='Name'),
        ),
        migrations.AlterField(
            model_name='subprojecttype',
            name='name_fr',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='subprojecttype',
            name='color',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Color'),
        ),
        migrations.AlterField(
            model_name='subprojecttype',
            name='sector',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='subprojects.subprojectsector', verbose_name='Subproject sector'),
        ),
        migrations.CreateModel(
            name='SubprojectTypeDesignation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_date', models.DateTimeField(auto_now_add=True, null=True)),
                ('updated_date', models.DateTimeField(auto_now=True, null=True)),
                ('create_by_user', models.JSONField(blank=True, null=True)),
                ('update_by_user', models.JSONField(blank=True, null=True)),
                ('delete_by_user', models.JSONField(blank=True, null=True)),
                ('users_involved', models.JSONField(blank=True, null=True)),
                ('name', models.CharField(max_length=255, unique=True, verbose_name='Name')),
            ],
            options={
                'verbose_name': 'Subproject type designation',
                'verbose_name_plural': 'Subproject type designations',
                'ordering': ['name'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='WorksType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_date', models.DateTimeField(auto_now_add=True, null=True)),
                ('updated_date', models.DateTimeField(auto_now=True, null=True)),
                ('create_by_user', models.JSONField(blank=True, null=True)),
                ('update_by_user', models.JSONField(blank=True, null=True)),
                ('delete_by_user', models.JSONField(blank=True, null=True)),
                ('users_involved', models.JSONField(blank=True, null=True)),
                ('name', models.CharField(max_length=255, unique=True, verbose_name='Name')),
            ],
            options={
                'verbose_name': 'Works type',
                'verbose_name_plural': 'Works types',
                'ordering': ['name'],
                'abstract': False,
            },
        ),
        # '' -> NULL : ces deux colonnes doivent d'abord accepter NULL
        migrations.AlterField(
            model_name='subproject',
            name='subproject_sector',
            field=models.CharField(max_length=100, null=True, verbose_name='Subproject sector'),
        ),
        migrations.AlterField(
            model_name='subproject',
            name='type_of_subproject',
            field=models.CharField(max_length=150, null=True, verbose_name='Type of structure'),
        ),
        migrations.RunPython(fill_reference_lists, restore_empty_texts),
        migrations.AlterField(
            model_name='subproject',
            name='subproject_sector',
            field=models.ForeignKey(db_column='subproject_sector', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='subprojects', to='subprojects.subprojectsector', to_field='name', verbose_name='Subproject sector'),
        ),
        migrations.AlterField(
            model_name='subproject',
            name='type_of_subproject',
            field=models.ForeignKey(db_column='type_of_subproject', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='subprojects', to='subprojects.subprojecttype', to_field='name', verbose_name='Type of structure'),
        ),
        migrations.AlterField(
            model_name='subproject',
            name='subproject_type_designation',
            field=models.ForeignKey(db_column='subproject_type_designation', default='Subproject', on_delete=django.db.models.deletion.PROTECT, related_name='subprojects', to='subprojects.subprojecttypedesignation', to_field='name', verbose_name='Subproject type designation (Subproject or Infrastructure)'),
        ),
        migrations.AlterField(
            model_name='subproject',
            name='works_type',
            field=models.ForeignKey(blank=True, db_column='works_type', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='subprojects', to='subprojects.workstype', to_field='name', verbose_name='Works type'),
        ),
    ]
