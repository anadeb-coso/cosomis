from email.policy import default
from django.db import models
import locale
from django.utils.translation import gettext_lazy as _
from django.db.models.signals import post_save
from typing import TypeVar, Any
from django.db.models import Q

from administrativelevels.models import AdministrativeLevel, CVD
from subprojects import SUB_PROJECT_TYPE_DESIGNATION, SUB_PROJECT_SECTORS, TYPES_OF_SUB_PROJECT
from cosomis.customers_fields import *
from cosomis.types import _QS
from cosomis.models_base import BaseModel


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




# Create your models here.
class Subproject(BaseModel):
    location_subproject_realized = models.ForeignKey(AdministrativeLevel, null=True, blank=True, on_delete=models.CASCADE, related_name='location_subproject_realized', verbose_name=_("Subproject location"))
    cvd = models.ForeignKey(CVD, null=True, blank=True, on_delete=models.CASCADE, verbose_name=_("CVD"))
    # cvds = models.ManyToManyField(CVD, default=[], blank=True, related_name="cvds_subprojects", verbose_name=_("Beneficiaries CVD"))
    list_of_beneficiary_villages = models.ManyToManyField(AdministrativeLevel, default=[], blank=True, related_name="vilages_subprojects", verbose_name=_("Beneficiaries villages"))
    canton = models.ForeignKey(AdministrativeLevel, null=True, blank=True, on_delete=models.CASCADE, verbose_name=_("Canton")) #canton subprojects (rural track)
    list_of_villages_crossed_by_the_track_or_electrification = models.ManyToManyField(AdministrativeLevel, default=[], blank=True, related_name="cantonal_subprojects", verbose_name=_("List of villages where the runway or electrification crosses"))
    link_to_subproject = models.ForeignKey('Subproject', null=True, blank=True, on_delete=models.CASCADE, verbose_name=_("Linked to a sub-project")) #To link the subprojects that the cantons or CVD link to make
    
    number = models.IntegerField(null=True, blank=True, verbose_name=_("Number unique to each sub-project or infrastructure"))
    joint_subproject_number = models.IntegerField(null=True, blank=True, verbose_name=_("Subproject kit number"))
    intervention_unit = models.IntegerField(null=True, blank=True, verbose_name=_("Intervention unit"))
    facilitator_name = models.CharField(max_length=255, null=True, blank=True, verbose_name=_("Facilitator name"))
    wave = models.CharField(max_length=4, null=True, blank=True, verbose_name=_("Arbitrage wave"))
    lot = models.CharField(max_length=4, null=True, blank=True, verbose_name=_("Lot"))
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
    length_of_the_track = models.FloatField(null=True, blank=True, verbose_name=_("Length of track (km)"))
    depth_of_drilling = models.FloatField(null=True, blank=True, verbose_name=_("Borehole depth (m)"))
    drilling_flow_rate = models.FloatField(null=True, blank=True, verbose_name=_("Borehole flow (m3)"))
    current_status_of_the_site = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("Current site status (Work in progress, Work stopped, Work abandoned, Technical acceptance, Provisional acceptance, etc.)"))
    expected_duration_of_the_work = models.FloatField(null=True, blank=True, verbose_name=_("Estimated completion time (months)"))
    expected_end_date_of_the_contract = models.DateField(null=True, blank=True, verbose_name=_("Expected contract end date"))
    total_contract_amount_paid = models.FloatField(null=True, blank=True, verbose_name=_("Total amount of the pay contract (technical inspection + safeguard inspection + construction company + furniture company + facilitator)"))
    amount_of_the_care_and_maintenance_fund_expected_to_be_mobilized = models.FloatField(null=True, blank=True, verbose_name=_("Upkeep and maintenance fund (EMI) to be mobilized"))
    care_and_maintenance_amount_on_village_account = models.FloatField(null=True, blank=True, verbose_name=_("Amount of maintenance fund (EMI) mobilized and deposited in village account"))
    existence_of_maintenance_and_upkeep_plan_developed_by_community = models.BooleanField(default=False, verbose_name=_("Existence of a maintenance and upkeep plan (EMI plan) drawn up by the community (if yes, put 1; if no, put 0)"))
    date_of_technical_acceptance_of_work_contracts = models.DateField(null=True, blank=True, verbose_name=_("Dates for technical acceptance of work contracts (BTP or FORAGE)"))
    technical_acceptance_date_for_efme_contracts = models.DateField(null=True, blank=True, verbose_name=_("Technical acceptance dates for furniture and equipment supply contracts"))
    date_of_provisional_acceptance_of_work_contracts = models.DateField(null=True, blank=True, verbose_name=_("Dates of provisional acceptance of work contracts (BTP or FORAGE)"))
    provisional_acceptance_date_for_efme_contracts = models.DateField(null=True, blank=True, verbose_name=_("Provisional acceptance dates for furniture and equipment supply contracts"))
    official_handover_date_of_the_microproject_to_the_community = models.DateField(null=True, blank=True, verbose_name=_("Date of official handover of the microproject to the community"))
    official_handover_date_of_the_microproject_to_the_sector = models.DateField(null=True, blank=True, verbose_name=_("Date of official handover of the microproject to the sector"))
    comments = models.TextField(null=True, blank=True, verbose_name=_("Comments"))
    
    target_female_beneficiaries = models.IntegerField(null=True, blank=True, verbose_name=_("Target female beneficiaries"))
    target_male_beneficiaries = models.IntegerField(null=True, blank=True, verbose_name=_("Target male beneficiaries"))
    target_youth_beneficiaries = models.IntegerField(null=True, blank=True, verbose_name=_("Target youth beneficiaries"))

    population = models.IntegerField(null=True, blank=True, verbose_name=_("Population"))
    direct_beneficiaries_men = models.IntegerField(null=True, blank=True, verbose_name=_("Direct beneficiaries men"))
    direct_beneficiaries_women = models.IntegerField(null=True, blank=True, verbose_name=_("Direct beneficiaries women"))
    indirect_beneficiaries_men = models.IntegerField(null=True, blank=True, verbose_name=_("Indirect beneficiaries men"))
    indirect_beneficiaries_women = models.IntegerField(null=True, blank=True, verbose_name=_("Indirect beneficiaries women"))

    component = models.ForeignKey('Component', null=True, on_delete=models.CASCADE, verbose_name=_("Component (Subcomponent)"))
    priorities = models.ManyToManyField('VillagePriority', default=[], blank=True, related_name='priorities_covered', verbose_name=_("Priorities"))

    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, verbose_name=_("Latitude"))
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, verbose_name=_("Longitude"))

    projects = models.ManyToManyField('Project', default=[], blank=True, verbose_name=_("Projects")) #In Which projects that we finance the subproject
    financiers = models.ManyToManyField('Financier', default=[], blank=True, verbose_name=_("Financiers")) #Which Financiers finance this subproject (when its project is define, we don't need to specialize this attribute)

    #Whose choice this subproject?
    women_s_group = models.BooleanField(null=True, blank=True, verbose_name=_("Women's group"))
    youth_group = models.BooleanField(null=True, blank=True, verbose_name=_("Youth group"))
    breeders_farmers_group = models.BooleanField(null=True, blank=True, verbose_name=_("Breeders farmers group"))
    ethnic_minority_group = models.BooleanField(null=True, blank=True, verbose_name=_("Ethnic minority group"))

    has_latrine_blocs = models.BooleanField(null=True, blank=True, verbose_name=_("Latrine blocks?"))
    number_of_latrine_blocks = models.IntegerField(null=True, blank=True, verbose_name=_("Number of latrine blocks"))
    number_of_classrooms = models.IntegerField(null=True, blank=True, verbose_name=_("Number of classrooms"))
    has_fence = models.BooleanField(null=True, blank=True, verbose_name=_("Has a fence?"))
    
    objects = CustomQuerySet.as_manager()


    class Meta:
        unique_together = [
            # [
            #     'full_title_of_approved_subproject', 'location_subproject_realized', 
            #     'subproject_sector', 'type_of_subproject'
            # ], 
            # ['canton', 'full_title_of_approved_subproject'],
            # ['number']
        ]

        

    def get_cantons_names(self):
        if self.location_subproject_realized:
            return self.location_subproject_realized.parent.name
        elif self.canton: 
            cantons = self.canton.name
            subprojects_link_objects = self.subproject_set.get_queryset()
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

    def get_all_subprojects_linked(self):
        return self.subproject_set.get_queryset()
    
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
        estimated_cost = self.estimated_cost
        for o in self.subproject_set.get_queryset():
            estimated_cost += o.estimated_cost
        return estimated_cost

    def get_estimated_cost_str(self):
        locale.setlocale( locale.LC_ALL, '' )
        estimated_cost_str = ""
        estimated_cost_str += locale.currency(self.estimated_cost, grouping=True).__str__()
        subproject_link_objects = self.subproject_set.get_queryset()
        if subproject_link_objects:
            for o in self.subproject_set.get_queryset():
                estimated_cost_str += " + " + locale.currency(o.estimated_cost, grouping=True).__str__()
            return (locale.currency(self.get_estimated_cost(), grouping=True).__str__() + f' ({estimated_cost_str})').replace("$", "")
        
        return estimated_cost_str.replace("$", "")

    def get_files(self):
        return self.subprojectfile_set.get_queryset().filter().order_by("-date_taken")
    
    def get_all_images(self, order=False):
        if order:
            return sorted(self.subprojectfile_set.get_queryset().filter(file_type__icontains="image"), key=lambda o: o.order)
        return self.subprojectfile_set.get_queryset().filter(file_type__icontains="image")

    def get_all_exclude_images(self, order=False):
        if order:
            return sorted(self.subprojectfile_set.get_queryset().exclude(file_type__icontains="image"), key=lambda o: o.order)
        return self.subprojectfile_set.get_queryset().exclude(file_type__icontains="image")
    
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
    def get_facilitator_name(self):
        if self.facilitator_name:
            return self.facilitator_name
        elif self.cvd and self.cvd.headquarters_village:
            f = self.cvd.headquarters_village.get_facilitator(self.get_projects_ids())
            return f.name if f else None
        return None
    
    def get_subproject_steps(self, order=True):
        if order:
            return self.subprojectstep_set.get_queryset().order_by("-begin", "-ranking")
            #sorted(self.subprojectstep_set.get_queryset(), key=lambda o: o.begin, reverse=True) #self.subprojectstep_set.get_queryset().order_by("-ranking") #
        return self.subprojectstep_set.get_queryset()
    
    @property
    def get_current_subproject_step(self):
        return self.get_subproject_steps().first()
    
    @property
    def get_current_subproject_step_and_level(self):
        step = self.get_current_subproject_step
        if step and step.wording == "En cours":
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
        if step and step.wording == "En cours":
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
                return _("In progress") + f" {_status}%"
            elif _status >= 100:
                return _("Completed") + f" {_status}%"

        return None

    @property
    def get_current_subproject_step_and_level_object(self):
        step = self.get_current_subproject_step
        if step and step.wording == "En cours":
            level = step.get_levels().first()
            if level:
                return level
        if step:
            return step
        return None
    
    def check_step(self, step):
        for s in self.subprojectstep_set.get_queryset():
            if s.wording == step.wording:
                return True
        return False

    def __str__(self):
        return self.full_title_of_approved_subproject

class _Step(BaseModel):
    wording = models.CharField(max_length=200, verbose_name=_("Wording"))
    percent = CustomerFloatRangeField(null=True, blank=True, verbose_name=_("Percent"), min_value=0, max_value=100)
    description = models.TextField(null=True, blank=True, verbose_name=_("Description"))
    ranking = models.IntegerField(default=0, verbose_name=_("Ranking"))
    amount_spent_at_this_step = models.FloatField(null=True, blank=True, verbose_name=_("Amount spent at this stage"))
    total_amount_spent = models.FloatField(null=True, blank=True, verbose_name=_("Total amount spent"))

    class Meta:
        abstract = True

    def __str__(self):
        return f'{self.wording}' + (' '+str(self.percent)+'%' if self.percent else '')
    
class Step(_Step):
    has_levels = models.BooleanField(default=False, verbose_name=_("Has levels"))
    
    class Meta:
        unique_together = ['ranking']


class SubprojectStep(_Step):
    subproject = models.ForeignKey(Subproject, on_delete=models.CASCADE, verbose_name=_("Subproject"))
    step = models.ForeignKey(Step, on_delete=models.CASCADE, verbose_name=_("Step"))
    begin = models.DateField(verbose_name=_("Begin"))
    end = models.DateField(null=True, blank=True, verbose_name=_("End"))
    
    def get_levels(self, order=True):
        if order:
            return self.level_set.get_queryset().order_by("-begin", "-ranking", "-id")
            #sorted(self.level_set.get_queryset(), key=lambda o: o.begin, reverse=True)
        return self.level_set.get_queryset()
    
    def check_step(self, wording):
        for l in self.level_set.get_queryset():
            if l.wording == wording:
                return True
        return False
    
    def get_files(self):
        if self.wording == "En cours":
            return SubprojectFile.objects.filter(
                Q(subproject_level__subproject_step__id=self.id) | Q(subproject_step__id=self.id)
            ).order_by("-date_taken")
        return self.subprojectfile_set.get_queryset().filter().order_by("-date_taken")
    
    def get_images(self):
        if self.wording == "En cours":
            return SubprojectFile.objects.filter(
                Q(subproject_level__subproject_step__id=self.id) | Q(subproject_step__id=self.id),
                file_type__icontains="image"
            ).order_by("-date_taken")
        return self.subprojectfile_set.get_queryset().filter(file_type__icontains="image").order_by("-date_taken")

    def get_exclude_images(self):
        if self.wording == "En cours":
            return SubprojectFile.objects.filter(
                Q(subproject_level__subproject_step__id=self.id) | Q(subproject_step__id=self.id)
            ).exclude(
                file_type__icontains="image"
            ).order_by("-date_taken")
        return self.subprojectfile_set.get_queryset().exclude(file_type__icontains="image").order_by("-date_taken")
    
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
        return self.subprojectfile_set.get_queryset().filter(file_type__icontains="image").order_by("-date_taken")

    def get_exclude_images(self):
        return self.subprojectfile_set.get_queryset().exclude(file_type__icontains="image").order_by("-date_taken")
    
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
    date_taken = models.DateField()
    file_type = models.CharField(max_length=100, default="image")



class Financier(BaseModel):
    name = models.CharField(max_length=255)
    description = models.TextField()

    def __str__(self):
        return self.name
    

class Project(BaseModel):
    name = models.CharField(max_length=255)
    description = models.TextField()
    financier = models.ForeignKey('Financier', null=True, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


def update_step(sender, instance, **kwargs):
    if not kwargs['created']:
        for subproject_step in instance.subprojectstep_set.get_queryset():
            subproject_step.wording = instance.wording
            subproject_step.percent = instance.percent
            subproject_step.ranking = instance.ranking
            subproject_step.save()

post_save.connect(update_step, sender=Step)