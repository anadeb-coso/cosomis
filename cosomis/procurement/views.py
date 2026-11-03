"""Procurement pages: overview of supply orders, order detail (items, deliveries), and their forms."""
from decimal import Decimal, InvalidOperation

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext, gettext_lazy as _
from django.views import generic
from django.views.decorators.http import require_POST

from cosomis.access import EditorRequiredMixin, SaveWithHistoryMixin, can_edit
from cosomis.project_scope import ProjectRequiredMixin, ProjectScope, project_required
from procurement.models import Delivery, DeliveryLine, SupplyOrder, SupplyOrderLine
from subprojects.models import Subproject

ACTIVE = 'procurement'


def orders_in_scope(request):
    """Orders of the sub-projects financed by the projects shown on the page (selection + linked projects)."""
    ids = ProjectScope(request).ids
    return SupplyOrder.objects.filter(pk__in=SupplyOrder.objects.filter(subproject__projects__in=ids).values('pk'))


def subprojects_in_scope(request):
    return Subproject.objects.filter(projects__in=ProjectScope(request).ids).distinct().order_by('number')


def _styled(form):
    for field in form.fields.values():
        if not isinstance(field.widget, forms.CheckboxInput):
            field.widget.attrs.setdefault('class', 'form-control')
    return form


class SubprojectField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        title = (obj.full_title_of_approved_subproject or '')[:90]
        return f"{obj.number} - {title}" if obj.number else title


class SupplyOrderForm(forms.ModelForm):
    subproject = SubprojectField(Subproject.objects.order_by('number'), label=_("Sub-project"))

    class Meta:
        model = SupplyOrder
        fields = ['subproject', 'reference', 'subject', 'supplier', 'order_date', 'expected_delivery_date',
                  'delivery_place', 'cancelled', 'notes']
        widgets = {'order_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
                   'expected_delivery_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
                   'notes': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, subprojects=None, **kwargs):
        super().__init__(*args, **kwargs)
        if subprojects is not None:
            self.fields['subproject'].queryset = subprojects
        _styled(self)


class SupplyOrderLineForm(forms.ModelForm):
    class Meta:
        model = SupplyOrderLine
        fields = ['designation', 'unit', 'quantity', 'unit_price']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _styled(self)


class DeliveryForm(forms.ModelForm):
    class Meta:
        model = Delivery
        fields = ['delivery_date', 'delivery_note', 'document', 'reception_date', 'reservations']
        widgets = {'delivery_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
                   'reception_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
                   'reservations': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _styled(self)


# ----------------------------------------------------------------------------- overview
@login_required
@project_required
def overview(request):
    scope = ProjectScope(request)
    orders = (orders_in_scope(request).select_related('subproject')
              .prefetch_related('lines__delivery_lines', 'deliveries').order_by('-order_date', '-pk'))
    search = request.GET.get('q', '').strip()
    if search:
        orders = orders.filter(Q(reference__icontains=search) | Q(subject__icontains=search)
                               | Q(supplier__icontains=search)
                               | Q(subproject__full_title_of_approved_subproject__icontains=search))
    orders = list(orders)
    status = request.GET.get('status', '')
    rows = []
    for order in orders:
        row = {'order': order, 'status': order.status, 'status_label': order.get_status_display(),
               'amount': order.amount, 'rate': order.delivery_rate, 'late': order.is_late}
        if status == 'LATE' and not row['late']:
            continue
        if status and status != 'LATE' and row['status'] != status:
            continue
        rows.append(row)
    active = [o for o in orders if not o.cancelled]
    figures = {
        'total': len(active),
        'pending': sum(o.status in (SupplyOrder.Status.ORDERED, SupplyOrder.Status.PARTIALLY_DELIVERED) for o in active),
        'late': sum(o.is_late for o in active),
        'to_receive': sum(o.status == SupplyOrder.Status.DELIVERED for o in active),
        'received': sum(o.status == SupplyOrder.Status.RECEIVED for o in active),
        'amount': sum((o.amount for o in active), Decimal('0')),
    }
    return render(request, 'procurement/overview.html', {
        'title': gettext("Procurement"), 'active_level1': ACTIVE,
        'breadcrumb': [{'url': '', 'title': gettext("Procurement")}],
        'rows': rows, 'figures': figures, 'status': status, 'statuses': SupplyOrder.Status.choices,
        'search': search, 'can_edit': can_edit(request.user), **scope.context(),
    })


@login_required
@project_required
def order_detail(request, pk):
    order = get_object_or_404(orders_in_scope(request).select_related('subproject'), pk=pk)
    lines = list(order.lines.prefetch_related('delivery_lines__delivery'))
    deliveries = order.deliveries.prefetch_related('lines__order_line').select_related('received_by')
    return render(request, 'procurement/order_detail.html', {
        'title': str(order), 'active_level1': ACTIVE,
        'breadcrumb': [{'url': reverse('procurement:overview'), 'title': gettext("Procurement")}, {'url': '', 'title': order.reference}],
        'order': order, 'lines': lines, 'deliveries': deliveries,
        'line_form': SupplyOrderLineForm(), 'can_edit': can_edit(request.user),
    })


# ----------------------------------------------------------------------------- orders
class OrderMixin(ProjectRequiredMixin, EditorRequiredMixin, SaveWithHistoryMixin):
    model = SupplyOrder
    form_class = SupplyOrderForm
    template_name = 'common/page_form.html'
    active_level1 = ACTIVE

    def get_queryset(self):
        return orders_in_scope(self.request)

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), 'subprojects': subprojects_in_scope(self.request)}

    def get_success_url(self):
        return reverse('procurement:order_detail', args=[self.object.pk])

    def get_back_url(self):
        return reverse('procurement:overview')


class OrderCreateView(OrderMixin, generic.CreateView):
    page_title = _("New supply order")

    def get_initial(self):
        return {'subproject': self.request.GET.get('subproject')}


class OrderUpdateView(OrderMixin, generic.UpdateView):
    page_title = _("Edit supply order")


@login_required
@require_POST
def order_delete(request, pk):
    if not can_edit(request.user):
        raise Http404
    get_object_or_404(orders_in_scope(request), pk=pk).soft_delete(user=request.user)
    messages.success(request, gettext("The order has been deleted."))
    return redirect('procurement:overview')


# ----------------------------------------------------------------------------- order lines
@login_required
@require_POST
def line_create(request, order_pk):
    if not can_edit(request.user):
        raise Http404
    order = get_object_or_404(orders_in_scope(request), pk=order_pk)
    form = SupplyOrderLineForm(request.POST, instance=SupplyOrderLine(order=order))
    if form.is_valid():
        form.instance.save_and_return_object(request.user)
        messages.success(request, gettext("The item has been added."))
    else:
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
    return redirect('procurement:order_detail', pk=order.pk)


class LineUpdateView(ProjectRequiredMixin, EditorRequiredMixin, SaveWithHistoryMixin, generic.UpdateView):
    model = SupplyOrderLine
    form_class = SupplyOrderLineForm
    template_name = 'common/page_form.html'
    active_level1 = ACTIVE
    page_title = _("Edit item")

    def get_queryset(self):
        return SupplyOrderLine.objects.filter(order__in=orders_in_scope(self.request))

    def get_success_url(self):
        return reverse('procurement:order_detail', args=[self.object.order_id])

    def get_back_url(self):
        return self.get_success_url()


@login_required
@require_POST
def line_delete(request, pk):
    if not can_edit(request.user):
        raise Http404
    line = get_object_or_404(SupplyOrderLine.objects.filter(order__in=orders_in_scope(request)), pk=pk)
    if line.delivery_lines.exists():
        messages.error(request, gettext("This item has already been delivered and cannot be deleted."))
    else:
        line.delete()
        messages.success(request, gettext("The item has been deleted."))
    return redirect('procurement:order_detail', pk=line.order_id)


# ----------------------------------------------------------------------------- deliveries
def _parse_quantity(value):
    value = (value or '').strip().replace(' ', '').replace(',', '.')
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        raise ValidationError(gettext("“%(value)s” is not a valid quantity.") % {'value': value})


@login_required
def delivery_edit(request, order_pk, pk=None):
    if not can_edit(request.user):
        raise Http404
    order = get_object_or_404(orders_in_scope(request), pk=order_pk)
    delivery = get_object_or_404(Delivery, pk=pk, order=order) if pk else Delivery(order=order)
    existing = {line.order_line_id: line for line in delivery.lines.all()} if delivery.pk else {}
    order_lines = list(order.lines.all())
    form = DeliveryForm(request.POST or None, request.FILES or None, instance=delivery)
    errors = []
    items = []
    for line in order_lines:
        current = existing.get(line.pk)
        delivered = request.POST.get(f'delivered_{line.pk}') if request.method == 'POST' else (
            current.quantity_delivered if current else '')
        accepted = request.POST.get(f'accepted_{line.pk}') if request.method == 'POST' else (
            current.quantity_accepted if current and current.quantity_accepted is not None else '')
        remaining = line.remaining + (current.quantity_delivered if current else 0)
        items.append({'line': line, 'delivered': delivered, 'accepted': accepted, 'remaining': remaining})

    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                delivery = form.save(commit=False)
                if delivery.reception_date and not delivery.received_by_id:
                    delivery.received_by = request.user
                delivery.save_and_return_object(request.user)
                saved = 0
                for item in items:
                    line, current = item['line'], existing.get(item['line'].pk)
                    delivered = _parse_quantity(str(item['delivered'] or ''))
                    accepted = _parse_quantity(str(item['accepted'] or ''))
                    if not delivered:
                        if current:
                            current.delete()
                        continue
                    delivery_line = current or DeliveryLine(delivery=delivery, order_line=line)
                    delivery_line.quantity_delivered, delivery_line.quantity_accepted = delivered, accepted
                    try:
                        delivery_line.full_clean(exclude=['delivery'])
                    except ValidationError as error:
                        errors += [f"{line.designation} : {m}" for m in error.messages]
                        continue
                    delivery_line.save()
                    saved += 1
                if not saved and not errors:
                    errors.append(gettext("Enter the delivered quantity of at least one item."))
                if errors:
                    raise ValidationError(errors)
        except ValidationError:
            pass
        else:
            messages.success(request, gettext("The delivery has been saved."))
            return redirect('procurement:order_detail', pk=order.pk)

    return render(request, 'procurement/delivery_form.html', {
        'title': gettext("Edit delivery") if pk else gettext("New delivery"), 'active_level1': ACTIVE,
        'form': form, 'items': items, 'errors': errors, 'order': order,
        'back_url': reverse('procurement:order_detail', args=[order.pk]),
    })


@login_required
@require_POST
def delivery_delete(request, pk):
    if not can_edit(request.user):
        raise Http404
    delivery = get_object_or_404(Delivery.objects.filter(order__in=orders_in_scope(request)), pk=pk)
    order_id = delivery.order_id
    delivery.lines.all().delete()
    delivery.soft_delete(user=request.user)
    messages.success(request, gettext("The delivery has been deleted."))
    return redirect('procurement:order_detail', pk=order_id)
