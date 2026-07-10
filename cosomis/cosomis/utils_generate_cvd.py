import datetime
from datetime import timedelta
from django.utils import timezone
import itertools

from subprojects.models import Subproject, Component, SubprojectStep, Level, Step, Project
from no_sql_client import NoSQLClient
from authentication.models import Facilitator
from administrativelevels.models import AdministrativeLevel, GeographicalUnit, CVD
from assignments.models import AssignAdministrativeLevelToFacilitator
from administrativelevels.libraries.functions import strip_accents




def generate_unit_cvd_by_canton(canton_ids, villages_ids_to_exclude=[]):
    administrative_levels = list(itertools.chain(*[list(c.children.filter(type="Village", cvd=None).exclude(parent=None, id__in=villages_ids_to_exclude)) for c in AdministrativeLevel.objects.filter(type="Canton", id__in=canton_ids)]))

    for adl in administrative_levels:
        g_u = GeographicalUnit.objects.filter(canton_id=adl.parent.id).order_by('attributed_number_in_canton').last()
        attributed_number_in_canton = 0
        if g_u:
            attributed_number_in_canton = g_u.attributed_number_in_canton
        
        attributed_number_in_canton += 1

        unit = GeographicalUnit(
            canton=adl.parent,
            attributed_number_in_canton=attributed_number_in_canton
        )
        try:
            length_str = str(GeographicalUnit.objects.all().last().pk + 1)
        except Exception as exc:
            length_str = "1"
        unit.unique_code = ('0'*(9-len(length_str))) + length_str
        unit = unit.save_and_return_object()


        length_str_cvd = str(CVD.objects.all().last().pk + 1)
        cvd = CVD(
            geographical_unit = unit,
            unique_code = ('0'*(9-len(length_str_cvd))) + length_str_cvd,
            name = adl.name,
            headquarters_village = adl
        )
        
        cvd = cvd.save_and_return_object()
        
        adl.cvd = cvd
        adl.geographical_unit = unit
        adl.save()



def generate_unit_cvd(project_name):
    administrative_levels = AdministrativeLevel.objects.filter(type="Village", cvd=None).exclude(parent=None)

    for adl in administrative_levels:
        g_u = GeographicalUnit.objects.filter(canton_id=adl.parent.id).order_by('attributed_number_in_canton').last()
        attributed_number_in_canton = 0
        if g_u:
            attributed_number_in_canton = g_u.attributed_number_in_canton
        
        attributed_number_in_canton += 1

        unit = GeographicalUnit(
            canton=adl.parent,
            attributed_number_in_canton=attributed_number_in_canton
        )
        try:
            length_str = str(GeographicalUnit.objects.all().last().pk + 1)
        except Exception as exc:
            length_str = "1"
        unit.unique_code = ('0'*(9-len(length_str))) + length_str
        unit = unit.save_and_return_object()


        length_str_cvd = str(CVD.objects.all().last().pk + 1)
        cvd = CVD(
            geographical_unit = unit,
            unique_code = ('0'*(9-len(length_str_cvd))) + length_str_cvd,
            name = adl.name,
            headquarters_village = adl
        )
        
        cvd = cvd.save_and_return_object()
        
        adl.cvd = cvd
        adl.geographical_unit = unit
        adl.save()

        projects = Project.objects.filter(name=project_name)
        if projects.exists():
            project = projects.first()
            project.administrative_levels.add(adl)
            project.save()


def add_project_attr_on_adl(project_name):
    projects = Project.objects.filter(name=project_name)
    if projects.exists():
        administrative_levels = AdministrativeLevel.objects.filter(type="Village")
        administrative_levels = [adl for adl in administrative_levels if not Project.objects.filter(administrative_levels__id__in=[adl.id]).exists()]
        project = projects.first()
        project.administrative_levels.add(*administrative_levels)
        project.save()