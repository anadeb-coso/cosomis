from django.contrib import admin

from procurement.models import Delivery, DeliveryLine, SupplyOrder, SupplyOrderLine


class SupplyOrderLineInline(admin.TabularInline):
    model = SupplyOrderLine
    extra = 0


class DeliveryLineInline(admin.TabularInline):
    model = DeliveryLine
    extra = 0


@admin.register(SupplyOrder)
class SupplyOrderAdmin(admin.ModelAdmin):
    list_display = ('reference', 'subject', 'subproject', 'supplier', 'order_date', 'expected_delivery_date', 'cancelled')
    search_fields = ('reference', 'subject', 'supplier')
    raw_id_fields = ('subproject',)
    inlines = [SupplyOrderLineInline]


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = ('order', 'delivery_date', 'delivery_note', 'reception_date', 'received_by')
    raw_id_fields = ('order', 'received_by')
    inlines = [DeliveryLineInline]
