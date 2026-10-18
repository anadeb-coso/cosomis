from datetime import datetime

from django.db.models import Q
from django.utils.functional import Promise

from cosomis.constants import (
    STRUCTURE_COMPLETED_STATUS, STRUCTURE_IN_PROGRESS_STATUS, STRUCTURE_NOT_START_STATUS,
    IN_PROGRESS_RANKING, COMPLETED_RANKING,
)


def _parse_fr_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


def filter_dashboard_subprojects(subprojects, request):
    """`subprojects` filtered by the subproject filters of the dashboards in the
    query string: status (id_subproject_step[]), dates (start_date, end_date,
    dd/mm/yyyy), component, sector, type of structure and works type. The
    "show for all projects" choice (all_projects[]) is applied by
    Subproject.objects.get_objects_by_general_filtre()."""
    from subprojects.models import Component

    def get_list(name):
        return [elt for elt in request.GET.getlist(name) if elt]

    subproject_sectors = get_list('id_subproject_sectors[]')
    subproject_types = get_list('id_subproject_types[]')
    works_type_of_subprojects = get_list('id_works_type_of_subproject[]')
    subproject_steps = get_list('id_subproject_step[]')
    components_names = get_list('id_components[]')
    start_date = _parse_fr_date(request.GET.get('start_date', None))
    end_date = _parse_fr_date(request.GET.get('end_date', None))

    if start_date or end_date:
        if not subproject_steps:
            subprojects = subprojects.filter(current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS)

            if start_date and end_date:
                subprojects = subprojects.filter(
                    work_completion_date__range=[start_date, end_date]
                )
            elif start_date:
                subprojects = subprojects.filter(
                    work_completion_date__gte=start_date
                )
            else:
                subprojects = subprojects.filter(
                    work_completion_date__lte=end_date
                )

        else:
            q = Q()
            if 'not_started' in subproject_steps:
                q |= Q(subprojectstep__ranking__gte=0, subprojectstep__ranking__lt=IN_PROGRESS_RANKING)
            if 'in_progress' in subproject_steps:
                if start_date and end_date:
                    q |= Q(subprojectstep__ranking__gte=IN_PROGRESS_RANKING, subprojectstep__ranking__lt=IN_PROGRESS_RANKING, subprojectstep__level__begin__range=[start_date, end_date])
                elif start_date:
                    q |= Q(subprojectstep__ranking__gte=IN_PROGRESS_RANKING, subprojectstep__ranking__lt=IN_PROGRESS_RANKING, subprojectstep__level__begin__gte=start_date)
                else:
                    q |= Q(subprojectstep__ranking__gte=IN_PROGRESS_RANKING, subprojectstep__ranking__lt=IN_PROGRESS_RANKING, subprojectstep__level__begin__lte=end_date)
            if 'completed' in subproject_steps:
                q |= Q(subprojectstep__ranking__gte=COMPLETED_RANKING)

            if start_date and end_date:
                subprojects = subprojects.filter(Q(
                    Q(Q(subprojectstep__begin__range=[start_date, end_date]) & q)
                )).distinct()
            elif start_date:
                subprojects = subprojects.filter(Q(
                    Q(Q(subprojectstep__begin__gte=start_date) & q)
                )).distinct()
            else:
                subprojects = subprojects.filter(Q(
                    Q(Q(subprojectstep__begin__lte=end_date) & q)
                )).distinct()

    elif subproject_steps:
        q = Q()
        if 'not_started' in subproject_steps:
            q |= Q(current_status_of_the_site__in=STRUCTURE_NOT_START_STATUS)
        if 'in_progress' in subproject_steps:
            q |= Q(current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS)
        if 'completed' in subproject_steps:
            q |= Q(current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS)
        subprojects = subprojects.filter(q)

    if components_names:
        subprojects = subprojects.filter(
            component_id__in=Component.expand_names(components_names))

    if subproject_sectors:
        subprojects = subprojects.filter(subproject_sector__in=subproject_sectors)

    if subproject_types:
        subprojects = subprojects.filter(type_of_subproject__in=subproject_types)

    if works_type_of_subprojects:
        subprojects = subprojects.filter(works_type__in=works_type_of_subprojects)

    return subprojects


def sum_dict_value(d: dict, limit, pair=None,_type_data=int):
    _sum = 0
    for k, v in d.items():
        if str(k).isdigit() and v and str(v).replace('.','',1).replace(',','',1).isdigit() and k < limit:
            if str(k).isdigit() and pair == True and (k+1)%2 == 0:
                _sum += _type_data(float(v))
            elif str(k).isdigit() and pair == False and (k+1)%2 != 0:
                _sum += _type_data(float(v))
            elif pair == None:
                _sum += _type_data(float(v))
        elif not str(k).isdigit() and v and str(v).replace('.','',1).replace(',','',1).isdigit():
            _sum += _type_data(float(v))
    return _sum


def _plain_text(value):
    if isinstance(value, Promise):
        return str(value)
    if isinstance(value, tuple):
        return tuple(_plain_text(v) for v in value)
    return value


def plain_summary_tables(*tables):
    """Turn the translated (lazy) texts of summary tables ({'datas': {column:
    {row: value}}, 'values': [...], 'headers': ...}, rendered by
    components/summary_table.html) into plain strings, in place. The template
    compares every column name several times per cell and a lazy string is
    translated again at each comparison: thousands of translations per table.
    The rendered text is the same."""
    for table in tables:
        if not isinstance(table, dict):
            continue
        datas = table.get('datas')
        if isinstance(datas, dict):
            for column_values in datas.values():
                if isinstance(column_values, dict):
                    for row, value in column_values.items():
                        column_values[row] = _plain_text(value)
            table['datas'] = {_plain_text(column): column_values for column, column_values in datas.items()}
        headers = table.get('headers')
        if isinstance(headers, dict):
            table['headers'] = {key: [_plain_text(column) for column in columns] for key, columns in headers.items()}
        if 'title' in table:
            table['title'] = _plain_text(table['title'])
