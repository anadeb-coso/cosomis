from subprojects.models import Subproject

subprojects = Subproject.objects.get_actifs()

# secteurs, types d'ouvrage, types de travaux et désignations : listes de référence (subprojects.models)

VAR_COMPONENTS = [('', '')] + list(subprojects.values_list('component__name', 'component__name').distinct().order_by('component__name'))
