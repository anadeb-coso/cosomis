from rest_framework import serializers

from administrativelevels.models import *
from administrativelevels.functions_adl import get_cascade_villages_ids_by_administrative_level_id
from cosomis.serializers_base import SharedRepresentationMixin, shared_representation


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


class CVDSerializer(SharedRepresentationMixin, serializers.ModelSerializer):
	geographical_unit = GeographicalUnitSerializer(many=False)
	
	class Meta:
		"""docstring for Meta"""
		model = CVD
		fields = '__all__'

class CVDSerializerSimple(SharedRepresentationMixin, serializers.ModelSerializer):
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
	_zone_counts = None

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
		if not self.user:
			# sans compteurs (parents, villages d'un CVD, sites des sous-projets) : la même dans toute la réponse
			return shared_representation(self, instance, lambda: self._representation_with_parent(instance))

		data = self._representation_with_parent(instance)
		# number_subprojects, number_infrastructures, number_subproject_files, files_invalidated_count : sous-projets
		# de la zone de l'utilisateur sur ce niveau (site, parent du site ou canton)
		data.update(self.zone_counts().for_administrative_level(instance.id))
		return data

	def _representation_with_parent(self, instance):
		data = super().to_representation(instance)
		if instance.parent:
			data['parent'] = AdministrativeLevelSerializer(instance.parent).data
		return data

	def zone_counts(self):
		"""Sous-projets de la zone de l'utilisateur, lus une fois pour toute la liste (voir ZoneSubprojectCounts)."""
		from subprojects.api.prefetch import ZoneSubprojectCounts
		if self._zone_counts is None:
			self._zone_counts = ZoneSubprojectCounts(self.user, self.project_id)
		return self._zone_counts


class AdministrativeLevelSerializerSimple(serializers.ModelSerializer):
	geographical_unit = GeographicalUnitSerializerSimple(many=False)
	cvd = CVDSerializerSimple(many=False)

	user = None
	project_id = None
	_zone_counts = None

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
		if not self.user:
			# sans compteurs : la même dans toute la réponse
			return shared_representation(self, instance, lambda: self._representation_with_parent(instance))

		data = self._representation_with_parent(instance)
		# number_subprojects, number_infrastructures : sous-projets de la zone de l'utilisateur sur ce niveau
		data.update(self.zone_counts().for_administrative_level(instance.id, with_files=False))
		return data

	def _representation_with_parent(self, instance):
		data = super().to_representation(instance)
		if instance.parent:
			data['parent'] = AdministrativeLevelSerializerSimple(instance.parent).data
		return data

	def zone_counts(self):
		from subprojects.api.prefetch import ZoneSubprojectCounts
		if self._zone_counts is None:
			self._zone_counts = ZoneSubprojectCounts(self.user, self.project_id)
		return self._zone_counts
	

class CVDWithAdministrativeLevelSerializer(serializers.ModelSerializer):
	geographical_unit = GeographicalUnitSerializer(many=False)
	administrativelevels = AdministrativeLevelSerializer(source='administrativelevel_set', many=True) 
	
	user = None
	project_id = None
	_zone_counts = None

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
			# number_subprojects, number_infrastructures, number_subproject_files, files_invalidated_count : sous-projets
			# de la zone de l'utilisateur rattachés à ce CVD
			if self._zone_counts is None:
				from subprojects.api.prefetch import ZoneSubprojectCounts
				self._zone_counts = ZoneSubprojectCounts(self.user, self.project_id)
			data.update(self._zone_counts.for_cvd(instance.id))

		return data