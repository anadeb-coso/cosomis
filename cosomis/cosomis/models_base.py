from django.db import models
from django.utils.translation import gettext_lazy as _
import datetime
from cosomis.base_functions import model_to_full_dict, format_value


class ExternalIdMixin(models.Model):
    """Reference ID (the workbook's own `ID_xxx` column value) for models covered
    by `financial/management/commands/import_disbursement_workbook.py` - lets a
    later re-import of the same workbook match and update an existing row instead
    of creating a duplicate. Stays None for a record created directly in the app
    (never backfilled from the app's own primary key)."""

    external_id = models.CharField(max_length=50, null=True, blank=True, unique=True, verbose_name=_("External ID"))

    class Meta:
        abstract = True


# Create your models here.
class BaseModel(models.Model):
    created_date = models.DateTimeField(auto_now_add = True, blank=True, null=True)
    updated_date = models.DateTimeField(auto_now = True, blank=True, null=True)
    create_by_user = models.JSONField(blank=True, null=True)
    update_by_user = models.JSONField(blank=True, null=True)
    users_involved = models.JSONField(blank=True, null=True)

    class Meta:
        abstract = True
    
    def save_and_return_object(self, user=None, force_insert=False, force_update=False, using=None, update_fields=None):
        return self.users_history(user, force_insert, force_update, using, update_fields)
    
    def save(self, force_insert=False, force_update=False, using=None, update_fields=None, user=None):
        self.users_history(user, force_insert, force_update, using, update_fields)


    
    def users_history(self, user, force_insert=False, force_update=False, using=None, update_fields=None):
        """
        Save users stories
        user_json = {
            "type": "facilitator", # or user
            "date": self.updated_date,
            "data_changed": {"attr": (old_data, new_data)},
            "data": self
        }

        """
        
        user_json = (user if type(user) is dict else model_to_full_dict(user)) if user else {'type': None}
        self_json = model_to_full_dict(self)
        
        db_data_json, diffs, users_involved = None, None, None
        if self.id:
            db_data = self.__class__.objects.get(id=self.id)
            users_involved = db_data.users_involved if db_data.users_involved else []
            db_data_json = model_to_full_dict(db_data)
            diffs = {
                field: (format_value(db_data_json[field]), format_value(self_json[field]))
                for field in db_data_json
                if field not in [
                    'users_involved', 'update_by_user', 'created_date', 'updated_date', 'create_by_user'
                ] and db_data_json[field] != self_json[field]
            }
            
        if diffs == None or diffs:
            
            if user_json.get('last_name'):
                user_json['type'] = "user"
            elif user_json.get('no_sql_user'):
                user_json['type'] = "facilitator"
            # else:
            #     user_json['type'] = "facilitator"
            
            if db_data_json:
                user_json['data_updated_date'] = datetime.datetime.now().isoformat()
                user_json['data_changed'] = diffs
            else:
                user_json['data_created_date'] = datetime.datetime.now().isoformat()
                user_json['data'] = self_json

            if not users_involved:
                users_involved = self.users_involved if self.users_involved else []
                
            if self.created_date == self.updated_date:
                self.create_by_user = user_json
                
            self.update_by_user = user_json
            
            users_involved.append(user_json)

            self.users_involved = format_value(users_involved)
            
            super().save(force_insert, force_update, using, update_fields)
        else:
            pass
            
        return self



class CustomQuerySet(models.QuerySet):
    
    def get_objects_by_general_filtre(self, request, attrs, *args, **kwargs):
        if self.first():
            if self.first().__class__.__name__ in ["Phase", "Activity", "Task"]:
                return self.get_process_manager_actifs(request, attrs, *args, **kwargs)
            elif self.first().__class__.__name__ in ["AdministrativeLevel"]:
                return self.get_adl_actifs(request, attrs, *args, **kwargs)
        return self.filter()
    
    def get_adl_actifs(self, request, attrs, *args, **kwargs):
        if attrs:
            return self.filter(**attrs)
        elif request and request.user and request.user.is_authenticated:
            return self.filter(
                administrative_levels_projects__in=[request.session.get('project_id')]
            )
        return self.filter()
    
    def get_process_manager_actifs(self, request, attrs, *args, **kwargs):
        if attrs:
            if 'cycle_id' in attrs:
                attrs['cycles__in'] = [attrs.get('cycle_id')]
                del attrs['cycle_id']
            return self.filter(**attrs)
        elif request and request.user and request.user.is_authenticated:
            return self.filter(project_id=request.session.get('project_id'), cycles__in=[request.session.get('cycle_id')])
        return self.filter()