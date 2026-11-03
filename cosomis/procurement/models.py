"""Procurement: supply and equipment orders attached to sub-projects, their deliveries
and the reception of those deliveries (quantities accepted, reservations)."""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext, gettext_lazy as _

from cosomis.models_base import BaseModel, SoftDeleteMixin

ZERO = Decimal('0')


class SupplyOrder(SoftDeleteMixin, BaseModel):
    class Status(models.TextChoices):
        ORDERED = 'ORDERED', _('Ordered')
        PARTIALLY_DELIVERED = 'PARTIALLY_DELIVERED', _('Partially delivered')
        DELIVERED = 'DELIVERED', _('Delivered, awaiting reception')
        RECEIVED = 'RECEIVED', _('Received')
        CANCELLED = 'CANCELLED', _('Cancelled')

    subproject = models.ForeignKey('subprojects.Subproject', on_delete=models.CASCADE, related_name='supply_orders',
                                   verbose_name=_("Sub-project"))
    reference = models.CharField(max_length=100, verbose_name=_("Purchase order reference"))
    subject = models.CharField(max_length=255, verbose_name=_("Subject"))
    supplier = models.CharField(max_length=255, verbose_name=_("Supplier"))
    order_date = models.DateField(default=timezone.localdate, verbose_name=_("Order date"))
    expected_delivery_date = models.DateField(null=True, blank=True, verbose_name=_("Expected delivery date"))
    delivery_place = models.CharField(max_length=255, null=True, blank=True, verbose_name=_("Delivery place"))
    cancelled = models.BooleanField(default=False, verbose_name=_("Order cancelled"))
    notes = models.TextField(null=True, blank=True, verbose_name=_("Observations"))

    class Meta:
        verbose_name = _("Supply order")
        verbose_name_plural = _("Supply orders")
        ordering = ['-order_date', '-pk']
        base_manager_name = 'objects'
        constraints = [models.UniqueConstraint(fields=['subproject', 'reference'], name='unique_supply_order_per_subproject')]

    def __str__(self):
        return f"{self.reference} - {self.subject}"

    def clean(self):
        if self.expected_delivery_date and self.order_date and self.expected_delivery_date < self.order_date:
            raise ValidationError({'expected_delivery_date': _("The delivery cannot be expected before the order.")})
        super().clean()

    @property
    def amount(self):
        return sum((line.amount for line in self.lines.all()), ZERO)

    def _quantities(self):
        lines = list(self.lines.all())
        ordered = sum((line.quantity for line in lines), ZERO)
        delivered = sum((line.quantity_delivered for line in lines), ZERO)
        return ordered, delivered

    @property
    def delivery_rate(self):
        ordered, delivered = self._quantities()
        return min(delivered / ordered * 100, Decimal('100')).quantize(Decimal('0.1')) if ordered else None

    @property
    def status(self):
        if self.cancelled:
            return self.Status.CANCELLED
        ordered, delivered = self._quantities()
        if not ordered or not delivered:
            return self.Status.ORDERED
        if delivered < ordered:
            return self.Status.PARTIALLY_DELIVERED
        if self.deliveries.filter(reception_date__isnull=True).exists():
            return self.Status.DELIVERED
        return self.Status.RECEIVED

    def get_status_display(self):
        return self.Status(self.status).label

    @property
    def is_late(self):
        return (self.expected_delivery_date is not None and self.expected_delivery_date < timezone.localdate()
                and self.status in (self.Status.ORDERED, self.Status.PARTIALLY_DELIVERED))


class SupplyOrderLine(BaseModel):
    order = models.ForeignKey(SupplyOrder, on_delete=models.CASCADE, related_name='lines', verbose_name=_("Order"))
    designation = models.CharField(max_length=255, verbose_name=_("Designation"))
    unit = models.CharField(max_length=30, default='unité', verbose_name=_("Unit"))
    quantity = models.DecimalField(max_digits=14, decimal_places=2, verbose_name=_("Quantity ordered"))
    unit_price = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True, verbose_name=_("Unit price (FCFA)"))

    class Meta:
        verbose_name = _("Order line")
        verbose_name_plural = _("Order lines")
        ordering = ['order', 'pk']

    def __str__(self):
        return f"{self.designation} ({self.quantity} {self.unit})"

    def clean(self):
        if self.quantity is not None and self.quantity <= 0:
            raise ValidationError({'quantity': _("The quantity must be positive.")})
        super().clean()

    @property
    def amount(self):
        return (self.quantity or ZERO) * (self.unit_price or ZERO)

    @property
    def quantity_delivered(self):
        return self.delivery_lines.aggregate(t=Sum('quantity_delivered'))['t'] or ZERO

    @property
    def quantity_accepted(self):
        return self.delivery_lines.exclude(delivery__reception_date=None).aggregate(t=Sum('quantity_accepted'))['t'] or ZERO

    @property
    def remaining(self):
        return max((self.quantity or ZERO) - self.quantity_delivered, ZERO)


class Delivery(SoftDeleteMixin, BaseModel):
    """Delivery of an order (delivery note), then its reception (quantity and conformity check)."""
    order = models.ForeignKey(SupplyOrder, on_delete=models.CASCADE, related_name='deliveries', verbose_name=_("Order"))
    delivery_date = models.DateField(default=timezone.localdate, verbose_name=_("Delivery date"))
    delivery_note = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("Delivery note number"))
    document = models.FileField(upload_to='procurement/%Y/%m/', max_length=500, null=True, blank=True,
                                verbose_name=_("Delivery note or minutes (file)"))
    reception_date = models.DateField(null=True, blank=True, verbose_name=_("Reception date"),
                                      help_text=_("To fill in once quantities and conformity have been checked."))
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='received_supply_deliveries', verbose_name=_("Received by"))
    reservations = models.TextField(null=True, blank=True, verbose_name=_("Reservations (non-conformities found)"))

    class Meta:
        verbose_name = _("Delivery / reception")
        verbose_name_plural = _("Deliveries and receptions")
        ordering = ['-delivery_date', '-pk']
        base_manager_name = 'objects'

    def __str__(self):
        return gettext("Delivery of {date:%d/%m/%Y} - {reference}").format(date=self.delivery_date, reference=self.order.reference)

    def clean(self):
        if self.reception_date and self.delivery_date and self.reception_date < self.delivery_date:
            raise ValidationError({'reception_date': _("The reception cannot precede the delivery.")})
        super().clean()


class DeliveryLine(BaseModel):
    delivery = models.ForeignKey(Delivery, on_delete=models.CASCADE, related_name='lines', verbose_name=_("Delivery"))
    order_line = models.ForeignKey(SupplyOrderLine, on_delete=models.CASCADE, related_name='delivery_lines',
                                   verbose_name=_("Ordered item"))
    quantity_delivered = models.DecimalField(max_digits=14, decimal_places=2, verbose_name=_("Quantity delivered"))
    quantity_accepted = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                            verbose_name=_("Quantity accepted at reception"))

    class Meta:
        verbose_name = _("Delivered item")
        verbose_name_plural = _("Delivered items")
        constraints = [models.UniqueConstraint(fields=['delivery', 'order_line'], name='unique_item_per_delivery')]

    def __str__(self):
        return f"{self.order_line.designation} : {self.quantity_delivered}"

    def clean(self):
        if self.order_line_id and self.delivery_id and self.order_line.order_id != self.delivery.order_id:
            raise ValidationError({'order_line': _("The item must belong to the delivered order.")})
        if self.quantity_delivered is not None and self.quantity_delivered <= 0:
            raise ValidationError({'quantity_delivered': _("The delivered quantity must be positive.")})
        if (self.quantity_accepted is not None and self.quantity_delivered is not None
                and self.quantity_accepted > self.quantity_delivered):
            raise ValidationError({'quantity_accepted': _("You cannot accept more than the delivered quantity.")})
        if self.order_line_id and self.quantity_delivered is not None:
            already = self.order_line.delivery_lines.exclude(pk=self.pk).aggregate(t=Sum('quantity_delivered'))['t'] or ZERO
            if already + self.quantity_delivered > self.order_line.quantity:
                raise ValidationError({'quantity_delivered': _("Delivery greater than the remaining quantity (%(remaining)s).") % {
                    'remaining': self.order_line.quantity - already}})
        super().clean()

    def save(self, *args, **kwargs):
        if (self.quantity_accepted is None and self.delivery_id and self.delivery.reception_date
                and not self.delivery.reservations):
            self.quantity_accepted = self.quantity_delivered  # reception without reservation: everything is accepted
        super().save(*args, **kwargs)
