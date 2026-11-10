"""Figures shown on the profile pages of a locality: region, prefecture, commune, canton,
village, CVD and geographical unit.

Everything is computed from the database when the page opens: hierarchy, sub-levels, CVDs,
geographical units, subprojects (for the projects of the page), allocations and the stabilized
facilitators (read live from CDD). A locality is described by the set of its villages; the
other figures are derived from it, so every page uses the same rules."""
from collections import Counter, defaultdict

from django.db.models import Q, Sum
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from administrativelevels.functions_facilitators import TECHNICAL, active_facilitators, stabilized_facilitators
from administrativelevels.models import CVD, AdministrativeLevel, GeographicalUnit
from cosomis.project_scope import ProjectScope, linked_project_ids

TYPES = ['Region', 'Prefecture', 'Commune', 'Canton', 'Village']
TYPE_LABELS = {
    'Region': _("Region"), 'Prefecture': _("Prefecture"), 'Commune': _("Commune"),
    'Canton': _("Canton"), 'Village': _("Village"),
}
TYPE_PLURALS = {
    'Region': _("Regions"), 'Prefecture': _("Prefectures"), 'Commune': _("Communes"),
    'Canton': _("Cantons"), 'Village': _("Villages"),
}
TYPE_ICONS = {
    'Region': 'fa-globe-africa', 'Prefecture': 'fa-landmark', 'Commune': 'fa-city',
    'Canton': 'fa-map', 'Village': 'fa-home', 'CVD': 'fa-users', 'GeographicalUnit': 'fa-object-group',
}
AREA_STATUS_TONES = {
    AdministrativeLevel.AreaStatus.RISK_INACCESSIBLE: 'danger',
    AdministrativeLevel.AreaStatus.RISK: 'warning',
    AdministrativeLevel.AreaStatus.MODERATE_RISK: 'info',
    AdministrativeLevel.AreaStatus.NON_RISK: 'success',
}
SUBPROJECT = 'Subproject'
SUBPROJECT_LIST_LIMIT = 100
LEVEL_FIELDS = ('id', 'name', 'type', 'parent_id', 'cvd_id', 'geographical_unit_id', 'latitude', 'longitude',
                'area_status', 'frontalier', 'rural')


def scope_project_ids(request):
    """Projects whose data the page shows: the linked projects of the selection (COSO, FA-COSO...),
    narrowed by the page's "Project" filter."""
    scope = ProjectScope(request)
    ids = scope.ids or linked_project_ids(request.session.get('project_id')) or [request.session.get('project_id')]
    return scope, [i for i in ids if i]


def level_url(level):
    if level.type == AdministrativeLevel.VILLAGE:
        return reverse('administrativelevels:village_detail', args=[level.pk])
    return reverse('administrativelevels:detail', args=[level.pk])


def hierarchy(level):
    """Ancestors from the region down to the direct parent: [{'name', 'type', 'type_label', 'url'}]."""
    chain, parent = [], level.parent
    while parent is not None:
        chain.insert(0, {'name': parent.name, 'type': parent.type, 'type_label': TYPE_LABELS.get(parent.type, parent.type),
                         'url': level_url(parent), 'icon': TYPE_ICONS.get(parent.type, 'fa-map-marker-alt')})
        parent = parent.parent
    return chain


def breadcrumb(chain, title):
    return [{'url': item['url'], 'title': f"{item['type_label']} {item['name']}"} for item in chain] + [{'url': '', 'title': title}]


def area_status_badge(value):
    if not value:
        return None
    return {'label': AdministrativeLevel.AreaStatus(value).label, 'tone': AREA_STATUS_TONES.get(value, 'secondary')}


def descendants(level):
    """Every level under `level`, walking down one type at a time (one query per type).

    Returns (rows by id, direct children ids, {descendant id: id of the direct child it is under})."""
    rows, child_of, current = {}, {}, [level.pk]
    children = []
    while current:
        found = list(AdministrativeLevel.objects.filter(parent_id__in=current).values(*LEVEL_FIELDS))
        for row in found:
            rows[row['id']] = row
            if row['parent_id'] == level.pk:
                children.append(row['id'])
                child_of[row['id']] = row['id']
            else:
                child_of[row['id']] = child_of.get(row['parent_id'])
        current = [row['id'] for row in found]
    return rows, children, child_of


def subprojects_queryset(project_ids, village_ids=(), canton_ids=(), cvd_ids=()):
    """Active subprojects and infrastructures of the projects that are located in one of the villages,
    cross one of them (tracks, electrification), belong to one of the cantons or to one of the CVDs."""
    condition = Q(pk__in=[])
    if village_ids:
        condition |= Q(location_subproject_realized_id__in=village_ids)
        condition |= Q(list_of_villages_crossed_by_the_track_or_electrification__in=village_ids)
    if canton_ids:
        condition |= Q(canton_id__in=canton_ids)
    if cvd_ids:
        condition |= Q(cvd_id__in=cvd_ids)
    from subprojects.models import Subproject
    ids = Subproject.objects.filter(condition).get_actifs().values('pk')
    queryset = Subproject.objects.filter(pk__in=ids)
    if project_ids:
        queryset = queryset.filter(pk__in=Subproject.objects.filter(projects__in=project_ids).values('pk'))
    return queryset


def _beneficiaries(row):
    return sum(row.get(f) or 0 for f in ('direct_beneficiaries_men', 'direct_beneficiaries_women',
                                          'indirect_beneficiaries_men', 'indirect_beneficiaries_women'))


def subproject_rows(queryset):
    return list(queryset.values(
        'id', 'full_title_of_approved_subproject', 'subproject_type_designation', 'subproject_sector', 'type_of_subproject',
        'estimated_cost', 'contract_amount_work_companies', 'current_status_of_the_site',
        'current_level_of_physical_realization_of_the_work_percent', 'location_subproject_realized_id',
        'location_subproject_realized__name', 'canton_id', 'cvd_id', 'link_to_subproject_id',
        'direct_beneficiaries_men', 'direct_beneficiaries_women', 'indirect_beneficiaries_men', 'indirect_beneficiaries_women',
    ).order_by('subproject_sector', 'full_title_of_approved_subproject', 'id'))


def subproject_summary(rows):
    """Counts and amounts: kits ("Subproject") and structures ("Infrastructure") are counted apart;
    amounts add up every row, as a kit's cost is its own plus its structures' (Subproject.get_estimated_cost)."""
    from subprojects.models import SubprojectSector
    colors = SubprojectSector.color_map()
    kits = [r for r in rows if r['subproject_type_designation'] == SUBPROJECT]
    estimated = sum(r['estimated_cost'] or 0 for r in rows)
    contract = sum(r['contract_amount_work_companies'] or 0 for r in rows)
    progress = [r['current_level_of_physical_realization_of_the_work_percent'] for r in kits
                if r['current_level_of_physical_realization_of_the_work_percent'] is not None]

    sectors = defaultdict(lambda: {'count': 0, 'cost': 0})
    for r in kits:
        sector = sectors[r['subproject_sector'] or '-']
        sector['count'] += 1
        sector['cost'] += r['estimated_cost'] or 0
    top = max((s['count'] for s in sectors.values()), default=0) or 1
    by_sector = [{'name': name, 'count': s['count'], 'cost': s['cost'], 'color': colors.get(name) or '#6c757d',
                  'percent': round(s['count'] * 100 / len(kits), 1) if kits else 0, 'bar': round(s['count'] * 100 / top)}
                 for name, s in sorted(sectors.items(), key=lambda item: (-item[1]['count'], item[0]))]
    statuses = Counter(r['current_status_of_the_site'] or str(_("Not specified")) for r in kits)
    by_status = [{'name': name, 'count': count, 'percent': round(count * 100 / len(kits)) if kits else 0}
                 for name, count in statuses.most_common()]
    return {
        'kits': len(kits), 'structures': len(rows) - len(kits), 'estimated': estimated, 'contract': contract,
        'beneficiaries': sum(_beneficiaries(r) for r in kits),
        'progress': round(sum(progress) / len(progress)) if progress else None,
        'by_sector': by_sector, 'by_status': by_status,
    }


def allocations(project_ids, level_ids=(), cvd_ids=()):
    """Allocations of the projects: to the levels (cantons) and to the CVDs, kept apart (a canton's
    allocation is shared out between its CVDs, adding both would count it twice)."""
    from financial.models import AdministrativeLevelAllocation
    queryset = AdministrativeLevelAllocation.objects.filter(project_id__in=project_ids)
    levels = queryset.filter(administrative_level_id__in=level_ids).aggregate(s=Sum('amount'))['s'] or 0 if level_ids else 0
    cvds = queryset.filter(cvd_id__in=cvd_ids, administrative_level=None).aggregate(s=Sum('amount'))['s'] or 0 if cvd_ids else 0
    return {'levels': levels, 'cvds': cvds}


def facilitators_block(village_names, facilitators=None):
    found = stabilized_facilitators(village_names, facilitators)
    return {
        'groups': [(_("AC/FC (community facilitator)"), found['community']), (_("FT (technical facilitator)"), found['technical'])],
        'community': len(found['community']), 'technical': len(found['technical']),
        'covered': len(set().union(*[f.stabilized_village_ids for f in found['community'] + found['technical']]))
        if found['community'] or found['technical'] else 0,
    }


def _kpi(icon, label, value, hint=None, tone='blue', money=False):
    return {'icon': icon, 'label': label, 'value': value, 'hint': hint, 'tone': tone, 'money': money}


def _common_kpis(summary, alloc, facilitators, villages_count=None, cvds_count=None):
    kpis = []
    if villages_count is not None:
        kpis.append(_kpi('fa-home', _("Villages"), villages_count))
    if cvds_count is not None:
        kpis.append(_kpi('fa-users', _("CVD"), cvds_count))
    kpis += [
        _kpi('fa-project-diagram', _("Subprojects"), summary['kits'],
             hint=_("%(count)s structure(s)") % {'count': summary['structures']}, tone='indigo'),
        _kpi('fa-coins', _("Estimated cost"), summary['estimated'], tone='teal', money=True),
        _kpi('fa-file-signature', _("Contract amount"), summary['contract'], tone='orange', money=True),
        _kpi('fa-hard-hat', _("Average physical progress"),
             f"{summary['progress']} %" if summary['progress'] is not None else '-', tone='green'),
        _kpi('fa-hands-helping', _("Stabilized facilitators"), facilitators['community'] + facilitators['technical'],
             hint=_("%(ac)s AC/FC · %(ft)s FT") % {'ac': facilitators['community'], 'ft': facilitators['technical']},
             tone='purple'),
    ]
    if alloc['levels']:
        kpis.append(_kpi('fa-wallet', _("Canton allocations"), alloc['levels'], tone='blue', money=True))
    if alloc['cvds']:
        kpis.append(_kpi('fa-piggy-bank', _("CVD allocations"), alloc['cvds'], tone='blue', money=True))
    return kpis


def _subprojects_block(rows):
    kits = [r for r in rows if r['subproject_type_designation'] == SUBPROJECT]
    return {'rows': kits[:SUBPROJECT_LIST_LIMIT], 'total': len(kits), 'limited': len(kits) > SUBPROJECT_LIST_LIMIT}


def administrative_level_profile(level, project_ids):
    """Profile of a region, prefecture, commune, canton or village."""
    is_village = level.type == AdministrativeLevel.VILLAGE
    rows, children_ids, child_of = ({}, [], {}) if is_village else descendants(level)
    villages = {level.pk: level.name} if is_village else {i: r['name'] for i, r in rows.items() if r['type'] == AdministrativeLevel.VILLAGE}
    cantons = [level.pk] if level.type == AdministrativeLevel.CANTON else [i for i, r in rows.items() if r['type'] == AdministrativeLevel.CANTON]
    if is_village:
        cvd_ids = [level.cvd_id] if level.cvd_id else []
    else:
        cvd_ids = sorted({r['cvd_id'] for i, r in rows.items() if i in villages and r['cvd_id']})

    queryset = subprojects_queryset(project_ids, list(villages), cantons, cvd_ids)
    rows_sp = subproject_rows(queryset)
    summary = subproject_summary(rows_sp)
    facilitators = active_facilitators()
    fac = facilitators_block(villages, facilitators)
    alloc = allocations(project_ids, [level.pk] + list(rows), cvd_ids)

    profile = {
        'kind': level.type, 'icon': TYPE_ICONS.get(level.type, 'fa-map-marker-alt'),
        'type_label': TYPE_LABELS.get(level.type, level.type), 'name': level.name, 'object': level,
        'chain': hierarchy(level), 'area_status': area_status_badge(level.area_status),
        'summary': summary, 'facilitators': fac, 'allocations': alloc,
        'subprojects': _subprojects_block(rows_sp), 'villages_count': len(villages), 'cvds_count': len(cvd_ids),
        'updated': level.updated_date,
    }

    if is_village:
        profile['kpis'] = _common_kpis(summary, alloc, fac)
        profile['cvd'] = level.cvd
        profile['cvd_villages'] = list(level.cvd.get_villages().order_by('name')) if level.cvd_id else []
        profile['geographical_unit'] = level.geographical_unit
        profile['priorities_count'] = level.get_list_priorities().count()
        return profile

    # Sub-levels and per-type counts
    counts = Counter(r['type'] for r in rows.values())
    profile['level_counts'] = [{'type': t, 'label': TYPE_PLURALS[t], 'icon': TYPE_ICONS[t], 'count': counts[t]}
                               for t in TYPES[TYPES.index(level.type) + 1:] if t in counts] if level.type in TYPES else []
    village_rows = [rows[i] for i in villages]
    profile['gps'] = sum(1 for r in village_rows if r['latitude'] is not None and r['longitude'] is not None)
    profile['frontalier'] = sum(1 for r in village_rows if r['frontalier'])
    profile['rural'] = sum(1 for r in village_rows if r['rural'])
    profile['area_statuses'] = [
        {'label': choice.label, 'tone': AREA_STATUS_TONES[choice], 'count': count,
         'percent': round(count * 100 / len(village_rows)) if village_rows else 0}
        for choice in AdministrativeLevel.AreaStatus
        for count in [sum(1 for r in village_rows if r['area_status'] == choice)] if count]
    profile['geographical_units'] = GeographicalUnit.objects.filter(canton_id__in=cantons).count()
    profile['kpis'] = _common_kpis(summary, alloc, fac, villages_count=len(villages), cvds_count=len(cvd_ids))

    # One line per direct sub-level
    per_child = defaultdict(lambda: {'villages': 0, 'cvds': set(), 'kits': 0, 'structures': 0, 'estimated': 0,
                                     'contract': 0, 'ac': set(), 'ft': set()})
    for village_id in villages:
        child = per_child[child_of.get(village_id)]
        child['villages'] += 1
        if rows[village_id]['cvd_id']:
            child['cvds'].add(rows[village_id]['cvd_id'])
    village_cvd = {i: rows[i]['cvd_id'] for i in villages}
    cvd_child = {}
    for village_id, cvd_id in village_cvd.items():
        if cvd_id:
            cvd_child.setdefault(cvd_id, child_of.get(village_id))
    for r in rows_sp:
        where = r['location_subproject_realized_id'] if r['location_subproject_realized_id'] in child_of else None
        child_id = child_of.get(where) or child_of.get(r['canton_id']) or cvd_child.get(r['cvd_id'])
        if level.type == AdministrativeLevel.CANTON and child_id is None:
            continue
        child = per_child[child_id]
        child['kits' if r['subproject_type_designation'] == SUBPROJECT else 'structures'] += 1
        child['estimated'] += r['estimated_cost'] or 0
        child['contract'] += r['contract_amount_work_companies'] or 0
    for _label, people in fac['groups']:
        for f in people:
            for village_id in f.stabilized_village_ids:
                per_child[child_of.get(village_id)]['ft' if f.facilitator_type == TECHNICAL else 'ac'].add(f.pk)

    children = []
    for child_id in sorted(children_ids, key=lambda i: rows[i]['name']):
        row, stats = rows[child_id], per_child[child_id]
        children.append({
            'id': child_id, 'name': row['name'], 'type': row['type'],
            'url': reverse('administrativelevels:village_detail' if row['type'] == AdministrativeLevel.VILLAGE
                           else 'administrativelevels:detail', args=[child_id]),
            'area_status': area_status_badge(row['area_status']),
            'villages': stats['villages'], 'cvds': len(stats['cvds']), 'kits': stats['kits'], 'structures': stats['structures'],
            'estimated': stats['estimated'], 'contract': stats['contract'], 'ac': len(stats['ac']), 'ft': len(stats['ft']),
            'gps': row['latitude'] is not None and row['longitude'] is not None,
            'cvd_id': row['cvd_id'],
        })
    profile['children'] = children
    profile['children_type'] = children[0]['type'] if children else None
    profile['children_label'] = TYPE_PLURALS.get(profile['children_type'], _("Sub-levels"))

    if level.type == AdministrativeLevel.CANTON:
        cvds = CVD.objects.filter(pk__in=cvd_ids).select_related('headquarters_village').order_by('attributed_number_in_canton', 'name')
        village_count = Counter(c for c in village_cvd.values() if c)
        profile['cvds'] = [{'object': c, 'villages': village_count[c.pk]} for c in cvds]
        profile['units'] = list(GeographicalUnit.objects.filter(canton_id=level.pk).order_by('attributed_number_in_canton'))
        cvd_names = {c.pk: c.get_name() for c in cvds}
        for child in children:
            child['cvd_name'] = cvd_names.get(child['cvd_id'])
    return profile


def _group_profile(kind, name, villages_qs, cvd_ids, project_ids, extra_level_ids=()):
    villages = {v.pk: v.name for v in villages_qs}
    queryset = subprojects_queryset(project_ids, list(villages), (), cvd_ids)
    rows_sp = subproject_rows(queryset)
    summary = subproject_summary(rows_sp)
    fac = facilitators_block(villages)
    alloc = allocations(project_ids, list(extra_level_ids), cvd_ids)
    return {
        'kind': kind, 'icon': TYPE_ICONS[kind], 'name': name, 'summary': summary, 'facilitators': fac,
        'allocations': alloc, 'subprojects': _subprojects_block(rows_sp),
        'kpis': _common_kpis(summary, alloc, fac, villages_count=len(villages),
                             cvds_count=len(cvd_ids) if kind == 'GeographicalUnit' else None),
    }


def cvd_profile(cvd, project_ids):
    villages = cvd.get_villages().select_related('parent').order_by('name')
    profile = _group_profile('CVD', cvd.get_name(), villages, [cvd.pk], project_ids)
    canton = cvd.get_canton()
    profile.update({
        'type_label': _("CVD"), 'object': cvd, 'canton': canton,
        'chain': (hierarchy(canton) + [{'name': canton.name, 'type': canton.type, 'type_label': TYPE_LABELS['Canton'],
                                        'url': level_url(canton), 'icon': TYPE_ICONS['Canton']}]) if canton else [],
        'villages': list(villages),
        'members': [
            {'role': _("President"), 'icon': 'fa-user-tie', 'name': cvd.president_name_of_the_cvd, 'phone': cvd.president_phone_of_the_cvd},
            {'role': _("Treasurer"), 'icon': 'fa-cash-register', 'name': cvd.treasurer_name_of_the_cvd, 'phone': cvd.treasurer_phone_of_the_cvd},
            {'role': _("Secretary"), 'icon': 'fa-feather-alt', 'name': cvd.secretary_name_of_the_cvd, 'phone': cvd.secretary_phone_of_the_cvd},
        ],
        'updated': cvd.updated_date if hasattr(cvd, 'updated_date') else None,
    })
    return profile


def geographical_unit_profile(unit, project_ids):
    villages = unit.get_villages().select_related('cvd').order_by('name')
    cvds = list(unit.get_cvds().select_related('headquarters_village').order_by('attributed_number_in_canton', 'name'))
    profile = _group_profile('GeographicalUnit', unit.get_name(), villages, [c.pk for c in cvds], project_ids)
    canton = unit.canton
    village_count = Counter(v.cvd_id for v in villages if v.cvd_id)
    profile.update({
        'type_label': _("Geographical unit"), 'object': unit, 'canton': canton,
        'chain': (hierarchy(canton) + [{'name': canton.name, 'type': canton.type, 'type_label': TYPE_LABELS['Canton'],
                                        'url': level_url(canton), 'icon': TYPE_ICONS['Canton']}]) if canton else [],
        'villages': list(villages),
        'cvds': [{'object': c, 'villages': village_count[c.pk]} for c in cvds],
    })
    return profile
