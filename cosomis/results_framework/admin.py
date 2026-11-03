from django.contrib import admin

from results_framework.models import IndicatorMeasurement, ResultIndicator


class MeasurementInline(admin.TabularInline):
    model = IndicatorMeasurement
    fields = ('date', 'value', 'source', 'comment')
    extra = 0


@admin.register(ResultIndicator)
class ResultIndicatorAdmin(admin.ModelAdmin):
    list_display = ('code', 'label', 'project', 'indicator_type', 'unit', 'baseline_value', 'target')
    list_filter = ('project', 'indicator_type')
    search_fields = ('code', 'label')
    inlines = [MeasurementInline]
