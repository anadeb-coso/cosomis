from django.contrib import admin

from financial.models.report_template import ReportTemplate


@admin.register(ReportTemplate)
class ReportTemplateAdmin(admin.ModelAdmin):
    list_display = ('title', 'report_type', 'periodicity', 'file_format', 'is_active', 'last_sent')
    list_filter = ('report_type', 'periodicity', 'is_active')
    filter_horizontal = ('recipients',)
