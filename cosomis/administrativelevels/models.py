from email.policy import default
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.db.models import Q

from financial.models.bank import Bank
from cosomis.models_base import BaseModel, CustomQuerySet
from authentication.models import Facilitator

    
class AdministrativeLevel(BaseModel):
    VILLAGE = 'Village'
    CANTON = 'Canton'
    COMMUNE = 'Commune'
    PREFECTURE = 'Prefecture'
    REGION = 'Region'

    name = models.CharField(max_length=255, verbose_name=_("Name"))
    parent = models.ForeignKey('AdministrativeLevel', null=True, blank=True, on_delete=models.CASCADE, verbose_name=_("Parent"))
    geographical_unit = models.ForeignKey('GeographicalUnit', null=True, blank=True, on_delete=models.SET_NULL, verbose_name=_("Geographical unit"))
    cvd = models.ForeignKey('CVD', null=True, blank=True, on_delete=models.SET_NULL, verbose_name=_("CVD"))
    type = models.CharField(max_length=255, verbose_name=_("Type"))
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, verbose_name=_("Latitude"))
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, verbose_name=_("Longitude"))
    frontalier = models.BooleanField(default=True, verbose_name=_("Frontalier"))
    rural = models.BooleanField(default=True, verbose_name=_("Rural"))
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    no_sql_db_id = models.CharField(null=True, blank=True, max_length=255)
    
    total_tasks = models.IntegerField(default=0)
    total_tasks_completed = models.IntegerField(default=0)
    last_activity = models.DateTimeField(blank=True, null=True)

    objects = CustomQuerySet.as_manager()

    class Meta:
        unique_together = ['name', 'parent', 'type']

    def __str__(self):
        return self.name if not self.parent and "(" not in self.name else f"{self.name} ({self.parent.name})"

    def get_list_priorities(self):
        """Method to get the list of the all priorities that the administrative is linked"""
        return self.villagepriority_set.get_queryset()
    
    # def get_list_subprojects(self):
    #     """Method to get the list of the all subprojects that the administrative is linked"""
    #     return self.subproject_set.get_queryset()
    def get_list_subprojects(self):
        """Method to get the list of the all subprojects that the administrative is linked"""
        if self.cvd:
            return self.cvd.subproject_set.get_queryset().get_actifs()
        return []
    
    def get_list_subprojects_kit(self):
        """Method to get the list of the all subprojects"""
        return self.subproject_set.get_queryset().filter(subproject_type_designation="Subproject").get_actifs()
    
    # def get_facilitator(self, projects_ids, is_stabilized=True, is_technical_facilitator=False):
    #     """Anciennement : interrogeait la vue CouchDB `eadls`/_design/adl_village_filter/by_village_id
    #     pour trouver le(s) facilitateur(s) "stabilisés" (validés côté terrain) gérant ce
    #     village, en filtrant sur `representative.groups` ("CommunityFacilitator" /
    #     "TechnicalFacilitator") et `representative.is_active`.

    #     La base CouchDB `eadls` a été migrée vers Postgres côté GRM (`issue.models.Adl`), et
    #     la nouvelle API inter-services GRM (`grm_client.py`) n'expose qu'une recherche de
    #     facilitateur PAR EMAIL — pas de recherche inverse par village : impossible de
    #     reproduire directement cette requête (option "b" envisagée, écartée faute
    #     d'endpoint).

    #     Solution retenue (option "a") : MIS possède déjà, dans sa propre base MySQL, la table
    #     `AssignAdministrativeLevelToFacilitator` (via `assignadministrativeleveltofacilitator_set`)
    #     qui est la source de vérité de l'affectation facilitateur <-> village. On l'utilise donc
    #     pour retrouver le(s) facilitateur(s) "stabilisés" de ce village, en filtrant sur
    #     `Facilitator.facilitator_type` ('technical_facilitator' / 'community_facilitator',
    #     mêmes valeurs que côté CDD) pour reproduire la distinction Community/Technical
    #     qu'apportait auparavant `representative.groups`.

    #     Les appelants (`subprojects/models.py::get_facilitator`/`get_technical_facilitator`,
    #     `subprojects/templatetags/custom_tags.py::get_facilitator_with_ids`) ne lisent que
    #     `facilitator.name` / `.email` / `.phone`, déjà portés par le modèle Django
    #     `Facilitator` (base `cdd`) résolu ci-dessous : aucun aller-retour vers l'API GRM
    #     (`grm_client.get_facilitator_by_email`) n'est donc nécessaire ici, celle-ci n'apporterait
    #     que des champs (ex. `representative.photo`) qu'aucun appelant n'utilise.
    #     """
    #     wanted_facilitator_type = 'technical_facilitator' if is_technical_facilitator else 'community_facilitator'
    #     assigns = self.assignadministrativeleveltofacilitator_set.get_queryset().filter(
    #         project_id__in=projects_ids, activated=True
    #     ).order_by('-activated', '-created_date')

    #     facilitator = None
    #     if is_stabilized:
    #         for assign in assigns:
    #             candidate = assign.facilitator
    #             if candidate and candidate.is_active and candidate.facilitator_type == wanted_facilitator_type:
    #                 facilitator = candidate
    #                 break

    #     if facilitator:
    #         return facilitator
    #     elif is_technical_facilitator:
    #         return None

    #     for assign in assigns:
    #         return assign.facilitator
    #     return None
    def get_facilitator(self, projects_ids, is_stabilized=True, is_technical_facilitator=False):
        
        facilitator = None
        if is_stabilized:
            if is_technical_facilitator:
                facilitator = Facilitator.objects.using('cdd').filter(facilitator_type='technical_facilitator', active=True).filter(
                    Q(stabilization_administrative_ids__contains=[self.id])
                    #   | 
                    # Q(additional_administrative_ids__contains=[self.id])
                ).first()
            else:
                facilitator = Facilitator.objects.using('cdd').filter(facilitator_type='community_facilitator', active=True).filter(
                    Q(stabilization_administrative_ids__contains=[self.id])
                    #   | 
                    # Q(additional_administrative_ids__contains=[self.id])
                ).first()

        if facilitator:
            return facilitator
        elif is_technical_facilitator:
            return None
        
        for assign in self.assignadministrativeleveltofacilitator_set.get_queryset().filter(project_id__in=projects_ids, activated=True).order_by('-activated', '-created_date'):
            return assign.facilitator
        return None
    
    @property
    def children(self):
        return self.administrativelevel_set.get_queryset()
    
    def get_list_geographical_unit(self):
        """Method to get the list of the all Geographical Unit that the administrative is linked"""
        return self.geographicalunit_set.get_queryset()

    def get_descendants(self):
        """Récupère récursivement tous les niveaux inférieurs."""
        descendants = list(self.children.all())
        for child in self.children.all():
            descendants.extend(child.get_descendants())
        return AdministrativeLevel.objects.filter(id__in=[adl.id for adl in descendants])

    def get_ancestors(self):
        """Récupère récursivement tous les niveaux supérieurs (jusqu'à la racine)."""
        ancestors = []
        parent = self.parent
        while parent:
            ancestors.append(parent)
            parent = parent.parent
        return AdministrativeLevel.objects.filter(id__in=[adl.id for adl in ancestors])
    
    def get_administrative_hierarchy(level_id):
        """Retourne les niveaux ascendants et descendants d'un niveau donné."""
        try:
            level = AdministrativeLevel.objects.get(id=level_id)
            descendants = level.get_descendants()
            ancestors = level.get_ancestors()
            return descendants.union(ancestors, ancestors, AdministrativeLevel.objects.filter(id=level.id))
        except AdministrativeLevel.DoesNotExist:
            return []

class GeographicalUnit(BaseModel):
    canton = models.ForeignKey('AdministrativeLevel', null=True, blank=True, on_delete=models.CASCADE, verbose_name=_("Administrative level"))
    attributed_number_in_canton = models.IntegerField(verbose_name=_("Attributed number in canton"))
    unique_code = models.CharField(max_length=100, unique=True, verbose_name=_("Unique code"))
    description = models.TextField(null=True, blank=True, verbose_name=_("Description"))

    class Meta:
        unique_together = ['canton', 'attributed_number_in_canton']

    def get_name(self):
        administrativelevels = self.get_villages()
        name = ""
        count = 1
        length = len(administrativelevels)
        for adl in administrativelevels:
            name += adl.name
            if length != count:
                name += "/"
            count += 1
        return name if name else self.unique_code
    
    def get_villages(self):
        return self.administrativelevel_set.get_queryset()

    def get_cvds(self):
        return self.cvd_set.get_queryset()
    
    def __str__(self):
        return self.get_name()
    

class CVD(BaseModel):
    name = models.CharField(max_length=255, verbose_name=_("Name"))
    geographical_unit = models.ForeignKey('GeographicalUnit', on_delete=models.CASCADE, verbose_name=_("Geographical unit"))
    headquarters_village = models.ForeignKey('AdministrativeLevel', null=True, blank=True, on_delete=models.CASCADE, related_name='headquarters_village_of_the_cvd', verbose_name=_("Headquarters village"))
    attributed_number_in_canton = models.IntegerField(null=True, blank=True, verbose_name=_("Attributed number in canton"))
    unique_code = models.CharField(max_length=100, verbose_name=_("Unique code"))
    bank = models.ForeignKey(Bank, null=True, blank=True, on_delete=models.SET_NULL, verbose_name=_("Bank"))
    bank_code = models.CharField(max_length=10, verbose_name=_("Bank code"), null=True, blank=True)
    guichet_code = models.CharField(max_length=10, verbose_name=_("Guichet code"), null=True, blank=True)
    account_number = models.CharField(max_length=100, verbose_name=_("Account number"), null=True, blank=True)
    rib = models.CharField(max_length=3, verbose_name=_("RIB"), null=True, blank=True)
    president_name_of_the_cvd = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("President name of the CVD"))
    president_phone_of_the_cvd = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("President phone of the CVD"))
    treasurer_name_of_the_cvd = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("Treasurer name of the CVD"))
    treasurer_phone_of_the_cvd = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("Treasurer phone of the CVD"))
    secretary_name_of_the_cvd = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("Secretary name of the CVD"))
    secretary_phone_of_the_cvd = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("Secretary phone of the CVD"))
    description = models.TextField(null=True, blank=True, verbose_name=_("Description"))

    def get_name(self):
        administrativelevels = self.get_villages()
        if self.name:
            return self.name
        
        name = ""
        count = 1
        length = len(administrativelevels)
        for adl in administrativelevels:
            name += adl.name
            if length != count:
                name += "/"
            count += 1
        return name if name else self.unique_code
    
    def get_villages(self):
        return self.administrativelevel_set.get_queryset()
    
    def get_canton(self):
        if self.headquarters_village:
            return self.headquarters_village.parent
            
        for obj in self.get_villages():
            return obj.parent
        return None
    
    def get_list_subprojects(self):
        """Method to get the list of the all subprojects"""
        return self.subproject_set.get_queryset().get_actifs()
    
    def get_list_subprojects_kit(self):
        """Method to get the list of the all subprojects"""
        return self.subproject_set.get_queryset().filter(subproject_type_designation="Subproject").get_actifs()
    
    def __str__(self):
        return self.get_name()
    

# Anciens hooks `post_save`/`post_delete` -> CouchDB `administrative_levels` retirés : cette
# base CouchDB était un simple miroir en écriture (via `CddClient` dans `cdd_client.py`), plus
# lu par rien depuis que GRM lit désormais MIS (base `mis`) directement pour ses besoins
# d'administrative levels. `cdd_client.py` est conservé (import à faire au cas par cas) mais
# n'est plus branché automatiquement sur le cycle de vie de `AdministrativeLevel`.

