from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.utils.translation import gettext_lazy as _

# from django.forms.models import model_to_dict


""" CDD """


class Facilitator(models.Model):
    no_sql_user = models.CharField(max_length=150, unique=True)
    no_sql_pass = models.CharField(max_length=128)
    no_sql_db_name = models.CharField(max_length=150, unique=True)
    username = models.CharField(max_length=150, unique=True, verbose_name=_('username'))
    password = models.CharField(max_length=128, verbose_name=_('password'))
    code = models.CharField(max_length=6, unique=True, verbose_name=_('code'))
    active = models.BooleanField(default=False, verbose_name=_('active'))
    develop_mode = models.BooleanField(default=False, verbose_name=_('test mode'))
    training_mode = models.BooleanField(default=False, verbose_name=_('test mode'))
    
    name = models.CharField(max_length=200, null=True, blank=True, verbose_name=_('name'))
    email = models.CharField(max_length=100, null=True, blank=True, verbose_name=_('email'))
    phone = models.CharField(max_length=20, null=True, blank=True, verbose_name=_('phone'))
    sex = models.CharField(max_length=5, null=True, blank=True, verbose_name=_('sex'))
    total_tasks = models.IntegerField(default=0)
    total_tasks_completed = models.IntegerField(default=0)
    last_activity = models.DateTimeField(blank=True, null=True)

    @property
    def is_active(self):
        return self.active
    
    
    
    
    
    
    
""" GRM """
class User(AbstractUser):
    email = models.EmailField(unique=True, verbose_name=_('email address'))
    phone_number = models.CharField(max_length=45, verbose_name=_('phone number'))
    photo = models.CharField(max_length=45, verbose_name=_('photo'))
    groups = models.ManyToManyField(Group, related_name='grm_user_groups')
    user_permissions = models.ManyToManyField(Permission, related_name='grm_user_permissions')
    # using = 'grm'
    # class Meta:
    #     using = 'grm'

        
    def __str__(self):
        return self.email

    @property
    def name(self):
        return f'{self.first_name} {self.last_name}'
    
    @property
    def administrative_level(self):
        if self and hasattr(self, 'governmentworker'):
            return self.governmentworker.administrative_level
        return None
    

class GovernmentWorker(models.Model):
    user = models.OneToOneField('User', models.PROTECT)
    department = models.PositiveSmallIntegerField(db_index=True, verbose_name=_('department'))
    administrative_id = models.CharField(
        max_length=255, blank=True, null=True, verbose_name=_('administrative level'))
    administrative_ids = models.JSONField(blank=True, null=True, verbose_name=_('administrative levels'))

    class Meta:
        verbose_name = _('Government Worker')
        verbose_name_plural = _('Government Workers')

    @property
    def name(self):
        return self.user.name
    
    @property
    def all_administrative_ids(self):
        return list(
                set(
                    (self.administrative_ids if self.administrative_ids else list()) \
                    + ([self.administrative_id] if self.administrative_id else list())
                )
            )