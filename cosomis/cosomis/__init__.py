from __future__ import absolute_import, unicode_literals
from .celery import app as celery_app

__all__ = ('celery_app',)

FORM_FIELDS_TO_EXCLUDE = ['create_by_user', 'update_by_user', 'users_involved', 'external_id'] # specify the fields to be hid
TABLE_SHEET_FIELDS_TO_EXCLUDE = ['created_date', 'linked_subprojects', 'subprojectstep', 'subprojectfile', 'cvd', 'canton', 'financiers', 'list_of_beneficiary_villages', 'priorities']