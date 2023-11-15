from django.contrib import admin
from .models import AdministrativeLevel, GeographicalUnit, CVD


class AdministrativeLevelAdmin(admin.ModelAdmin):
    search_fields = [
        'name',
        'no_sql_db_id'
    ]
    
    list_display = (
        'name',
        'parent__name',
        'no_sql_db_id'
    )


# Register your models here.
admin.site.register(AdministrativeLevel, AdministrativeLevelAdmin)
admin.site.register(GeographicalUnit)
admin.site.register(CVD)