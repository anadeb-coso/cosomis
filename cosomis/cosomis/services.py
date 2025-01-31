from django.conf import settings

def overall_variables(request):
    """Function to define globals variables"""
    return {
        'OTHER_LANGUAGES': True, #Variable to define if other languages are setuped
        'CURRENCY_UNIT': 'FCFA',
        
        'DOMAIN_PATH': ("http://" if "127." in request.get_host() else "https://") + (request.get_host()),

        "CDD_URL_BASE": settings.CDD_URL_BASE,
        "MIS_URL_BASE": settings.MIS_URL_BASE,
        "GRM_URL_BASE": settings.GRM_URL_BASE,
    }

