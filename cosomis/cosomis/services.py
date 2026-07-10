from django.conf import settings
from django.db import connections

from subprojects.models import Project


def get_user_projects(user):
    
    user_email = user.email if user.is_authenticated else None

    with connections['cdd'].cursor() as cursor:
        cursor.execute("""
            SELECT p.id, p.name
            FROM process_manager_project p
            INNER JOIN process_manager_project_users pu ON pu.project_id = p.id
            INNER JOIN auth_user auth_user ON auth_user.id = pu.user_id
            WHERE auth_user.email = %s;
        """, [user_email])

        rows = cursor.fetchall()
    return rows


def overall_variables(request):
    """Function to define globals variables"""

    projects = get_user_projects(request.user)

    return {
        'OTHER_LANGUAGES': True, #Variable to define if other languages are setuped
        'CURRENCY_UNIT': 'FCFA',
        
        'DOMAIN_PATH': ("http://" if "127." in request.get_host() else "https://") + (request.get_host()),

        "CDD_URL_BASE": settings.CDD_URL_BASE,
        "MIS_URL_BASE": settings.MIS_URL_BASE,
        "GRM_URL_BASE": settings.GRM_URL_BASE,

        "PROJECT_ID": request.session.get('project_id'),
        "PROJECT_NAME": request.session.get('project_name'),
        "PROJECTS_IDS": request.session.get('tree_structure_projects_ids'),
        "PROJECTS_NAMES": request.session.get('tree_structure_projects_names'),
        
        "PROJECTS": Project.objects.filter(name__in=[p[1] for p in projects])
    }

