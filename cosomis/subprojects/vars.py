from subprojects.models import Subproject

subprojects = Subproject.objects.get_actifs()

VAR_SUB_PROJECT_SECTORS = [('', '')] + list(subprojects.values_list('subproject_sector', 'subproject_sector').distinct().order_by('subproject_sector'))

VAR_TYPES_OF_SUB_PROJECT = [('', '')] + list(subprojects.values_list('type_of_subproject', 'type_of_subproject').distinct().order_by('type_of_subproject'))

VAR_COMPONENTS = [('', '')] + list(subprojects.values_list('component__name', 'component__name').distinct().order_by('component__name'))
