from rest_framework import serializers
from django.db.models import Q

from administrativelevels.models import *
from administrativelevels.functions_adl import get_cascade_villages_ids_by_administrative_level_id
from assignments.functions import get_subprojects_by_facilitator_id_and_project_id
from subprojects.models import Subproject, SubprojectFile


class GeographicalUnitSerializer(serializers.ModelSerializer):
	class Meta:
		"""docstring for Meta"""
		model = GeographicalUnit
		fields = '__all__'

class GeographicalUnitSerializerSimple(serializers.ModelSerializer):
	class Meta:
		"""docstring for Meta"""
		model = GeographicalUnit
		fields = ['id', 'unique_code', 'attributed_number_in_canton']


class CVDSerializer(serializers.ModelSerializer):
	geographical_unit = GeographicalUnitSerializer(many=False)
	
	class Meta:
		"""docstring for Meta"""
		model = CVD
		fields = '__all__'

class CVDSerializerSimple(serializers.ModelSerializer):
	geographical_unit = GeographicalUnitSerializerSimple(many=False)
	
	class Meta:
		"""docstring for Meta"""
		model = CVD
		fields = ['id', 'name', 'geographical_unit']


class SimpleAdministrativeLevelSerializer(serializers.ModelSerializer):

	class Meta:
		"""docstring for Meta"""
		model = AdministrativeLevel
		fields = '__all__'


class AdministrativeLevelSerializer(serializers.ModelSerializer):
	geographical_unit = GeographicalUnitSerializer(many=False)
	cvd = CVDSerializer(many=False)

	user = None
	project_id = None

	def __init__(self, *args, **kwargs):
		super(AdministrativeLevelSerializer, self).__init__(*args, **kwargs)
		initial = kwargs.get('initial')
		if initial:
			self.user = initial.get('user')
			self.project_id = initial.get('project_id')

	class Meta:
		"""docstring for Meta"""
		model = AdministrativeLevel
		fields = '__all__'

	def to_representation(self, instance, *args, **kwargs):
		data = super().to_representation(instance)
		if instance.parent:
			data['parent'] = AdministrativeLevelSerializer(instance.parent).data
		
		if self.user:

			if not hasattr(self.user, 'no_sql_user'):
				subprojects = Subproject.objects.filter(projects__in=[self.project_id]).get_actifs()
			else:
				subprojects = get_subprojects_by_facilitator_id_and_project_id(self.user.id, self.project_id)
				
			data['number_subprojects'] = subprojects.filter(
                Q(link_to_subproject=None, location_subproject_realized__id=instance.id) | 
                Q(link_to_subproject=None, location_subproject_realized__parent__id=instance.id) | 
                Q(link_to_subproject=None, canton__id=instance.id)
            ).count()

			infrastructures = subprojects.filter(
                Q(location_subproject_realized__id=instance.id) | 
                Q(location_subproject_realized__parent__id=instance.id) | 
                Q(canton__id=instance.id)
            )
			data['number_infrastructures'] = infrastructures.count()

			files = SubprojectFile.objects.filter(subproject__in=infrastructures)
			data['number_subproject_files'] = files.count()
			data['files_invalidated_count'] = files.filter(validated=False).count()

		return data


class AdministrativeLevelSerializerSimple(serializers.ModelSerializer):
	geographical_unit = GeographicalUnitSerializerSimple(many=False)
	cvd = CVDSerializerSimple(many=False)

	user = None
	project_id = None

	def __init__(self, *args, **kwargs):
		super(AdministrativeLevelSerializerSimple, self).__init__(*args, **kwargs)
		initial = kwargs.get('initial')
		if initial:
			self.user = initial.get('user')
			self.project_id = initial.get('project_id')

	class Meta:
		"""docstring for Meta"""
		model = AdministrativeLevel
		fields = ['id', 'name', 'geographical_unit', 'cvd', 'parent', 'latitude', 'longitude']

	def to_representation(self, instance, *args, **kwargs):
		data = super().to_representation(instance)
		if instance.parent:
			data['parent'] = AdministrativeLevelSerializerSimple(instance.parent).data
		
		if self.user:

			if not hasattr(self.user, 'no_sql_user'):
				subprojects = Subproject.objects.filter(projects__in=[self.project_id]).get_actifs()
			else:
				subprojects = get_subprojects_by_facilitator_id_and_project_id(self.user.id, self.project_id)
				
			data['number_subprojects'] = subprojects.filter(
                Q(link_to_subproject=None, location_subproject_realized__id=instance.id) | 
                Q(link_to_subproject=None, location_subproject_realized__parent__id=instance.id) | 
                Q(link_to_subproject=None, canton__id=instance.id)
            ).count()
			data['number_infrastructures'] = subprojects.filter(
                Q(location_subproject_realized__id=instance.id) | 
                Q(location_subproject_realized__parent__id=instance.id) | 
                Q(canton__id=instance.id)
            ).count()


		return data
	

class CVDWithAdministrativeLevelSerializer(serializers.ModelSerializer):
	geographical_unit = GeographicalUnitSerializer(many=False)
	administrativelevels = AdministrativeLevelSerializer(source='administrativelevel_set', many=True) 
	
	user = None
	project_id = None

	def __init__(self, *args, **kwargs):
		super(CVDWithAdministrativeLevelSerializer, self).__init__(*args, **kwargs)
		initial = kwargs.get('initial')
		if initial:
			self.user = initial.get('user')
			self.project_id = initial.get('project_id')

	class Meta:
		"""docstring for Meta"""
		model = CVD
		fields = '__all__'
		extra_kwargs = {'administrativelevels': {'read_only': True}}

	def to_representation(self, instance, *args, **kwargs):
		data = super().to_representation(instance)

		if self.user:

			if not hasattr(self.user, 'no_sql_user'):
				subprojects = Subproject.objects.filter(projects__in=[self.project_id]).get_actifs()
			else:
				subprojects = get_subprojects_by_facilitator_id_and_project_id(self.user.id, self.project_id)
				
			data['number_subprojects'] = subprojects.filter(
                Q(link_to_subproject=None, cvd__id=instance.id)
            ).count()

			infrastructures = subprojects.filter(
                Q(cvd__id=instance.id)
            )
			data['number_infrastructures'] = infrastructures.count()

			files = SubprojectFile.objects.filter(subproject__in=infrastructures)
			data['number_subproject_files'] = files.count()
			data['files_invalidated_count'] = files.filter(validated=False).count()

		return data