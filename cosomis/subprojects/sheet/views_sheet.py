from cosomis import FORM_FIELDS_TO_EXCLUDE, TABLE_SHEET_FIELDS_TO_EXCLUDE

from rest_framework import serializers
from subprojects import (
    WORKS_TYPE_OF_SUB_PROJECT,
    LEVEL_OF_ACHIEVEMENT_DONATION_CERTIFICATE_OF_SUB_PROJECT, 
    CURRENT_STATUS_OF_THE_SITE, SUB_PROJECT_TYPE_DESIGNATION
)
from subprojects.vars import VAR_SUB_PROJECT_SECTORS, VAR_TYPES_OF_SUB_PROJECT


# app_name/serializers.py
# Ajoutez un serializer pour les modèles AdministrativeLevel, CVD, Component, etc.
class RelatedModelSerializer(serializers.ModelSerializer):
    class Meta:
        fields = ['id', 'name'] # Assurez-vous que le modèle a un champ 'name' ou 'title'
        # Le champ 'name' doit être un nom parlant pour l'utilisateur
        # Si le nom est 'libelle', utilisez: fields = ['id', 'libelle'] 
        # et renommez 'name' à 'libelle' dans le serializer.

        # NOTE: Vous devez définir model=X plus bas.




# app_name/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from django.apps import apps

class OptionsAPIView(APIView):
    def get(self, request, model_name):
        
        try:
            # Récupère le modèle à partir du nom (ex: 'CVD')
            Model = apps.get_model('my_app', model_name) # Remplacez 'my_app' par le nom de votre application
        except LookupError:
            return Response({"error": "Model not found"}, status=404)

        # Crée dynamiquement le serializer
        class DynamicSerializer(serializers.ModelSerializer):
            class Meta:
                model = Model
                # Assurez-vous que le modèle a un champ de nom parlant (ici on suppose 'name' ou 'title')
                fields = ('id', 'name') # Ajustez 'name' si votre champ est 'libelle' ou autre

        queryset = Model.objects.all().order_by('name')
        serializer = DynamicSerializer(queryset, many=True)

        # Renvoie une liste d'objets [{id: 1, name: "CVD X"}, ...]
        return Response(serializer.data)
    



# app_name/serializers.py
from rest_framework import serializers
from subprojects.models import Subproject

class SubprojectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subproject
        # Incluez tous les champs que vous voulez pouvoir modifier
        fields = '__all__'



# app_name/views.py
from rest_framework import viewsets
# from .serializers import SubprojectSerializer

class SubprojectViewSet(viewsets.ModelViewSet):
    queryset = Subproject.objects.all()
    serializer_class = SubprojectSerializer







# Assuming your model is defined in an application named 'my_app' (adjust as needed)
from django.shortcuts import render

choices_datas = {
    'subproject_sector': VAR_SUB_PROJECT_SECTORS,
    'type_of_subproject': VAR_TYPES_OF_SUB_PROJECT,
    'works_type': WORKS_TYPE_OF_SUB_PROJECT,
    'level_of_achievement_donation_certificate': LEVEL_OF_ACHIEVEMENT_DONATION_CERTIFICATE_OF_SUB_PROJECT,
    'current_status_of_the_site': CURRENT_STATUS_OF_THE_SITE,
    'subproject_type_designation': SUB_PROJECT_TYPE_DESIGNATION,
}

def get_subproject_metadata(request):

    """
    Récupère la liste des champs du modèle Subproject avec leurs verbose_name.
    """
    
    meta = Subproject._meta
    
    field_metadata = []
    for field in meta.get_fields(include_parents=False):# meta.concrete_fields:#meta.get_fields(include_parents=False): # linked_subprojects, subprojectstep, subprojectfile, list_of_beneficiary_villages, list_of_villages_crossed_by_the_track_or_electrification, priorities, projects, financiers
        
        # # Exclure les champs de relation ManyToMany
        # if field.many_to_many or field.name in (FORM_FIELDS_TO_EXCLUDE+TABLE_SHEET_FIELDS_TO_EXCLUDE):
        #     continue
        if field.name in (FORM_FIELDS_TO_EXCLUDE+TABLE_SHEET_FIELDS_TO_EXCLUDE):
            continue
        
        field_name = field.name
        
        verbose_name = getattr(field, 'verbose_name', field_name).title()

        field_info = {
            'data': field_name,
            'header': verbose_name,
            'type': 'text' # Type par défaut
        }

        if field_name in ['id', 'created_date', 'updated_date']:
            field_info['readOnly'] = True
        
        if field_name in [
            'subproject_sector', 'type_of_subproject', 'works_type', 'level_of_achievement_donation_certificate', 'current_status_of_the_site',
            'subproject_type_designation'
            ]:
            field_info['type'] = 'dropdown'
            _datas = choices_datas.get(field_name, [])
            field_info['source'] = [f"{item[0]}" for item in _datas] if _datas else [""]
            field_metadata.append(field_info)
            continue
        
        # Gérer le cas spécial des ForeignKeys pour s'assurer qu'on ne prend pas
        # seulement le champ 'id' implicite si on veut la relation complète,
        # mais dans le contexte de Handsontable, on veut souvent la clé brute.
        
        if field.is_relation and field.one_to_one is False:
            
            # Si c'est une relation (ForeignKey), nous utiliserons un dropdown
            
            # Nom du modèle lié (ex: 'AdministrativeLevel' ou 'CVD')
            related_model_name = field.related_model.__name__
            
            field_info['type'] = 'dropdown' # Type pour Handsontable
            field_info['strict'] = False # Permet de taper des IDs qui ne sont pas exactement dans la liste
            if field.many_to_many or field.one_to_many:
                field_info['renderer'] = 'generic_multi_select_renderer'
                field_info['editor'] = 'multi_select_checkbox_editor'
                field_info['mapSource'] = field_name
                field_info['type'] = 'autocomplete'
            else:
                field_info['renderer'] = 'select_renderer' # Renderer personnalisé pour afficher le nom au lieu de l'ID brut
            field_info['source_url'] = f'/api/options/{related_model_name}/' # URL pour récupérer les options

            try:
                ClassModal = None
                for app_conf in apps.get_app_configs():
                    try:
                        ClassModal = app_conf.get_model(related_model_name)
                        break # stop as soon as it is found
                    except LookupError:
                        # no such model in this application
                        pass
                
                if ClassModal:
                    name = 'name'
                    if hasattr(ClassModal, 'full_title_of_approved_subproject'):
                        name = 'full_title_of_approved_subproject'
                    elif hasattr(ClassModal, 'wording'):
                        name = 'wording'
                    elif hasattr(ClassModal, 'libelle'):
                        name = 'libelle'
                    
                    if name == 'full_title_of_approved_subproject':
                        objects = ClassModal.objects.get_actifs(projects_ids=[request.session.get('project_id')]).only('id', name, 'location_subproject_realized').order_by(name)
                        options = [""] + [
                            f"[{obj.id}.{obj.location_subproject_realized.name}{(' (' + obj.location_subproject_realized.parent.name + ')' if obj.location_subproject_realized.parent else '')}].{getattr(obj, name)}" if obj.location_subproject_realized else f"[{obj.id}].{getattr(obj, name)}" for obj in objects
                        ]
                    else:
                        if related_model_name.lower() == 'administrativelevel':
                            objects = ClassModal.objects.get_objects_by_general_filtre(request, {
                                'administrative_levels_projects__in': [request.session.get('project_id')],
                                'type': 'Village'
                            }).only('id', name).order_by(name)
                        else:
                            objects = ClassModal.objects.all().only('id', name).order_by(name)
                        options = [""] + [f"""[{obj.id}].{
                            (getattr(obj, name) + ' (' + getattr(obj.parent, name) + ')') if hasattr(obj, 'parent') and obj.parent else getattr(obj, name)
                            }""" for obj in objects]
                    
                    field_info['source'] = options

            except Exception as e:
                print("Error fetching options for", related_model_name, ":", e)
                
            
            # Handsontable doit modifier le champ qui stocke la clé (l'ID),
            # qui est souvent le nom du champ (ex: 'cvd')
            field_metadata.append(field_info)
            continue # Passer à la prochaine itération une fois le traitement terminé

        # 3. Traitement des autres types (texte, numérique, booléen, date)
        # Vous devez étendre cette logique pour les autres types comme 'date' ou 'numeric'
        if field_name in ['created_date', 'updated_date']:
            field_info['type'] = 'date'
            field_info['dateFormat'] = 'YYYY-MM-DDTHH:mm:ss.SSSZ'
            field_info['displayFormat'] = 'YYYY-MM-DDTHH:mm:ss.SSSZ'
            field_info['correctFormat'] = True
        elif 'date' in field_name:
            field_info['type'] = 'date'
            field_info['dateFormat'] = 'YYYY-MM-DD'
            field_info['displayFormat'] = 'YYYY-MM-DD'
            field_info['correctFormat'] = True
        elif field.get_internal_type() in ['IntegerField', 'FloatField']:
            field_info['type'] = 'numeric'
            field_info['numericFormat'] = {
                'pattern': '0,0', 
                'culture': 'fr-FR', 
                'pattern': '#,##0' #'#,##0.00' 
            }
        elif field.get_internal_type() == 'BooleanField':
             field_info['type'] = 'checkbox'
        # ... (ajoutez d'autres types si nécessaire)

        field_metadata.append(field_info)
        
    
    return field_metadata


# app_name/views.py (Ajouter à la suite de SubprojectViewSet)
from django.shortcuts import render
import json

def subproject_sheet_view(request):


    metadata = get_subproject_metadata(request)
        
    # 2. Séparer les noms de colonnes et les titres
    column_data_names = [item['data'] for item in metadata]
    column_headers = [item['header'] for item in metadata]

    # 3. Préparer les données (Exemple: pour charger les données initiales)
    # Note : Vous devriez normalement utiliser un Serializer DRF ici, mais
    # pour un exemple simple de passage au template :
    # subprojects = list(Subproject.objects.all().values(*column_data_names))


    column_data_names_json_string = json.dumps(column_data_names)
    
    context = {
        # Ces deux listes peuvent être passées au template pour générer le JS
        'column_data_names_json': column_data_names_json_string,
        'column_headers_json': column_headers,
        'column_definitions_json': metadata,
        # 'subprojects_data_json': subprojects,
    }
    

    return render(request, 'sheet/subproject_sheet.html', context)