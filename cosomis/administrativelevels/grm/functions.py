from administrativelevels.models import AdministrativeLevel

def get_choices(query_result, empty_choice=True):
    choices = [(i['id'], i['name']) for i in query_result]
    if empty_choice:
        choices = [('', '')] + choices
    return choices

def get_administrative_region_choices(adl_db, empty_choice=True):
    country_id = adl_db.get_query_result(
        {
            "type": 'administrative_level',
            "parent_id": None,
        }
    )[:][0]['administrative_id']
    query_result = adl_db.get_query_result(
        {
            "type": 'administrative_level',
            "parent_id": country_id,
        }
    )
    choices = list()
    for i in query_result:
        choices.append((i['administrative_id'], f"{i['name']}"))
    if empty_choice:
        choices = [('', '')] + choices
    return choices

def get_administrative_regions_by_level(adl_db, level=None):
    filters = {"type": 'administrative_level'}
    if level:
        filters['administrative_level'] = level
    else:
        filters['parent_id'] = None
    parent_id = adl_db.get_query_result(filters)[:][0]['administrative_id']
    data = adl_db.get_query_result(
        {
            "type": 'administrative_level',
            "parent_id": parent_id,
        }
    )
    data = [doc for doc in data]
    return data


def get_issue_category_choices(grm_db, empty_choice=True):
    query_result = grm_db.get_query_result({"type": 'issue_category'})
    return get_choices(query_result, empty_choice)


def get_issue_status_choices(grm_db, empty_choice=True):
    query_result = grm_db.get_query_result({"type": 'issue_status'})
    return get_choices(query_result, empty_choice)


def get_administrative_level_descendants_using_mis(adl_db, parent_id, ids, user=None):
    data = []
    if parent_id:
        if int(parent_id) == 1:
            data = AdministrativeLevel.objects.filter(type="Region")
        else:
            data = AdministrativeLevel.objects.filter(parent_id=int(parent_id))
        
    descendants_ids = [obj.id for obj in data]
    for descendant_id in descendants_ids:
        get_administrative_level_descendants_using_mis(adl_db, descendant_id, ids, user)
        ids.append(str(descendant_id))

    return ids