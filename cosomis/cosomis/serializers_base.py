from contextlib import contextmanager
import contextvars

from rest_framework import serializers
import datetime
from cosomis.base_functions import model_to_full_dict, format_value, model_or_dict_to_serializable, make_json_serializable


_SHARED_REPRESENTATIONS = contextvars.ContextVar('shared_representations', default=None)


@contextmanager
def shared_representations():
    """Pendant la construction d'une réponse d'API : la représentation d'un même objet de référence (niveau
    administratif et ses parents, CVD, projet, composante), répété d'un élément à l'autre, n'est calculée qu'une fois
    puis réutilisée telle quelle (les données ne changent pas pendant la réponse). Sans ce bloc, rien n'est gardé."""
    token = _SHARED_REPRESENTATIONS.set({})
    try:
        yield
    finally:
        _SHARED_REPRESENTATIONS.reset(token)


def shared_representation(serializer, instance, build):
    """Représentation de `instance` par `serializer` : build() la première fois dans la réponse, puis la même.
    Le résultat ne doit plus être modifié par l'appelant (il peut être repris ailleurs dans la réponse)."""
    cache = _SHARED_REPRESENTATIONS.get()
    if cache is None or instance is None or instance.pk is None:
        return build()
    key = (type(serializer), instance.pk)
    if key not in cache:
        cache[key] = build()
    return cache[key]


class SharedRepresentationMixin:
    """Sérialiseur d'objet de référence sans paramètre propre : sa représentation est partagée dans la réponse
    (voir shared_representations)."""

    def to_representation(self, instance):
        return shared_representation(self, instance, lambda: super(SharedRepresentationMixin, self).to_representation(instance))


class ReferenceValueField(serializers.SlugRelatedField):
    """Clé étrangère vers le nom d'une liste de référence (`to_field='name'`, ex. Subproject.subproject_sector) : la
    valeur rangée dans la colonne est déjà le nom, lu sans requête ; en écriture, le nom doit exister dans la liste."""

    def use_pk_only_optimization(self):
        return True

    def to_representation(self, value):
        return value.pk


# Create your models here.
class BaseModelSerializerCustomer(serializers.ModelSerializer):
    # relations `to_field` (listes de référence des sous-projets) : texte de la valeur, comme avant
    serializer_related_to_field = ReferenceValueField
    # def save(self, **kwargs):
    #     return self.users_history(**kwargs)


    
    # def users_history(self, **kwargs):
    #     """
    #     Save users stories
    #     user_json = {
    #         "type": "facilitator", # or user
    #         "date": self.updated_date,
    #         "data_changed": {"attr": (old_data, new_data)},
    #         "data": self
    #     }

    #     """
    #     user = kwargs.get('user')
    

    #     user_json = (user if type(user) is dict else model_to_full_dict(user)) if user else {'is_superuser': True}
    #     instance_json = make_json_serializable(self.validated_data)
        
    #     db_data_json, diffs = None, None
    #     if self.instance is not None:
    #         db_data = self.instance.__class__.objects.get(id=self.instance.id)
    #         db_data_json = model_to_full_dict(db_data)
    #         del db_data_json['id']
    #         diffs = {
    #             field: (format_value(db_data_json[field]), format_value(instance_json[field]))
    #             for field in db_data_json
    #             if db_data_json[field] != instance_json[field]
    #         }
    
    #     if diffs == None or diffs:

    #         if user_json.get('is_superuser'):
    #             user_json['type'] = "user"
    #         else:
    #             user_json['type'] = "facilitator"
            
    #         if db_data_json:
    #             user_json['data_updated_date'] = datetime.datetime.now().isoformat()
    #             user_json['data_changed'] = diffs
    #         else:
    #             user_json['data_created_date'] = datetime.datetime.now().isoformat()
    #             user_json['data'] = instance_json


    #         users_involved = self.validated_data.get('users_involved') or []

    #         if self.validated_data.get('created_date') == self.validated_data.get('updated_date'):
    #             self.validated_data['create_by_user'] = user_json
                
    #         self.validated_data['update_by_user'] = user_json
            
    #         users_involved.append(user_json)

    #         self.validated_data['users_involved'] = format_value(users_involved)

    #         return super().save(**kwargs)
            
    #     else:
    #         pass
            
        
    #     return None
