from rest_framework import serializers
import datetime
from cosomis.base_functions import model_to_full_dict, format_value, model_or_dict_to_serializable, make_json_serializable


# Create your models here.
class BaseModelSerializerCustomer(serializers.ModelSerializer):
    pass
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
