"""Chargement groupé de ce que les sérialiseurs de l'API mobile lisent pour chaque élément d'une page (niveaux
administratifs, CVD, sous-projets), pour des réponses IDENTIQUES à celles calculées élément par élément.

Règle suivie : seules les lectures « par clé » sont groupées (objet lié, compteurs, fichiers d'un sous-projet...).
Les requêtes sans ORDER BY qui décident de l'ordre d'une liste de la réponse (sous-projets liés, villages d'un CVD)
restent les mêmes requêtes qu'avant ; quand une liste triée a des ex aequo, sa requête d'origine est rejouée pour
garder exactement son ordre. Exception : les listes many-to-many des sous-projets, groupées avec un ordre désormais
fixé (SUBPROJECT_MANY_TO_MANY_ORDER)."""
from collections import defaultdict

from django.db.models import Case, Count, IntegerField, Q, Value, When, prefetch_related_objects

from assignments.functions import get_subprojects_by_facilitator_id_and_project_id
from cosomis.constants import IMAGE_EXTENSIONS, STRUCTURE_IN_PROGRESS_RANKING_LIST, STRUCTURE_IN_PROGRESS_STATUS
from subprojects.models import FileComment, Level, Subproject, SubprojectFile, SubprojectStep

# Ordre des fichiers d'un sous-projet dans l'API : non validés, validés, sans avis ; puis les plus récents
FILE_ORDER = Case(
    When(validated=False, then=Value(1)),
    When(validated=True, then=Value(2)),
    When(validated=None, then=Value(3)),
    default=Value(4),
    output_field=IntegerField(),
)

# Niveau administratif sérialisé : unité géographique, CVD (et son unité), puis les mêmes pour chaque parent
ADMINISTRATIVE_LEVEL_LOOKUPS = [
    'parent__' * depth + lookup
    for depth in range(6)
    for lookup in ('geographical_unit', 'cvd__geographical_unit')
]


def prefetch_administrative_levels_for_api(administrative_levels):
    """Unités géographiques, CVD et parents (jusqu'à la région) des niveaux, en une requête par relation et par
    profondeur au lieu de plusieurs par niveau."""
    administrative_levels = [adl for adl in administrative_levels if adl is not None]
    if administrative_levels:
        prefetch_related_objects(administrative_levels, *ADMINISTRATIVE_LEVEL_LOOKUPS)


def prefetch_cvds_for_api(cvds):
    """CVD d'une page : leurs villages (même requête par CVD qu'avant, donc même ordre) puis tout ce qui est lu
    pour ces villages."""
    villages = []
    for cvd in cvds:
        queryset = cvd.administrativelevel_set.all()
        villages += list(queryset)
        cvd._prefetched_objects_cache = {**getattr(cvd, '_prefetched_objects_cache', {}), 'administrativelevel_set': queryset}
    prefetch_related_objects(list(cvds), 'geographical_unit')
    prefetch_administrative_levels_for_api(villages)


class ZoneSubprojectCounts:
    """Nombres de sous-projets, d'infrastructures et de fichiers (dont non validés) d'un niveau administratif ou d'un
    CVD, parmi les sous-projets de la zone d'un utilisateur (ceux du projet, ou ceux du facilitateur) : mêmes nombres
    que les count() faits auparavant pour chaque élément (la zone était aussi recalculée pour chaque élément), en
    deux requêtes pour toute la réponse."""

    def __init__(self, user, project_id):
        if not hasattr(user, 'no_sql_user'):
            subprojects = Subproject.objects.filter(projects__in=[project_id]).get_actifs()
        else:
            subprojects = get_subprojects_by_facilitator_id_and_project_id(user.id, project_id)
        # une ligne par sous-projet de la zone (comme les lignes comptées par count())
        self.rows = list(subprojects.values_list(
            'id', 'link_to_subproject_id', 'location_subproject_realized_id',
            'location_subproject_realized__parent_id', 'canton_id', 'cvd_id',
        ))
        self.files = {
            subproject_id: (total, invalidated)
            for subproject_id, total, invalidated in SubprojectFile.objects.filter(subproject__in=subprojects).order_by()
            .values_list('subproject_id').annotate(total=Count('id'), invalidated=Count('id', filter=Q(validated=False)))
        }
        self.rows_by_administrative_level = defaultdict(set)
        self.rows_by_cvd = defaultdict(set)
        for index, (_id, _link, location_id, location_parent_id, canton_id, cvd_id) in enumerate(self.rows):
            # site du sous-projet, parent du site, ou canton
            for administrative_level_id in (location_id, location_parent_id, canton_id):
                if administrative_level_id is not None:
                    self.rows_by_administrative_level[administrative_level_id].add(index)
            if cvd_id is not None:
                self.rows_by_cvd[cvd_id].add(index)

    def _numbers(self, indexes, with_files=True):
        rows = [self.rows[index] for index in sorted(indexes)]
        numbers = {
            'number_subprojects': sum(1 for row in rows if row[1] is None),
            'number_infrastructures': len(rows),
        }
        if with_files:
            subproject_ids = {row[0] for row in rows}
            numbers['number_subproject_files'] = sum(self.files.get(i, (0, 0))[0] for i in subproject_ids)
            numbers['files_invalidated_count'] = sum(self.files.get(i, (0, 0))[1] for i in subproject_ids)
        return numbers

    def for_administrative_level(self, administrative_level_id, with_files=True):
        return self._numbers(self.rows_by_administrative_level.get(administrative_level_id, ()), with_files)

    def for_cvd(self, cvd_id):
        return self._numbers(self.rows_by_cvd.get(cvd_id, ()))


def _step_order_key(step):
    return (step.begin, step.created_date, step.ranking)


def _file_order_key(file):
    return (file.validated_order, file.updated_date)


def _attach_current_steps(subprojects):
    """Étape en cours (Subproject.get_current_subproject_step) et ses niveaux, lus par
    get_current_subproject_step_and_level : 2 requêtes pour la page au lieu de 2 par sous-projet."""
    steps = defaultdict(list)
    for step in SubprojectStep.objects.filter(subproject_id__in=[s.pk for s in subprojects]).order_by(
            'subproject_id', '-begin', '-created_date', '-ranking'):
        steps[step.subproject_id].append(step)
    current_steps = {}
    for subproject in subprojects:
        candidates = steps.get(subproject.pk, [])
        if len(candidates) > 1 and _step_order_key(candidates[0]) == _step_order_key(candidates[1]):
            # ex aequo sur l'ordre : la requête d'origine désigne l'étape, comme avant
            current_steps[subproject.pk] = subproject.get_current_subproject_step
        else:
            current_steps[subproject.pk] = candidates[0] if candidates else None
    levels = defaultdict(list)
    for level in Level.objects.filter(subproject_step_id__in=[s.pk for s in current_steps.values() if s]).order_by(
            'subproject_step_id', '-begin', '-ranking', '-created_date', '-id'):
        levels[level.subproject_step_id].append(level)
    for subproject in subprojects:
        step = current_steps[subproject.pk]
        subproject._prefetched_current_step = subproject._current_step_data(step, levels.get(step.pk, []) if step else [])


def attach_current_steps(subprojects):
    """Étape en cours de chaque sous-projet (lue aussi par is_delayed_update), en 2 requêtes pour la liste."""
    subprojects = [subproject for subproject in subprojects if subproject.pk]
    if subprojects:
        _attach_current_steps(subprojects)


def subprojects_without_current_level_image(subprojects):
    """Sous-projets (dans l'ordre reçu) dont get_current_level_object n'a pas d'image (get_images()), comme
    `not (sp.get_current_level_object and sp.get_current_level_object.get_images().exists())`, en 3 requêtes."""
    subprojects = list(subprojects)
    steps = defaultdict(list)
    for step in SubprojectStep.objects.filter(subproject_id__in=[s.pk for s in subprojects]).filter(
            Q(wording__in=STRUCTURE_IN_PROGRESS_STATUS) | Q(ranking__in=STRUCTURE_IN_PROGRESS_RANKING_LIST)
    ).order_by('subproject_id', '-begin', '-created_date', '-ranking'):
        steps[step.subproject_id].append(step)
    first_level = {}
    for level in Level.objects.filter(subproject_step_id__in=[s.pk for ss in steps.values() for s in ss]).order_by(
            'subproject_step_id', '-begin', '-ranking', '-created_date', '-id'):
        first_level.setdefault(level.subproject_step_id, level)
    current_levels = {}
    for subproject in subprojects:
        in_progress = steps.get(subproject.pk, [])
        if any(_step_order_key(a) == _step_order_key(b) for a, b in zip(in_progress, in_progress[1:])):
            # ex aequo sur l'ordre des étapes : calcul d'origine
            current_levels[subproject.pk] = subproject.get_current_level_object
        else:
            current_levels[subproject.pk] = next((first_level[s.pk] for s in in_progress if s.pk in first_level), None)
    image_query = Q()
    for extension in IMAGE_EXTENSIONS:
        image_query |= Q(url__icontains=extension)
    levels_with_images = set(SubprojectFile.objects.filter(
        subproject_level_id__in=[level.pk for level in current_levels.values() if level], file_type__icontains="image"
    ).filter(image_query).values_list('subproject_level_id', flat=True))
    return [
        subproject for subproject in subprojects
        if not (current_levels[subproject.pk] and current_levels[subproject.pk].pk in levels_with_images)
    ]


def _attach_files(subprojects, comments_count=True):
    """Fichiers de chaque sous-projet dans l'ordre de l'API, avec l'étape / le niveau de chaque fichier et son nombre
    de commentaires : quelques requêtes pour la page au lieu de plusieurs par sous-projet et par fichier."""
    files_by_subproject = defaultdict(list)
    for file in SubprojectFile.objects.filter(subproject_id__in=[s.pk for s in subprojects]).annotate(
            validated_order=FILE_ORDER).order_by('subproject_id', 'validated_order', '-updated_date'):
        files_by_subproject[file.subproject_id].append(file)
    all_files = []
    for subproject in subprojects:
        files = files_by_subproject.get(subproject.pk, [])
        if any(_file_order_key(a) == _file_order_key(b) for a, b in zip(files, files[1:])):
            # ex aequo sur l'ordre : la requête d'origine décide de l'ordre, comme avant
            files = list(subproject.get_files().annotate(validated_order=FILE_ORDER).order_by("validated_order", "-updated_date"))
        subproject._api_files = files
        all_files += files
    if not all_files:
        return
    prefetch_related_objects(all_files, 'subproject_step', 'subproject_level__subproject_step')
    if comments_count:
        counts = dict(FileComment.objects.filter(file_id__in=[f.pk for f in all_files]).order_by()
                      .values_list('file_id').annotate(n=Count('id')))
        for file in all_files:
            file._comments_count = counts.get(file.pk, 0)


# Listes many-to-many d'un sous-projet, chargées pour toute la page dans un ordre FIXÉ : celui que PostgreSQL renvoyait
# pour la requête faite auparavant pour chaque sous-projet (sans ORDER BY), vérifié sur toutes les listes de la base
# le 22/10/2026. Grande table de liaison, lue par son index unique (sous-projet, objet) : par identifiant de l'objet ;
# petite table des villages traversés, lue en séquence : ordre d'ajout (identifiant de la liaison).
SUBPROJECT_MANY_TO_MANY_ORDER = {
    'list_of_beneficiary_villages': 'related',
    'list_of_villages_crossed_by_the_track_or_electrification': 'link',
    'priorities': 'related',
    'projects': 'related',
    'financiers': 'related',
}


def _attach_many_to_many(instances, name, order):
    """Liste many-to-many `name` de chaque objet en 2 requêtes pour tous, rangée comme un prefetch_related (lue par
    `getattr(objet, name).all()`). Renvoie les objets liés."""
    field = type(instances[0])._meta.get_field(name)
    source, target = field.m2m_field_name(), field.m2m_reverse_field_name()
    links = list(field.remote_field.through.objects.filter(**{f'{source}_id__in': [i.pk for i in instances]})
                 .order_by(f'{source}_id', 'id' if order == 'link' else f'{target}_id')
                 .values_list(f'{source}_id', f'{target}_id'))
    related = field.related_model._default_manager.in_bulk({target_id for _, target_id in links})
    by_instance = defaultdict(list)
    for instance_id, target_id in links:
        if target_id in related:
            by_instance[instance_id].append(related[target_id])
    for instance in instances:
        queryset = getattr(instance, name).get_queryset()
        queryset._result_cache = by_instance.get(instance.pk, [])
        queryset._prefetch_done = True
        instance._prefetched_objects_cache = {**getattr(instance, '_prefetched_objects_cache', {}), name: queryset}
    return list(related.values())


def prefetch_subprojects_for_api(subprojects, with_children=False, comments_count=True):
    """Sous-projets d'une page (SubprojectSerializer et SubprojectSerializerSimple) : objets liés, sites et leurs
    parents, étape en cours, fichiers ; avec with_children, aussi leurs sous-projets liés (même requête par
    sous-projet qu'avant, donc même ordre) et tout ce qui est lu pour eux."""
    subprojects = [subproject for subproject in subprojects if subproject is not None and subproject.pk]
    if not subprojects:
        return
    prefetch_related_objects(subprojects, 'location_subproject_realized', 'canton', 'cvd__geographical_unit', 'component')
    related = {name: _attach_many_to_many(subprojects, name, order) for name, order in SUBPROJECT_MANY_TO_MANY_ORDER.items()}
    prefetch_administrative_levels_for_api(
        [s.location_subproject_realized for s in subprojects] + [s.canton for s in subprojects]
        + related['list_of_villages_crossed_by_the_track_or_electrification'])
    _attach_current_steps(subprojects)
    _attach_files(subprojects, comments_count)
    if with_children:
        children = []
        for subproject in subprojects:
            linked = subproject.linked_subprojects.get_queryset().get_actifs()
            children += list(linked)
            subproject._prefetched_linked_subprojects = linked
        prefetch_subprojects_for_api(children, comments_count=comments_count)
