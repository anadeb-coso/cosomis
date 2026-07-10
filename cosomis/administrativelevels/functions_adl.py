from administrativelevels.models import AdministrativeLevel
from django.db import connection


def get_administrative_level_under_json(administrative_level):
    if administrative_level:
        return {
            "administrative_id": str(administrative_level.id),
            "name": str(administrative_level.name)
        }
        
    return None

def get_administrative_levels_under_json(administrative_levels):
    datas = []
    for adm_obj in administrative_levels:
        datas.append(get_administrative_level_under_json(adm_obj))
        
    return datas

def get_cascade_administrative_levels_by_administrative_level_id(_id):
    datas = {}
    
    if _id:
        ad_obj = AdministrativeLevel.objects.get(id=int(_id))

        ads = ad_obj.administrativelevel_set.get_queryset()
        _type = ad_obj.type

        if _type == "Region":
            # regions = administrativelevels_models.AdministrativeLevel.objects.filter(type="Region")
            prefectures = ads
            communes = AdministrativeLevel.objects.filter(parent_id__in=[o.id for o in prefectures])
            cantons = AdministrativeLevel.objects.filter(parent_id__in=[o.id for o in communes])
            villages = AdministrativeLevel.objects.filter(parent_id__in=[o.id for o in cantons])
        elif _type == "Prefecture":
            # regions = administrativelevels_models.AdministrativeLevel.objects.filter(type="Region")
            prefectures = AdministrativeLevel.objects.filter(type="Prefecture")
            communes = ads
            cantons = AdministrativeLevel.objects.filter(parent_id__in=[o.id for o in communes])
            villages = AdministrativeLevel.objects.filter(parent_id__in=[o.id for o in cantons])
        elif _type == "Commune":
            # regions = administrativelevels_models.AdministrativeLevel.objects.filter(type="Region")
            prefectures = AdministrativeLevel.objects.filter(type="Prefecture")
            communes = AdministrativeLevel.objects.filter(type="Commune")
            cantons = ads
            villages = AdministrativeLevel.objects.filter(parent_id__in=[o.id for o in cantons])
        elif _type == "Canton":
            # regions = administrativelevels_models.AdministrativeLevel.objects.filter(type="Region")
            prefectures = AdministrativeLevel.objects.filter(type="Prefecture")
            communes = AdministrativeLevel.objects.filter(type="Commune")
            cantons = AdministrativeLevel.objects.filter(type="Canton")
            villages = ads
        elif _type == "Village":
            # regions = administrativelevels_models.AdministrativeLevel.objects.filter(type="Region")
            prefectures = AdministrativeLevel.objects.filter(type="Prefecture")
            communes = AdministrativeLevel.objects.filter(type="Commune")
            cantons = AdministrativeLevel.objects.filter(type="Canton")
            villages = ad_obj.parent.administrativelevel_set.get_queryset()
        else:
            prefectures = AdministrativeLevel.objects.filter(type="Prefecture")
            communes = AdministrativeLevel.objects.filter(type="Commune")
            cantons = AdministrativeLevel.objects.filter(type="Canton")
            villages = AdministrativeLevel.objects.filter(type="Village")
    else:
        prefectures = AdministrativeLevel.objects.filter(type="Prefecture")
        communes = AdministrativeLevel.objects.filter(type="Commune")
        cantons = AdministrativeLevel.objects.filter(type="Canton")
        villages = AdministrativeLevel.objects.filter(type="Village")

        
    datas["prefectures"] = get_administrative_levels_under_json(prefectures)
    datas["communes"] = get_administrative_levels_under_json(communes)
    datas["cantons"] = get_administrative_levels_under_json(cantons)
    datas["villages"] = get_administrative_levels_under_json(villages)


    return datas


def get_cascade_villages_by_administrative_level_id(_ids):
    
    if type(_ids) is not list:
        _ids = [_ids]
    if _ids:
        
        ad_objects = AdministrativeLevel.objects.filter(id__in=[int(_id) for _id in _ids if _id])
        
        villages = []
        for ad_obj in ad_objects:
            if ad_obj:
                ads = []
                _type = ad_obj.type
                if _type == "Village":
                    ads.append(ad_obj)
                else:
                    ads = ad_obj.administrativelevel_set.get_queryset()
                    
                datas = {
                    "prefectures": ads if _type == "Region" else [], 
                    "communes": ads if _type == "Prefecture" else [], 
                    "cantons": ads if _type == "Commune" else [], 
                    "villages": ads if _type in ("Canton", "Village") else []
                }
                for p in datas["prefectures"]:
                    [datas["communes"].append(o) for o in p.administrativelevel_set.get_queryset()]

                for c in datas["communes"]:
                    [datas["cantons"].append(o) for o in c.administrativelevel_set.get_queryset()]
                
                for c in datas["cantons"]:
                    [datas["villages"].append(o) for o in c.administrativelevel_set.get_queryset()]
                
                if _type == "village":
                    datas["villages"].append(ad_obj)
                villages += datas["villages"]

        return get_administrative_levels_under_json(list(set(villages)))
    return []

def get_cascade_villages_ids_by_administrative_level_id(_ids):
    
    if type(_ids) is not list:
        _ids = [_ids]
    if _ids:
        
        ad_objects = AdministrativeLevel.objects.filter(id__in=[int(_id) for _id in _ids if _id])
        
        villages = []
        for ad_obj in ad_objects:
            if ad_obj:
                ads = []
                _type = ad_obj.type
                if _type == "Village":
                    ads.append(ad_obj)
                else:
                    ads = ad_obj.administrativelevel_set.get_queryset()
                    
                datas = {
                    "prefectures": ads if _type == "Region" else [], 
                    "communes": ads if _type == "Prefecture" else [], 
                    "cantons": ads if _type == "Commune" else [], 
                    "villages": [o.id for o in ads] if _type in ("Canton", "Village") else []
                }
                for p in datas["prefectures"]:
                    [datas["communes"].append(o) for o in p.administrativelevel_set.get_queryset()]

                for c in datas["communes"]:
                    [datas["cantons"].append(o) for o in c.administrativelevel_set.get_queryset()]
                
                for c in datas["cantons"]:
                    [datas["villages"].append(int(o.id)) for o in c.administrativelevel_set.get_queryset()]
                
                if _type == "village":
                    datas["villages"].append(int(ad_obj.id))
                villages += datas["villages"]

        return list(set(villages))
    return []


def get_cascade_adls_by_administrative_level_id(_ids, __type="Village", parent_id=None):
    
    if type(_ids) is not list:
        _ids = [_ids]
    if _ids:
        
        ad_objects = AdministrativeLevel.objects.filter(id__in=[int(_id) for _id in _ids if _id]).distinct()
        
        villages = []
        for ad_obj in ad_objects:
            if ad_obj:
                ads = []
                _type = ad_obj.type
                if _type == "Village":
                    ads.append(ad_obj)
                else:
                    ads = ad_obj.administrativelevel_set.get_queryset()
                    
                datas = {
                    "prefectures": ads if _type == "Region" else [], 
                    "communes": ads if _type == "Prefecture" else [], 
                    "cantons": ads if _type == "Commune" else [], 
                    "villages": ads if _type in ("Canton", "Village") else []
                }
                for p in datas["prefectures"]:
                    [datas["communes"].append(o) for o in p.administrativelevel_set.get_queryset()]

                for c in datas["communes"]:
                    [datas["cantons"].append(o) for o in c.administrativelevel_set.get_queryset()]
                
                for c in datas["cantons"]:
                    [datas["villages"].append(o) for o in c.administrativelevel_set.get_queryset()]
                
                if _type == "village":
                    datas["villages"].append(ad_obj)
                villages += datas["villages"]

        villages = list(set(villages))
        if __type == "Region":
            return [
                v.parent.parent.parent.parent for v in villages
            ]
        elif __type == "Prefecture":
            return [
                v.parent.parent.parent for v in villages if (not parent_id or (parent_id and v.parent.parent.parent.parent and v.parent.parent.parent.parent_id==parent_id))
            ]
        elif __type == "Commune":
            return [
                v.parent.parent for v in villages if (not parent_id or (parent_id and v.parent.parent.parent and v.parent.parent.parent_id==parent_id))
            ]
        elif __type == "Canton":
            return [
                v.parent for v in villages if (not parent_id or (parent_id and v.parent.parent and v.parent.parent_id==parent_id))
            ]

        return [v for v in villages if (not parent_id or (parent_id and v.parent and v.parent_id==parent_id))]
    return []


def get_multiple_administrative_hierarchies_ids(level_ids, search_descendants_for=["Canton", ]):
    """Récupère tous les ascendants et descendants des niveaux donnés."""
    
    # Convertir les IDs en chaîne pour l'utiliser dans la requête SQL
    level_ids_str = ",".join(map(str, level_ids))

    # Requête SQL récursive pour récupérer tous les descendants
    sql_descendants = f"""
        WITH RECURSIVE descendants AS (
            SELECT * FROM administrativelevels_administrativelevel WHERE id IN ({level_ids_str})
            UNION ALL
            SELECT al.* FROM administrativelevels_administrativelevel al
            INNER JOIN descendants d ON al.parent_id = d.id AND d.type IN {tuple(search_descendants_for+search_descendants_for)}
        )
        SELECT id FROM descendants;
    """

    # Requête SQL récursive pour récupérer tous les ascendants
    sql_ancestors = f"""
        WITH RECURSIVE ancestors AS (
            SELECT * FROM administrativelevels_administrativelevel WHERE id IN ({level_ids_str})
            UNION ALL
            SELECT al.* FROM administrativelevels_administrativelevel al
            INNER JOIN ancestors a ON a.parent_id = al.id
        )
        SELECT id FROM ancestors;
    """

    with connection.cursor() as cursor:
        # Récupérer les IDs des descendants
        cursor.execute(sql_descendants)
        descendant_ids = [row[0] for row in cursor.fetchall()]

        # Récupérer les IDs des ascendants
        cursor.execute(sql_ancestors)
        ancestor_ids = [row[0] for row in cursor.fetchall()]

    return descendant_ids, ancestor_ids, level_ids


def get_multiple_administrative_hierarchies(level_ids):
    descendant_ids, ancestor_ids, level_ids = get_multiple_administrative_hierarchies_ids(level_ids)
    return AdministrativeLevel.objects.filter(id__in=(descendant_ids + ancestor_ids + level_ids))