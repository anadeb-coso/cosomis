"""Liens d'un projet avec les facilitateurs et les utilisateurs.

Le projet est la table commune `process_manager_project` (base unifiée DCC + COSOMIS). Ses liens avec les
facilitateurs et les utilisateurs sont rangés dans les tables du DCC (`process_manager.Project.facilitators` /
`.users`), que COSOMIS lit déjà (cosomis/services.py::get_user_projects : projets proposés à un utilisateur).
COSOMIS ne migre pas ces tables : elles sont lues et écrites ici en SQL, sans champ sur le modèle.
"""
from django.db import connection, transaction

LINK_TABLES = {
    'facilitators': ('process_manager_project_facilitators', 'facilitator_id'),
    'users': ('process_manager_project_users', 'user_id'),
}


def linked_ids(project_id, kind):
    """Identifiants des facilitateurs (`kind='facilitators'`) ou utilisateurs (`'users'`) liés au projet."""
    if not project_id:
        return []
    table, column = LINK_TABLES[kind]
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT {column} FROM {table} WHERE project_id = %s ORDER BY {column}", [project_id])
        return [row[0] for row in cursor.fetchall()]


def set_links(project_id, kind, ids):
    """Remplace les liens du projet par `ids` (ajoute les nouveaux, retire les absents). Renvoie (ajoutés, retirés)."""
    table, column = LINK_TABLES[kind]
    wanted = {int(i) for i in ids}
    with transaction.atomic():
        current = set(linked_ids(project_id, kind))
        added, removed = sorted(wanted - current), sorted(current - wanted)
        with connection.cursor() as cursor:
            if removed:
                cursor.execute(f"DELETE FROM {table} WHERE project_id = %s AND {column} = ANY(%s)", [project_id, removed])
            for item_id in added:
                cursor.execute(f"INSERT INTO {table} (project_id, {column}) VALUES (%s, %s)", [project_id, item_id])
    return added, removed
