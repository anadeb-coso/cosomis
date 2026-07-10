from email.policy import default
from django.db import models
from cdd_client import CddClient
from django.db.models.signals import post_save, post_delete
from django.utils.translation import gettext_lazy as _

from financial.models.bank import Bank
from cosomis.models_base import BaseModel, CustomQuerySet
from no_sql_client import NoSQLClient
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
    
    def get_facilitator(self, projects_ids, is_stabilized=True, is_technical_facilitator=False):
        facilitator = None
        if is_stabilized:
            nsc = NoSQLClient()
            eadls = nsc.get_db('eadls')
            facilitators_stabilized = eadls.get_view_result(
                "_design/adl_village_filter", "by_village_id", 
                keys=[self.id], 
                include_docs=True
            )
            if facilitators_stabilized:
                for elt in [row["doc"] for row in facilitators_stabilized[:] if any(g for g in (["TechnicalFacilitator"] if is_technical_facilitator else ["CommunityFacilitator"]) if g in row["doc"]["representative"]["groups"]) and row["doc"]["representative"]["is_active"] == True]:
                    facilitator = Facilitator.objects.using('cdd').filter(email=elt["representative"]["email"]).first()
        
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
    

def update_or_create_amd_couch(sender, instance, **kwargs):
    print("test", instance.id, kwargs['created'])
    client = CddClient()
    if kwargs['created']:
        couch_object_id = client.create_administrative_level(instance)
        to_update = AdministrativeLevel.objects.filter(id=instance.id)
        to_update.update(no_sql_db_id=couch_object_id)
    else:
        client.update_administrative_level(instance)

def delete_amd_couch(sender, instance, **kwargs):
    client = CddClient()
    client.delete_administrative_level(instance)



post_save.connect(update_or_create_amd_couch, sender=AdministrativeLevel)
post_delete.connect(delete_amd_couch, sender=AdministrativeLevel) # POST-DELETE method to delete the administrativelevel in the couchdb

