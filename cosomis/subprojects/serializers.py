from rest_framework import serializers
from subprojects.models import *
from django.db.models import Q, Case, When, Value, IntegerField
from administrativelevels.serializers import (
    AdministrativeLevelSerializer, CVDSerializer, 
	AdministrativeLevelSerializerSimple, CVDSerializerSimple
)
from usermanager.api.auth.login import CheckUserSerializer
from cosomis.serializers_base import BaseModelSerializerCustomer
from cosomis.__init__ import FORM_FIELDS_TO_EXCLUDE, FORM_FIELDS_TO_EXCLUDE_WITH_EXTERNAL_ID
from cosomis.constants import STRUCTURE_COMPLETED_ALL_STATUS, STRUCTURE_IN_PROGRESS_ALL_STATUS
from usermanager.serializers import UserSerializer


class SubprojectFileSerializer(BaseModelSerializerCustomer):
	class Meta:
		"""docstring for Meta"""
		model = SubprojectFile
		# fields = '__all__'
		exclude = FORM_FIELDS_TO_EXCLUDE #[elt for elt in FORM_FIELDS_TO_EXCLUDE if elt != 'create_by_user']
  
	def to_representation(self, instance):
		data = super().to_representation(instance)
		if instance.description:
			data['description'] = instance.description
		elif instance.subproject_step:
			data['description'] = instance.subproject_step.description
		elif instance.subproject_level:
			if instance.subproject_level.description:
				data['description'] = instance.subproject_level.description
			else:
				data['description'] = instance.subproject_level.subproject_step.description
		else:
			data['description'] = None

		data['comments_count'] = instance.comments.count()

		return data
  

class SubprojectFileSerializerSimple(BaseModelSerializerCustomer):
	class Meta:
		"""docstring for Meta"""
		model = SubprojectFile
		fields = ['id', 'url', 'name', 'date_taken', 'order', 'principal', 'special', 'description', 'validated']
  
	def to_representation(self, instance):
		data = super().to_representation(instance)
		if instance.description:
			data['description'] = instance.description
		elif instance.subproject_step:
			data['description'] = instance.subproject_step.description
			data['subproject_step'] = instance.subproject_step.wording
		elif instance.subproject_level:
			if instance.subproject_level.description:
				data['description'] = instance.subproject_level.description
			else:
				data['description'] = instance.subproject_level.subproject_step.description
		else:
			data['description'] = None

		if 'subproject_step' not in data and instance.subproject_step:
			data['subproject_step'] = instance.subproject_step.wording
		elif (
			"kobotoolbox" in str(instance.url).lower() and 
			any(
				elt for elt in list(
					set((instance.name if instance.name else "").split(" ")+(instance.description if instance.description else "").split(" "))
				) if elt.lower() in [o.lower() for o in STRUCTURE_IN_PROGRESS_ALL_STATUS]
			)
		):
			data['subproject_step'] = "En cours"
		elif (
			"kobotoolbox" in str(instance.url).lower() and 
			any(
				elt for elt in list(
					set((instance.name if instance.name else "").split(" ")+(instance.description if instance.description else "").split(" "))
				) if elt.lower() in [o.lower() for o in STRUCTURE_COMPLETED_ALL_STATUS]
			)
		):
			data['subproject_step'] = "Achevé"

		return data
	

class ComponentSerializer(BaseModelSerializerCustomer):
	class Meta:
		"""docstring for Meta"""
		model = Component
		# fields = '__all__'
		exclude = FORM_FIELDS_TO_EXCLUDE_WITH_EXTERNAL_ID

class FinancierSerializer(BaseModelSerializerCustomer):
	class Meta:
		"""docstring for Meta"""
		model = Financier
		# fields = '__all__'
		exclude = FORM_FIELDS_TO_EXCLUDE


class ProjectSerializer(BaseModelSerializerCustomer):
	financiers = FinancierSerializer(many=True)
	class Meta:
		"""docstring for Meta"""
		model = Project
		# fields = '__all__'
		exclude = FORM_FIELDS_TO_EXCLUDE_WITH_EXTERNAL_ID

class ProjectSerializerSimple(BaseModelSerializerCustomer):
	financiers = FinancierSerializer(many=True)
	class Meta:
		"""docstring for Meta"""
		model = Project
		fields = ['id', 'name', 'financiers']


class VillagePrioritySerializer(BaseModelSerializerCustomer):
	class Meta:
		"""docstring for Meta"""
		model = VillagePriority
		# fields = '__all__'
		exclude = FORM_FIELDS_TO_EXCLUDE

class VillagePrioritySerializerSimple(BaseModelSerializerCustomer):
	class Meta:
		"""docstring for Meta"""
		model = VillagePriority
		fields = ['id', 'name', 'ranking']

class StepSerializer(BaseModelSerializerCustomer):

	def __init__(self, *args, **kwargs):
		self.depth = kwargs.pop('depth', 0)
		super().__init__(*args, **kwargs)

	class Meta:
		"""docstring for Meta"""
		model = Step
		# fields = '__all__'
		exclude = FORM_FIELDS_TO_EXCLUDE
	
	def to_representation(self, instance, *args, **kwargs):
		data = super().to_representation(instance)
		
		if self.depth < 1:
			data['next_steps'] = StepSerializer(
				instance.next_steps.all(),
				many=True,
				depth=self.depth + 1
			).data
		
		return data


class LevelSerializer(BaseModelSerializerCustomer):
	class Meta:
		"""docstring for Meta"""
		model = Level
		# fields = '__all__'
		exclude = FORM_FIELDS_TO_EXCLUDE
		ordering = ['-begin', '-ranking', '-created_date']

	def to_representation(self, instance):
		data = super().to_representation(instance)
		
		files = instance.photos if hasattr(instance, "photos") else instance.get_files().annotate(
			validated_order=Case(
				When(validated=False, then=Value(1)),
				When(validated=True, then=Value(2)),
				When(validated=None, then=Value(3)),
				default=Value(4),
				output_field=IntegerField(),
			)
		).order_by("validated_order", "-updated_date")
		data['files'] = SubprojectFileSerializer(files, many=True).data
		try:
			data['files_invalidated_count'] = files.filter(validated=False).count()
		except:
			pass

		return data

class SubprojectStepSerializer(BaseModelSerializerCustomer):
	class Meta:
		"""docstring for Meta"""
		model = SubprojectStep
		# fields = '__all__'
		exclude = FORM_FIELDS_TO_EXCLUDE
		ordering = ['-begin', '-created_date', '-ranking']

	def to_representation(self, instance):
		data = super().to_representation(instance)
		
		data['levels'] = LevelSerializer(instance.get_levels(), many=True).data
		files = instance.photos if hasattr(instance, "photos") else instance.get_files().annotate(
			validated_order=Case(
				When(validated=False, then=Value(1)),
				When(validated=True, then=Value(2)),
				When(validated=None, then=Value(3)),
				default=Value(4),
				output_field=IntegerField(),
			)
		).order_by("validated_order", "-updated_date")
		data['files'] = SubprojectFileSerializer(files, many=True).data
		try:
			data['files_invalidated_count'] = files.filter(validated=False).count()
		except:
			pass
			
		return data



class SubprojectSerializer(BaseModelSerializerCustomer):
	location_subproject_realized = AdministrativeLevelSerializer(many=False)
	list_of_villages_crossed_by_the_track_or_electrification = AdministrativeLevelSerializer(many=True)
	cvd = CVDSerializer(many=False)
	canton = AdministrativeLevelSerializer(many=False, )
	component = ComponentSerializer(many=False)
	priorities = VillagePrioritySerializer(many=True)
	projects = ProjectSerializer(many=True)
	financiers = FinancierSerializer(many=True)
	class Meta:
		"""docstring for Meta"""
		model = Subproject
		# fields = '__all__'
		exclude = FORM_FIELDS_TO_EXCLUDE

	def to_representation(self, instance):
		data = super().to_representation(instance)
			
		data['current_subproject_step_and_level'] = instance.get_current_subproject_step_and_level
		files = instance.photos if hasattr(instance, "photos") else instance.get_files().annotate(
			validated_order=Case(
				When(validated=False, then=Value(1)),
				When(validated=True, then=Value(2)),
				When(validated=None, then=Value(3)),
				default=Value(4),
				output_field=IntegerField(),
			)
		).order_by("validated_order", "-updated_date")
		data['files'] = SubprojectFileSerializer(files, many=True).data
		try:
			data['files_invalidated_count'] = files.filter(validated=False).count()
		except:
			pass

		return data
	
class SubprojectSerializerSimple(BaseModelSerializerCustomer):
	location_subproject_realized = AdministrativeLevelSerializerSimple(many=False)
	list_of_villages_crossed_by_the_track_or_electrification = AdministrativeLevelSerializerSimple(many=True)
	cvd = CVDSerializerSimple(many=False)
	canton = AdministrativeLevelSerializerSimple(many=False, )
	component = ComponentSerializer(many=False)
	priorities = VillagePrioritySerializerSimple(many=True)
	projects = ProjectSerializerSimple(many=True)
	financiers = FinancierSerializer(many=True)
	class Meta:
		"""docstring for Meta"""
		model = Subproject
		# fields = '__all__'
		exclude = FORM_FIELDS_TO_EXCLUDE
	def to_representation(self, instance):
		data = super().to_representation(instance)
			
		data['current_subproject_step_and_level'] = instance.get_current_subproject_step_and_level
		files = instance.photos if hasattr(instance, "photos") else instance.get_files().annotate(
			validated_order=Case(
				When(validated=False, then=Value(1)),
				When(validated=True, then=Value(2)),
				When(validated=None, then=Value(3)),
				default=Value(4),
				output_field=IntegerField(),
			)
		).order_by("validated_order", "-updated_date")
		data['files'] = SubprojectFileSerializerSimple(files, many=True).data
		try:
			data['files_invalidated_count'] = files.filter(validated=False).count()
		except:
			pass

		return data

class SubprojectStandardSerializer(BaseModelSerializerCustomer):
	class Meta:
		"""docstring for Meta"""
		model = Subproject
		# fields = '__all__'
		exclude = FORM_FIELDS_TO_EXCLUDE
	

class SubprojectWithParentLinkSerializer(SubprojectSerializer):

	def to_representation(self, instance):
		data = super().to_representation(instance)
		if instance.link_to_subproject:
			data['link_to_subproject'] = SubprojectSerializer(instance.link_to_subproject).data
			
		return data

class SubprojectWithChildrenLinkedSerializer(SubprojectSerializer):

	def to_representation(self, instance):
		data = super().to_representation(instance)
		
		all_subprojects_linked = instance.get_all_subprojects_linked()
		if all_subprojects_linked:
			data['subprojects_linked'] = SubprojectSerializer(all_subprojects_linked, many=True).data

		return data

class SubprojectWithChildrenLinkedSerializerSimple(SubprojectSerializerSimple):
	priorities = None
	class Meta:
		"""docstring for Meta"""
		model = Subproject
		# fields = '__all__'
		exclude = FORM_FIELDS_TO_EXCLUDE + ['priorities', 'priority']
	# def to_representation(self, instance):
	# 	data = super().to_representation(instance)
	
	# 	all_subprojects_linked = instance.get_all_subprojects_linked()
	# 	if all_subprojects_linked:
	# 		data['subprojects_linked'] = SubprojectSerializerSimple(all_subprojects_linked, many=True).data

	# 	return data

class SubprojectWithChildrenLinkedSerializerSimpleWithPriorities(SubprojectSerializerSimple):
	pass
	
class SaveSubprojectSerializer(SubprojectStandardSerializer, CheckUserSerializer):
	pass



class FileCommentsSerializer(BaseModelSerializerCustomer):
	file = SubprojectFileSerializer(many=False)
	user = UserSerializer(many=False)
	
	class Meta:
		"""docstring for Meta"""
		model = FileComment
		exclude = FORM_FIELDS_TO_EXCLUDE
