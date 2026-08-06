from administrativelevels.models import AdministrativeLevel
import grm_client

# NB : `get_administrative_region_choices` et `get_administrative_regions_by_level`
# (anciens helpers CouchDB `administrative_levels`, zéro appelant) ont été supprimés lors de
# la migration vers l'API inter-services GRM.


def get_choices(query_result, empty_choice=True, id_field='id'):
    choices = [(i[id_field], i['name']) for i in query_result]
    if empty_choice:
        choices = [('', '')] + choices
    return choices


def get_issue_category_choices(empty_choice=True):
    """Remplace la requête Mango CouchDB `grm` `{"type": "issue_category"}` : passe désormais
    par l'API inter-services GRM (`grm_client.get_issue_categories`). Les dicts renvoyés
    portent `legacy_id` (ancien id CouchDB numérique conservé côté Postgres GRM comme clé de
    référence) plutôt que `id`, d'où le `id_field='legacy_id'`."""
    return get_choices(grm_client.get_issue_categories(), empty_choice, id_field='legacy_id')


def get_issue_status_choices(empty_choice=True):
    """Remplace la requête Mango CouchDB `grm` `{"type": "issue_status"}`, voir
    `get_issue_category_choices` ci-dessus."""
    return get_choices(grm_client.get_issue_statuses(), empty_choice, id_field='legacy_id')


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