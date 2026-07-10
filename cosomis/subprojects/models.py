from email.policy import default
from django.db import models
import locale
from django.utils.translation import gettext_lazy as _
from django.db.models.signals import post_save
from typing import TypeVar, Any
from django.db.models import Q
from django.contrib.auth import get_user_model
from datetime import date, timedelta

from administrativelevels.models import AdministrativeLevel, CVD
from subprojects import SUB_PROJECT_TYPE_DESIGNATION
from cosomis.customers_fields import *
from cosomis.types import _QS
from cosomis.models_base import BaseModel
from administrativelevels.functions_adl import get_cascade_villages_ids_by_administrative_level_id
from cosomis.constants import IMAGE_EXTENSIONS, STRUCTURE_IN_PROGRESS_STATUS, STRUCTURE_IN_PROGRESS_RANKING_LIST

User = get_user_model()

class CustomQuerySet(models.QuerySet):
    
    def filter_by_step(self, Type, step_id) -> _QS:
        l = []
        for o in self:
            if o.get_current_subproject_step and o.get_current_subproject_step.step.id == step_id:
                l.append(o)
                
        return Type.objects.filter(id__in=[o.id for o in l])


    def filter_by_steps_already_track(self, Type, step_id) -> _QS:
        l = []
        step = Step.objects.filter(id=step_id).first()
        for o in self:
            if o.check_step(step):
                l.append(o)
                
        return Type.objects.filter(id__in=[o.id for o in l])
    
    def get_actifs(self, projects_ids=[]):
        if projects_ids:
            return self.filter(projects__in=projects_ids).exclude(infrastructure_deleted=True)
        return self.exclude(infrastructure_deleted=True)

    def get_objects_by_general_filtre(self, request, attrs, *args, **kwargs):
        if attrs:
            return self.filter(**attrs)
        elif request and request.user and request.user.is_authenticated:
            all_projects = request.GET.getlist('all_projects[]') or request.GET.getlist('all_projects') or request.POST.getlist('all_projects[]') or request.POST.getlist('all_projects')
            return self.filter(projects__in=(
                    all_projects if type(all_projects) is list and len(all_projects) >= 2 else [request.session.get('project_id')]
                )
            )
        return self.filter()


# Create your models here.
class Subproject(BaseModel):
    location_subproject_realized = models.ForeignKey(AdministrativeLevel, null=True, blank=True, on_delete=models.CASCADE, related_name='location_subproject_realized', verbose_name=_("Subproject location"))
    cvd = models.ForeignKey(CVD, null=True, blank=True, on_delete=models.CASCADE, verbose_name=_("CVD"))
    # cvds = models.ManyToManyField(CVD, default=[], blank=True, related_name="cvds_subprojects", verbose_name=_("Beneficiaries CVD"))
    list_of_beneficiary_villages = models.ManyToManyField(AdministrativeLevel, default=[], blank=True, related_name="vilages_subprojects", verbose_name=_("Beneficiaries villages"))
    canton = models.ForeignKey(AdministrativeLevel, null=True, blank=True, on_delete=models.CASCADE, verbose_name=_("Canton")) #canton subprojects (rural track)
    list_of_villages_crossed_by_the_track_or_electrification = models.ManyToManyField(AdministrativeLevel, default=[], blank=True, related_name="cantonal_subprojects", verbose_name=_("List of villages where the runway or electrification crosses"))
    link_to_subproject = models.ForeignKey('Subproject', null=True, blank=True, on_delete=models.CASCADE, verbose_name=_("Linked to a sub-project"), related_name='linked_subprojects') #To link the subprojects that the cantons or CVD link to make
    
    number = models.IntegerField(null=True, blank=True, verbose_name=_("Number unique to each sub-project or infrastructure"))
    joint_subproject_number = models.IntegerField(null=True, blank=True, verbose_name=_("Subproject kit number"))
    intervention_unit = models.IntegerField(null=True, blank=True, verbose_name=_("Intervention unit"))
    facilitator_name = models.CharField(max_length=255, null=True, blank=True, verbose_name=_("Facilitator name"))
    wave = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("Arbitrage wave"))
    lot = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("Lot"))
    market_name = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("Market name"))
    subproject_sector = models.CharField(max_length=100, verbose_name=_("Subproject sector"))
    type_of_subproject = models.CharField(max_length=150, verbose_name=_("Type of structure"))
    subproject_type_designation = models.CharField(max_length=100, choices=SUB_PROJECT_TYPE_DESIGNATION, default='Subproject', verbose_name=_("Subproject type designation (Subproject or Infrastructure)"))
    full_title_of_approved_subproject = models.TextField(max_length=255, verbose_name=_("Full title of approved sub-project (description)"))
    works_type = models.CharField(max_length=150, null=True, blank=True, verbose_name=_("Works type"))
    estimated_cost = models.FloatField(null=True, blank=True, verbose_name=_("Estimated cost"))
    exact_amount_spent = models.FloatField(null=True, blank=True, verbose_name=_("Exact amount spent on the sub-project"))
    level_of_achievement_donation_certificate = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("Level of donation certificate"))
    approval_date_cora = models.DateField(null=True, blank=True, verbose_name=_("Approval date cora"))
    date_of_signature_of_contract_for_construction_supervisors = models.DateField(null=True, blank=True, verbose_name=_("Date signature contrat controleurs de travaux BTP (CT)"))
    amount_of_the_contract_for_construction_supervisors = models.FloatField(null=True, blank=True, verbose_name=_("Contract amount for construction supervisors BTP (CT)"))
    date_signature_contract_controllers_in_SES = models.DateField(null=True, blank=True, verbose_name=_("Date signed SES controllers contract (CSES)"))
    amount_of_the_controllers_contract_in_SES = models.FloatField(null=True, blank=True, verbose_name=_("Contract amount for SES controllers (CSES)"))
    convention = models.CharField(max_length=255, null=True, blank=True, verbose_name=_("Convention"))
    contract_number_of_work_companies = models.CharField(max_length=255, null=True, blank=True, verbose_name=_("Contract no. for work companies (ET)"))
    name_of_the_awarded_company_works_companies = models.CharField(max_length=255, null=True, blank=True, verbose_name=_("Name of company awarded work contract (ET)"))
    date_signature_contract_work_companies = models.DateField(null=True, blank=True, verbose_name=_("Date of signature of works contract (ET)"))
    contract_amount_work_companies = models.FloatField(null=True, blank=True, verbose_name=_("Contract amount for works companies (ET)"))
    name_of_company_awarded_efme = models.CharField(max_length=255, null=True, blank=True, verbose_name=_("Name of contractor entreprises de fourniture de mobiliers et equipements (EFME)"))
    date_signature_contract_efme = models.DateField(null=True, blank=True, verbose_name=_("Date signature contrat entreprises de fourniture de mobiliers et equipements (EFME)"))
    contract_companies_amount_for_efme = models.FloatField(null=True, blank=True, verbose_name=_("Contract amount Entreprises de fourniture de mobiliers et equipements (EFME)"))
    date_signature_contract_facilitator = models.DateField(null=True, blank=True, verbose_name=_("Date of signature of facilitator contract"))
    amount_of_the_facilitator_contract = models.FloatField(null=True, blank=True, verbose_name=_("Contract amount for facilitator"))
    launch_date_of_the_construction_site_in_the_village = models.DateField(null=True, blank=True, verbose_name=_("Date of start of work in the village (date of notification of service order)"))
    current_level_of_physical_realization_of_the_work = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("Current level of physical realization of the work"))
    current_level_of_physical_realization_of_the_work_percent = models.FloatField(null=True, blank=True, verbose_name=_("Current level of physical realization of the work (percent)"))
    current_level_of_physical_realization_of_the_work_wording = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("Current level of physical realization of the work (wording)"))
    length_of_the_track = models.FloatField(null=True, blank=True, verbose_name=_("Length of track (km)"))
    depth_of_drilling = models.FloatField(null=True, blank=True, verbose_name=_("Borehole depth (m)"))
    drilling_flow_rate = models.FloatField(null=True, blank=True, verbose_name=_("Borehole flow (m3)"))
    current_status_of_the_site = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("Current site status (Work in progress, Work stopped, Work abandoned, Technical acceptance, Provisional acceptance, etc.)"))
    expected_duration_of_the_work = models.FloatField(null=True, blank=True, verbose_name=_("Estimated completion time (months)"))
    expected_end_date_of_the_contract = models.DateField(null=True, blank=True, verbose_name=_("Expected contract end date"))
    total_contract_amount_paid = models.FloatField(null=True, blank=True, verbose_name=_("Total amount of the pay contract (technical inspection + safeguard inspection + construction company + furniture company + facilitator)"))
    amount_of_the_care_and_maintenance_fund_expected_to_be_mobilized = models.FloatField(null=True, blank=True, verbose_name=_("Upkeep and maintenance fund (EMI) to be mobilized"))
    care_and_maintenance_amount_on_village_account = models.FloatField(null=True, blank=True, verbose_name=_("Amount of maintenance fund (EMI) mobilized and deposited in village account"))
    existence_of_maintenance_and_upkeep_plan_developed_by_community = models.BooleanField(null=True, blank=True, default=False, verbose_name=_("Existence of a maintenance and upkeep plan (EMI plan) drawn up by the community (if yes, put 1; if no, put 0)"))
    work_completion_date = models.DateField(null=True, blank=True, verbose_name=_("Work completion date"))
    amount_spent_on_completing_the_infrastructure = models.FloatField(null=True, blank=True, verbose_name=_("Amount spent on completing the infrastructure"))
    date_of_technical_acceptance_of_work_contracts = models.DateField(null=True, blank=True, verbose_name=_("Dates for technical acceptance of work contracts (BTP or FORAGE)"))
    technical_acceptance_date_for_efme_contracts = models.DateField(null=True, blank=True, verbose_name=_("Technical acceptance dates for furniture and equipment supply contracts"))
    date_of_provisional_acceptance_of_work_contracts = models.DateField(null=True, blank=True, verbose_name=_("Dates of provisional acceptance of work contracts (BTP or FORAGE)"))
    amount_spent_on_infrastructure_up_to_provisional_acceptance = models.FloatField(null=True, blank=True, verbose_name=_("Amount spent on infrastructure up to provisional acceptance"))
    provisional_acceptance_date_for_efme_contracts = models.DateField(null=True, blank=True, verbose_name=_("Provisional acceptance dates for furniture and equipment supply contracts"))
    official_handover_date_of_the_microproject_to_the_community = models.DateField(null=True, blank=True, verbose_name=_("Date of official handover of the microproject to the community"))
    official_handover_date_of_the_microproject_to_the_sector = models.DateField(null=True, blank=True, verbose_name=_("Date of official handover of the microproject to the sector"))
    date_of_final_acceptance_of_the_work = models.DateField(null=True, blank=True, verbose_name=_("Date of final acceptance of the work"))
    comments = models.TextField(null=True, blank=True, verbose_name=_("Comments"))
    
    target_female_beneficiaries = models.IntegerField(null=True, blank=True, verbose_name=_("Target female beneficiaries"))
    target_male_beneficiaries = models.IntegerField(null=True, blank=True, verbose_name=_("Target male beneficiaries"))
    target_youth_beneficiaries = models.IntegerField(null=True, blank=True, verbose_name=_("Target youth beneficiaries"))
    
    estimated_number_of_beneficiaries = models.IntegerField(null=True, blank=True, verbose_name=_("Estimated number of beneficiaries"))

    population = models.IntegerField(null=True, blank=True, verbose_name=_("Population"))
    direct_beneficiaries_men = models.IntegerField(null=True, blank=True, verbose_name=_("Direct beneficiaries men"))
    direct_beneficiaries_women = models.IntegerField(null=True, blank=True, verbose_name=_("Direct beneficiaries women"))
    indirect_beneficiaries_men = models.IntegerField(null=True, blank=True, verbose_name=_("Indirect beneficiaries men"))
    indirect_beneficiaries_women = models.IntegerField(null=True, blank=True, verbose_name=_("Indirect beneficiaries women"))

    component = models.ForeignKey('Component', null=True, on_delete=models.CASCADE, verbose_name=_("Component (Subcomponent)"))
    priorities = models.ManyToManyField('VillagePriority', default=[], blank=True, related_name='priorities_covered', verbose_name=_("Priorities"))
    priority = models.JSONField(blank=True, null=True, verbose_name=_('Priority'))
    
    latitude = models.FloatField(null=True, blank=True, verbose_name=_("Latitude"))
    longitude = models.FloatField(null=True, blank=True, verbose_name=_("Longitude"))

    projects = models.ManyToManyField('Project', default=[], blank=True, verbose_name=_("Projects")) #In Which projects that we finance the subproject
    financiers = models.ManyToManyField('Financier', default=[], blank=True, verbose_name=_("Financiers")) #Which Financiers finance this subproject (when its project is define, we don't need to specialize this attribute)

    #Whose choice this subproject?
    women_s_group = models.BooleanField(null=True, blank=True, verbose_name=_("Women's group"))
    youth_group = models.BooleanField(null=True, blank=True, verbose_name=_("Youth group"))
    breeders_farmers_group = models.BooleanField(null=True, blank=True, verbose_name=_("Breeders farmers group"))
    ethnic_minority_group = models.BooleanField(null=True, blank=True, verbose_name=_("Ethnic minority group"))
    refugee_and_internally_displaced_persons_group = models.BooleanField(null=True, blank=True, verbose_name=_("Refugee and internally displaced persons group"))

    has_latrine_blocs = models.BooleanField(null=True, blank=True, verbose_name=_("Latrine blocks?"))
    number_of_latrine_blocks = models.IntegerField(null=True, blank=True, verbose_name=_("Number of latrine blocks"))
    number_of_classrooms = models.IntegerField(null=True, blank=True, verbose_name=_("Number of classrooms"))
    has_fence = models.BooleanField(null=True, blank=True, verbose_name=_("Has a fence?"))
    storage_capacity = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("Storage capacity"))
    extension_length = models.IntegerField(null=True, blank=True, verbose_name=_("Extension length (km)"))
    number_of_sections_of_track_developed = models.IntegerField(null=True, blank=True, verbose_name=_("Number of sections of track developed"))
    distance_covered_by_streetlights = models.IntegerField(null=True, blank=True, verbose_name=_("Distance covered by streetlights (km)"))
    number_of_streetlights = models.IntegerField(null=True, blank=True, verbose_name=_("Number of streetlights installed"))
    number_of_drinking_fountains = models.IntegerField(null=True, blank=True, verbose_name=_("Number of drinking fountains"))

    date_of_organization_of_the_social_audit = models.DateField(null=True, blank=True, verbose_name=_("Date of organization of the social audit"))
    number_of_participants_m_in_the_social_audit = models.IntegerField(null=True, blank=True, verbose_name=_("Number of participants (M) in the social audit"))
    number_of_participants_w_in_the_social_audit = models.IntegerField(null=True, blank=True, verbose_name=_("Number of participants (W) in the social audit"))
    number_of_participants_t_in_the_social_audit = models.IntegerField(null=True, blank=True, verbose_name=_("Number of participants (T) in the social audit"))
    
    infrastructure_changed = models.BooleanField(null=True, blank=True, verbose_name=_("Infrastructure changed?"))
    infrastructure_deleted = models.BooleanField(null=True, blank=True, verbose_name=_("Infrastructure will no longer be built?"))
    number_of_infrastructures = models.IntegerField(null=True, blank=True, verbose_name=_("Number of infrastructures"))

    objects = CustomQuerySet.as_manager()


    class Meta:
        unique_together = [['number', 'joint_subproject_number']]
    #     unique_together = [
    #         [
    #             'full_title_of_approved_subproject', 'location_subproject_realized', 
    #             'subproject_sector', 'type_of_subproject'
    #         ], 
    #         ['canton', 'full_title_of_approved_subproject'],
    #         ['number']
    #     ]

        

    def get_cantons_names(self):
        if self.location_subproject_realized:
            return self.location_subproject_realized.parent.name
        elif self.canton: 
            cantons = self.canton.name
            subprojects_link_objects = self.get_all_subprojects_linked()
            if subprojects_link_objects:
                cantons += "/"
            for i in range(len(subprojects_link_objects)):
                cantons += subprojects_link_objects[i].canton.name
                if i+1 < len(subprojects_link_objects):
                    cantons += "/"
            return cantons
        return None

    def get_canton(self):
        if self.location_subproject_realized:
            return self.location_subproject_realized.parent
        elif self.canton:
            return self.canton

        return None
    
    def get_village(self):
        if self.location_subproject_realized:
            return self.location_subproject_realized
        elif self.canton:
            a = AdministrativeLevel()
            a.name = "CCD"
            return a

        return None
    
    def get_villages(self):
        if self.location_subproject_realized:
            return self.location_subproject_realized.cvd.administrativelevel_set.get_queryset()
        elif self.canton:
            return self.list_of_villages_crossed_by_the_track_or_electrification.all()

        return []
    
    def get_villages_str(self):
        return ", ".join([o.name for o in self.get_villages()])

    def get_location(self):
        cantons_names = self.get_cantons_names()
        canton = self.get_canton()
        location = ""
        if canton:
            location = canton.parent.parent.parent.name + ", " + canton.parent.parent.name + ", " + canton.parent.name
        if cantons_names:
            location += ", " + cantons_names
        if self.location_subproject_realized:
            location += ", " + self.location_subproject_realized.name
        return location

    def get_location_commune(self):
        cantons_names = self.get_cantons_names()
        canton = self.get_canton()
        location = ""
        if canton:
            location = canton.parent.parent.parent.name + ", " + canton.parent.parent.name + ", " + canton.parent.name
        
        return location
    
    def get_location_subproject_realized(self):
        _location_subproject_realized = None
        if self.location_subproject_realized:
            _location_subproject_realized = self.location_subproject_realized
        elif self.cvd:
            _location_subproject_realized = self.cvd.headquarters_village
        elif self.canton:
            _location_subproject_realized = self.canton.children.first()
        elif self.list_of_beneficiary_villages.all().exists():
            _location_subproject_realized = self.list_of_beneficiary_villages.all().first()
        elif self.list_of_villages_crossed_by_the_track_or_electrification.all().exists():
            _location_subproject_realized = self.list_of_villages_crossed_by_the_track_or_electrification.all().first()
            
        return _location_subproject_realized

    def get_all_subprojects_linked(self):
        return self.linked_subprojects.get_queryset().get_actifs()
    
    @property
    def has_subprojects_linked(self):
        if self.get_all_subprojects_linked():
            return True
        return False
    
    def get_infrastructures_linked(self):
        return self.get_all_subprojects_linked().filter(subproject_type_designation="Infrastructure")
    
    def get_subprojects_linked(self):
        return self.get_all_subprojects_linked().filter(subproject_type_designation="Subproject")
    
    def get_estimated_cost(self):
        all_subprojects_linked = self.get_all_subprojects_linked()
        return (
            (self.estimated_cost if self.estimated_cost else 0) + \
            sum([o.estimated_cost for o in all_subprojects_linked if o.estimated_cost])
        )

    def get_estimated_cost_str(self):
        locale.setlocale( locale.LC_ALL, '' )
        estimated_cost_str = ""
        estimated_cost_str += locale.currency(self.estimated_cost if self.estimated_cost else 0, grouping=True).__str__()
        subproject_link_objects = self.get_all_subprojects_linked()
        if subproject_link_objects:
            for o in subproject_link_objects:
                if o.estimated_cost:
                    estimated_cost_str += " + " + locale.currency(o.estimated_cost, grouping=True).__str__()
            return (locale.currency(self.get_estimated_cost(), grouping=True).__str__() + f' ({estimated_cost_str})').replace("$", "")
        
        return estimated_cost_str.replace("$", "")

    def get_files(self, include_children=False):
        if include_children:
            subproject_ids = list(self.get_all_subprojects_linked().values_list('id', flat=True)) + [self.id]
            return SubprojectFile.objects.filter(subproject__id__in=subproject_ids).order_by("-date_taken")
        return self.subprojectfile_set.get_queryset().filter().order_by("-date_taken")
    
    def get_all_images(self, order=False):
        query = Q()

        for ext in IMAGE_EXTENSIONS:
            query |= Q(url__icontains=ext)

        if order:
            return sorted(self.subprojectfile_set.get_queryset().filter(file_type__icontains="image").filter(query), key=lambda o: o.order).order_by("-principal")
        return self.subprojectfile_set.get_queryset().filter(file_type__icontains="image").filter(query).order_by("-principal")

    def get_all_exclude_images(self, order=False):
        query = Q()

        for ext in IMAGE_EXTENSIONS:
            query |= Q(url__icontains=ext)

        if order:
            return sorted(self.subprojectfile_set.get_queryset().exclude(file_type__icontains="image").exclude(query), key=lambda o: o.order)
        return self.subprojectfile_set.get_queryset().exclude(file_type__icontains="image").exclude(query)
    
    def get_principal_image(self):
        for img in self.get_all_images():
            if img.principal:
                return img
        return None

    @property
    def get_all_projects(self):
        return self.projects.all()

    @property
    def get_all_financiers(self):
        return self.financiers.all()
    
    def get_projects_ids(self):
        return [o.id for o in self.projects.all()]
    
    @property
    def get_facilitator(self):
        _location_subproject_realized = self.get_location_subproject_realized()
        
        if _location_subproject_realized:
            return _location_subproject_realized.get_facilitator(self.get_projects_ids())

        return None
    
    @property
    def get_technical_facilitator(self):
        _location_subproject_realized = self.get_location_subproject_realized()
        
        if _location_subproject_realized:
            return _location_subproject_realized.get_facilitator(self.get_projects_ids(), is_technical_facilitator=True)

        return None

    @property
    def get_facilitator_name(self):
        facilitator = self.get_facilitator
        if facilitator:
            return f"{facilitator.name} ({facilitator.email}, {facilitator.phone})"
        
        if self.facilitator_name:
            return self.facilitator_name
        
        return None

    @property
    def get_technical_facilitator_name(self):
        facilitator = self.get_technical_facilitator
        if facilitator:
            return f"{facilitator.name} ({facilitator.email}, {facilitator.phone})"
        
        return None
    
    def get_subproject_steps(self, order=True):
        if order:
            return self.subprojectstep_set.get_queryset().order_by("-begin", "-created_date", "-ranking")
            #sorted(self.subprojectstep_set.get_queryset(), key=lambda o: o.begin, reverse=True) #self.subprojectstep_set.get_queryset().order_by("-ranking") #
        return self.subprojectstep_set.get_queryset()
    
    @property
    def get_current_subproject_step(self):
        return self.get_subproject_steps().first()
    
    @property
    def get_current_subproject_step_and_level(self):
        step = self.get_current_subproject_step
        if step and (step.wording in STRUCTURE_IN_PROGRESS_STATUS or (step.ranking in STRUCTURE_IN_PROGRESS_RANKING_LIST)):
            level = step.get_levels().first()
            if level:
                return level.__str__()
        if step:
            return step.__str__()
        if self.current_level_of_physical_realization_of_the_work:
            if not self.current_level_of_physical_realization_of_the_work.replace('.','',1).replace(',','',1).isdigit():
                return self.current_level_of_physical_realization_of_the_work
            _status = float(self.current_level_of_physical_realization_of_the_work)
            if _status > 0 and _status < 100:
                return _("In progress")
            elif _status >= 100:
                return _("Completed")

        return None
    
    @property
    def get_current_subproject_step_and_level_without_percent(self):
        step = self.get_current_subproject_step
        if step and (step.wording in STRUCTURE_IN_PROGRESS_STATUS or (step.ranking in STRUCTURE_IN_PROGRESS_RANKING_LIST)):
            level = step.get_levels().first()
            if level:
                return level.wording
        if step:
            return step.wording
        if self.current_level_of_physical_realization_of_the_work:
            if not self.current_level_of_physical_realization_of_the_work.replace('.','',1).replace(',','',1).isdigit():
                return self.current_level_of_physical_realization_of_the_work
            _status = float(self.current_level_of_physical_realization_of_the_work)
            if _status > 0 and _status < 100:
                return _("In progress")
            elif _status >= 100:
                return _("Completed")

        return None
    
    @property
    def get_current_subproject_step_and_level_with_percent(self):
        step = self.get_current_subproject_step
        if step and (step.wording in STRUCTURE_IN_PROGRESS_STATUS or (step.ranking in STRUCTURE_IN_PROGRESS_RANKING_LIST)):
            level = step.get_levels().first()
            if level:
                return level.__str__()
        if step:
            return step.__str__()
        if self.current_level_of_physical_realization_of_the_work:
            if not self.current_level_of_physical_realization_of_the_work.replace('.','',1).replace(',','',1).isdigit():
                return self.current_level_of_physical_realization_of_the_work
            _status = float(self.current_level_of_physical_realization_of_the_work)
            if _status > 0 and _status < 100:
                return _("In progress") + f" {_status}%"
            elif _status >= 100:
                return _("Completed") + f" {_status}%"

        return None
    
    @property
    def get_current_subproject_step_and_level_object(self):
        step = self.get_current_subproject_step
        if step and (step.wording in STRUCTURE_IN_PROGRESS_STATUS or (step.ranking in STRUCTURE_IN_PROGRESS_RANKING_LIST)):
            level = step.get_levels().first()
            if level:
                return level
        if step:
            return step
        return None
    
    @property
    def get_current_level_object(self):
        in_progress_steps = self.subprojectstep_set.get_queryset().filter(Q(wording__in=STRUCTURE_IN_PROGRESS_STATUS) | Q(ranking__in=STRUCTURE_IN_PROGRESS_RANKING_LIST)).order_by("-begin", "-created_date", "-ranking")
        
        for step in in_progress_steps:
            level = step.get_levels().first()
            
            if level:
                return level
        return None
    
    def check_step(self, step):
        if not step:
            return False
        
        for s in self.subprojectstep_set.get_queryset():
            if s.wording == step.wording:
                return s
        return None
    
    def get_nearest_step_or_level_with_percent_from_step(self, step):
        
        for s in self.subprojectstep_set.get_queryset().filter(begin__isnull=False).filter(Q(begin__lte=step.begin) | Q(wording__in=STRUCTURE_IN_PROGRESS_STATUS) | Q(ranking__in=STRUCTURE_IN_PROGRESS_RANKING_LIST)).order_by("-begin", "-created_date", "-ranking"):
            
            if s.percent and not (s.wording in STRUCTURE_IN_PROGRESS_STATUS or (s.ranking in STRUCTURE_IN_PROGRESS_RANKING_LIST)) and s.begin and step.begin and s.begin <= step.begin:
                return s
            elif (s.wording in STRUCTURE_IN_PROGRESS_STATUS or (s.ranking in STRUCTURE_IN_PROGRESS_RANKING_LIST)) and step.begin:
                levels = s.get_levels().exclude(Q(percent__isnull=True) | Q(percent=0)).order_by("-begin", "-ranking", "-created_date")
                for l in levels:
                    if l.percent and l.begin and l.begin <= step.begin:
                        return l
                    
        return None
    
    @property
    def get_longitude(self):
        if self.longitude:
            return self.longitude
        liste = []
        if self.link_to_subproject:
            if self.link_to_subproject.longitude:
                return self.link_to_subproject.longitude
            liste.extend(
                list(self.link_to_subproject.get_all_subprojects_linked().values_list('longitude', flat=True))
            )
        else:
            liste.extend(
                list(self.get_all_subprojects_linked().values_list('longitude', flat=True))
            )
        if liste:
            return liste[0]
        
        if self.location_subproject_realized and self.location_subproject_realized.longitude:
            return self.location_subproject_realized.longitude
        
        return self.longitude
    
    @property
    def get_latitude(self):
        if self.latitude:
            return self.latitude
        liste = []
        if self.link_to_subproject:
            if self.link_to_subproject.latitude:
                return self.link_to_subproject.latitude
            liste.extend(
                list(self.link_to_subproject.get_all_subprojects_linked().values_list('latitude', flat=True))
            )
        else:
            liste.extend(
                list(self.get_all_subprojects_linked().values_list('latitude', flat=True))
            )
        if liste:
            return liste[0]
        
        if self.location_subproject_realized and self.location_subproject_realized.latitude:
            return self.location_subproject_realized.latitude
        
        return self.latitude

    @property
    def is_delayed_update(self, weeks=2):
        current_subproject_step_and_level_object = self.get_current_subproject_step_and_level_object
        step_date = None
        if current_subproject_step_and_level_object:
            if (
                (
                    current_subproject_step_and_level_object.__class__.__name__.lower() == "SubprojectStep".lower() and 
                    (
                        current_subproject_step_and_level_object.wording in STRUCTURE_IN_PROGRESS_STATUS or 
                        current_subproject_step_and_level_object.ranking in STRUCTURE_IN_PROGRESS_RANKING_LIST
                    )
                )
                or
                (
                    current_subproject_step_and_level_object.__class__.__name__.lower() == "Level".lower()
                )
            ):
                step_date = current_subproject_step_and_level_object.begin
                if step_date:
                    today = date.today()
                    if today - step_date >= timedelta(weeks=weeks):
                        return True
        return False

    def __str__(self):
        return self.full_title_of_approved_subproject

class _Step(BaseModel):
    wording = models.CharField(max_length=200, verbose_name=_("Wording"))
    percent = CustomerFloatRangeField(null=True, blank=True, verbose_name=_("Percent"), min_value=0, max_value=100)
    description = models.TextField(null=True, blank=True, verbose_name=_("Description"))
    ranking = models.FloatField(default=0, verbose_name=_("Ranking"))
    amount_spent_at_this_step = models.FloatField(null=True, blank=True, verbose_name=_("Amount spent at this stage"))
    total_amount_spent = models.FloatField(null=True, blank=True, verbose_name=_("Total amount spent"))

    class Meta:
        abstract = True

    def __str__(self):
        return f'{self.wording}' + (' '+str(self.percent)+'%' if self.percent else '')
    
class Step(_Step):
    has_levels = models.BooleanField(default=False, verbose_name=_("Has levels"))
    color = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("Color (hexadecimal)"))
    next_steps = models.ManyToManyField('self', blank=True, symmetrical=False, related_name='previous_steps', verbose_name=_("Next steps"))
    
    class Meta:
        unique_together = ['ranking']


class SubprojectStep(_Step):
    subproject = models.ForeignKey(Subproject, on_delete=models.CASCADE, verbose_name=_("Subproject"))
    step = models.ForeignKey(Step, on_delete=models.CASCADE, verbose_name=_("Step"))
    begin = models.DateField(verbose_name=_("Begin"))
    end = models.DateField(null=True, blank=True, verbose_name=_("End"))
    
    def get_levels(self, order=True):
        if order:
            return self.level_set.get_queryset().order_by("-begin", "-ranking", "-created_date", "-id")
            #sorted(self.level_set.get_queryset(), key=lambda o: o.begin, reverse=True)
        return self.level_set.get_queryset()
    
    def check_step(self, wording):
        for l in self.level_set.get_queryset():
            if l.wording == wording:
                return True
        return False
    
    def get_files(self):
        if (self.wording in STRUCTURE_IN_PROGRESS_STATUS or (self.ranking in STRUCTURE_IN_PROGRESS_RANKING_LIST)):
            return SubprojectFile.objects.filter(
                Q(subproject_level__subproject_step__id=self.id) | Q(subproject_step__id=self.id)
            ).order_by("-date_taken")
        return self.subprojectfile_set.get_queryset().filter().order_by("-date_taken")
    
    def get_images(self):
        query = Q()

        for ext in IMAGE_EXTENSIONS:
            query |= Q(url__icontains=ext)

        if (self.wording in STRUCTURE_IN_PROGRESS_STATUS or (self.ranking in STRUCTURE_IN_PROGRESS_RANKING_LIST)):
            return SubprojectFile.objects.filter(
                Q(subproject_level__subproject_step__id=self.id) | Q(subproject_step__id=self.id),
                file_type__icontains="image"
            ).filter(query).order_by("-date_taken")
        return self.subprojectfile_set.get_queryset().filter(file_type__icontains="image").filter(query).order_by("-date_taken")

    def get_exclude_images(self):
        query = Q()

        for ext in IMAGE_EXTENSIONS:
            query |= Q(url__icontains=ext)

        if (self.wording in STRUCTURE_IN_PROGRESS_STATUS or (self.ranking in STRUCTURE_IN_PROGRESS_RANKING_LIST)):
            return SubprojectFile.objects.filter(
                Q(subproject_level__subproject_step__id=self.id) | Q(subproject_step__id=self.id)
            ).exclude(
                file_type__icontains="image"
            ).exclude(query).order_by("-date_taken")
        return self.subprojectfile_set.get_queryset().exclude(file_type__icontains="image").exclude(query).order_by("-date_taken")
    
    def get_last_image(self):
        return self.get_images().last()

    def get_last_exclude_image(self):
        return self.get_exclude_images().last()
        
    
    def __str__(self):
        percent = self.percent
        for level in  self.get_levels():
            if (level.percent and not percent) or (level.percent and percent and level.percent > percent):
                percent = level.percent
        return f'{self.wording}' + (' '+str(percent)+'%' if percent else '')

class Level(_Step):
    subproject_step = models.ForeignKey(SubprojectStep, on_delete=models.CASCADE, verbose_name=_("Step"))
    percent = CustomerFloatRangeField(verbose_name=_("Percent"), min_value=0, max_value=100)
    begin = models.DateField(verbose_name=_("Begin"))
    end = models.DateField(null=True, blank=True, verbose_name=_("End"))
    
    def get_files(self):
        return self.subprojectfile_set.get_queryset().filter().order_by("-date_taken")
    
    def get_images(self):
        query = Q()

        for ext in IMAGE_EXTENSIONS:
            query |= Q(url__icontains=ext)

        return self.subprojectfile_set.get_queryset().filter(file_type__icontains="image").filter(query).order_by("-date_taken")

    def get_exclude_images(self):
        query = Q()

        for ext in IMAGE_EXTENSIONS:
            query |= Q(url__icontains=ext)
            
        return self.subprojectfile_set.get_queryset().exclude(file_type__icontains="image").exclude(query).order_by("-date_taken")
    
    def get_last_image(self):
        return self.get_images().last()

    def get_last_exclude_image(self):
        return self.get_exclude_images().last()


class VulnerableGroup(BaseModel):
    name = models.CharField(max_length=255)
    description = models.TextField()
    administrative_level = models.ForeignKey(AdministrativeLevel, null=False, on_delete=models.CASCADE)

    def __str__(self):
        return self.name



class VillageObstacle(BaseModel):
    administrative_level = models.ForeignKey(AdministrativeLevel, on_delete=models.CASCADE)
    focus_group = models.CharField(max_length=255)
    description = models.TextField()
    meeting = models.ForeignKey('VillageMeeting', on_delete=models.CASCADE)
    ranking = models.IntegerField(default=0)

    def __str__(self):
        return self.description


class VillageGoal(BaseModel):
    administrative_level = models.ForeignKey(AdministrativeLevel, on_delete=models.CASCADE)
    focus_group = models.CharField(max_length=255)
    description = models.TextField()
    meeting = models.ForeignKey('VillageMeeting', on_delete=models.CASCADE)
    ranking = models.IntegerField(default=0)

    def __str__(self):
        return self.description


class VillagePriority(BaseModel):
    administrative_level = models.ForeignKey(AdministrativeLevel, on_delete=models.CASCADE)
    component = models.ForeignKey('Component', null=True, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    proposed_men = models.IntegerField(null=True, blank=True)
    proposed_women = models.IntegerField(null=True, blank=True)
    estimated_cost = models.FloatField(null=True, blank=True)
    estimated_beneficiaries = models.IntegerField(null=True, blank=True)
    climate_changing_contribution = models.TextField(null=True, blank=True)
    eligibility = models.BooleanField(blank=True, null=True)
    sector = models.CharField(max_length=255, null=True, blank=True)
    parent = models.ForeignKey('VillagePriority', null=True, blank=True, on_delete=models.CASCADE)
    meeting = models.ForeignKey('VillageMeeting', on_delete=models.CASCADE)
    ranking = models.IntegerField(default=0)

    def __str__(self):
        return self.name


class TypeMain(BaseModel):
    village_priority = models.ForeignKey(VillagePriority, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    value = models.CharField(max_length=255)

    def __str__(self):
        return "{} : {}".format(self.name, self.value)


class VillageMeeting(BaseModel):
    description = models.TextField()
    date_conducted = models.DateTimeField()
    administrative_level = models.ForeignKey(AdministrativeLevel, on_delete=models.CASCADE)
    type = models.CharField(max_length=255)
    ranking = models.IntegerField(default=0)

    def __str__(self):
        return self.description


class Component(BaseModel):
    name = models.CharField(max_length=255)
    parent = models.ForeignKey('Component', null=True, blank=True, on_delete=models.CASCADE)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.name


class SubprojectFile(BaseModel):
    subproject = models.ForeignKey(Subproject, null=True, blank=True, on_delete=models.CASCADE)
    subproject_step = models.ForeignKey(SubprojectStep, null=True, blank=True, on_delete=models.CASCADE)
    subproject_level = models.ForeignKey(Level, null=True, blank=True, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    url = models.CharField(max_length=255)
    order = models.IntegerField(default=0)
    principal = models.BooleanField(default=False)
    special = models.BooleanField(default=False)
    date_taken = models.DateField()
    file_type = models.CharField(max_length=100, default="image")
    description = models.TextField(null=True, blank=True)
    validated = models.BooleanField(null=True, blank=True)
    review = models.BooleanField(default=False)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="user_files")
    facilitator_id = models.IntegerField(null=True, blank=True)

    @property
    def comments(self):
        return self.filecomment_set.get_queryset()


class FileComment(BaseModel):
    file = models.ForeignKey(SubprojectFile, on_delete=models.CASCADE)
    comment = models.TextField(verbose_name=_("Comment"))
    type = models.CharField(max_length=25, default="comment")
    comment_read = models.BooleanField(default=False)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="file_comments")


class Financier(BaseModel):
    name = models.CharField(max_length=255)
    description = models.TextField()

    def __str__(self):
        return self.name
    

class Project(BaseModel):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField()
    parent = models.ForeignKey('Project', null=True, blank=True, on_delete=models.CASCADE)
    financiers = models.ManyToManyField('Financier', default=[], blank=True, related_name="financiers_projects")

    administrative_levels = models.ManyToManyField(AdministrativeLevel, default=[], blank=True, verbose_name=_("Administrative Levels"), related_name="administrative_levels_projects")


    def __str__(self):
        return self.name
    
    @property
    def get_all_financiers(self):
        return self.financiers.all()
    
    def build_the_tree_structure(self):
        """
        Construit l'arborescence complète (ascendants + descendants)
        en partant de ce projet.
        Retourne une liste ordonnée de projets.
        """
        visited = set()

        # --- 1. Remonter jusqu'au parent racine ---
        root = self
        while root.parent:
            root = root.parent

        result = []

        # --- 2. Descente récursive depuis la racine ---
        def dfs(project):
            if project.id in visited:
                return
            visited.add(project.id)
            result.append(project)

            # On explore tous les enfants (ordre alphabétique si besoin)
            for child in project.project_set.all().order_by("name"):
                dfs(child)

        dfs(root)

        # --- 3. Garder seulement les projets liés à self ---
        # on coupe la liste à partir de self, et on garde descendants
        if self in result:
            start_index = result.index(self)
            return result[:start_index+1] + [
                p for p in result[start_index+1:]
                if p.parent and (p.parent == self or p.parent in result[:start_index+1])
            ]
        return result


class Cycle(BaseModel):
    name = models.CharField(max_length=255)
    description = models.TextField()
    project = models.ForeignKey("Project", on_delete=models.CASCADE)
    order = models.IntegerField(default=1)
    
    administrative_levels = models.ManyToManyField(AdministrativeLevel, default=[], blank=True, verbose_name=_("Administrative Levels"), related_name="administrative_levels_cycles")

    class Meta:
        unique_together = ['project', 'order']

    def __str__(self):
        return self.name


class  SubprojectSector(BaseModel):
    name = models.CharField(max_length=255)
    name_fr = models.CharField(max_length=255)
    color = models.CharField(max_length=50)

    def __str__(self):
        return self.name
    
class SubprojectType(BaseModel):
    name = models.CharField(max_length=255)
    name_fr = models.CharField(max_length=255)
    color = models.CharField(max_length=50)
    sector = models.ForeignKey('SubprojectSector', null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return self.name


def update_step(sender, instance, **kwargs):
    if not kwargs['created']:
        for subproject_step in instance.subprojectstep_set.get_queryset():
            subproject_step.wording = instance.wording
            subproject_step.percent = instance.percent
            subproject_step.ranking = instance.ranking
            subproject_step.save()

def create_or_update_project(sender, instance, **kwargs):
    if not kwargs['created'] and instance.id:
        instance_administrative_levels = instance.administrative_levels.all()
        cycle = Cycle.objects.filter(project_id=instance.id).first()

        if not cycle and instance_administrative_levels.exists():
            cycle = Cycle.objects.create(
                name="Cycle 1",
                description=f"Cycle 1 du projet ({instance.name})",
                project_id=instance.id
            )
            cycle.administrative_levels.set(instance_administrative_levels)
            cycle.save()

        elif instance_administrative_levels.exists():
            cycles =  Cycle.objects.filter(project_id=instance.id)
            project_administrative_levels = set(instance_administrative_levels.values_list('id', flat=True))
            for cycle in cycles:
                cycle_administrative_levels = cycle.administrative_levels.all()
                common_cycle_adl_ids = []
                
                if cycle_administrative_levels:
                    cycle_administrative_levels = set(get_cascade_villages_ids_by_administrative_level_id([o.id for o in cycle_administrative_levels]))

                    # Identifier les ID présents dans le cycle mais pas dans le projet
                    common_cycle_adl_ids = project_administrative_levels & cycle_administrative_levels
                else:
                    common_cycle_adl_ids = project_administrative_levels
                
                cycle.administrative_levels.set(AdministrativeLevel.objects.filter(id__in=common_cycle_adl_ids))
                cycle.save()

        elif not instance_administrative_levels.exists():
            cycles =  Cycle.objects.filter(project_id=instance.id)
            for cycle in cycles:
                cycle.administrative_levels.set([])
                cycle.save()

        




post_save.connect(update_step, sender=Step)
post_save.connect(create_or_update_project, sender=Project)