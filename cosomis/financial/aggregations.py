"""Shared aggregation helpers for the financial app's dashboard and detail pages.

Kept in one place so every section (Project IDA, Funding, Category, Component, ...)
computes "requested/validated/disbursed/available" and "budgeted/justified/available"
the exact same way the dashboard does - no drift between the KPI cards and the detail
pages of the objects those KPIs are built from.
"""
import re

from django.db.models import Sum

_NATURAL_SORT_SPLIT_RE = re.compile(r'(\d+)')


def natural_sort_key(text):
    """Sort key so "Composante 1", "1.1", "1.2", "1.2a", "1.2b", "2", "10" compare
    in the order a human expects (digit runs compared numerically, not lexically -
    plain string sort would put "10" before "2"). Every token is tagged (0, int) or
    (1, str) so comparing two keys of different shapes never raises a TypeError from
    Python comparing an int to a str mid-list."""
    text = str(text or '')
    parts = _NATURAL_SORT_SPLIT_RE.split(text)
    return [(0, int(part)) if part.isdigit() else (1, part.lower()) for part in parts]


def activity_sort_key(activity):
    """Order PTBA activities by their component's name (natural order) then by
    their own code - matches how the reference workbook numbers activities under
    each component."""
    component_name = activity.component.name if activity.component_id else ''
    return (natural_sort_key(component_name), natural_sort_key(activity.code))


def requests_indicators(requests_qs):
    """Aggregate a DisbursementRequest queryset into the KPI dict used across the app."""
    from financial.models.financial import Disbursement, DisbursementRequestValidation

    disbursements_qs = Disbursement.objects.filter(disbursement_request__in=requests_qs)
    total_requested = requests_qs.aggregate(total=Sum('amount_requested'))['total'] or 0
    # amount_validated is computed from DisbursementRequestValidation (never stored
    # directly), so it's summed here via the validation rows rather than via
    # requests_qs.aggregate(Sum('amount_validated')).
    total_validated = DisbursementRequestValidation.objects.filter(
        disbursement_request__in=requests_qs
    ).aggregate(total=Sum('amount_validated'))['total'] or 0
    total_disbursed = disbursements_qs.aggregate(total=Sum('amount_disbursed'))['total'] or 0
    return {
        'count': requests_qs.count(),
        'total_requested': total_requested,
        'total_validated': total_validated,
        'validation_rate': (total_validated / total_requested) if total_requested else 0,
        'total_disbursed': total_disbursed,
        'available_balance': total_validated - total_disbursed,
    }


def component_cascade_meta():
    """Maps each Component id (any level - Composante or Sous-composante) to its
    owning project id - lets the Allocation add/edit form narrow the component
    select once a project is chosen (see allocation_add.html's JS)."""
    from subprojects.models import Component

    return {
        str(component.pk): {'project_id': component.project_id}
        for component in Component.objects.all()
    }


def category_cascade_meta():
    """Maps each CategoryIDA id to its owning project id - lets the top-level
    Composante add/edit form narrow the funding select once a category is chosen
    (see component_add.html's JS)."""
    from subprojects.models import CategoryIDA

    return {
        str(category.pk): {'project_id': category.project_id}
        for category in CategoryIDA.objects.all()
    }


def funding_cascade_meta():
    """Maps each Funding id to its (single) owning project id - shared by every
    add/edit form that lets the user pick both a project and a funding."""
    from financial.models.funding import Funding

    return {
        str(funding.pk): {'project_id': funding.project_id}
        for funding in Funding.objects.all()
    }


def component_descendant_ids(component):
    """All descendant Component ids at any depth - a Sous-composante can itself have
    its own Sous-composantes, so a single component_set.all() only reaches one level."""
    ids = []
    for child in component.component_set.all():
        ids.append(child.pk)
        ids.extend(component_descendant_ids(child))
    return ids


def component_financial_breakdown(component):
    """Per-row PTBA-planning breakdown for a single Composante/Sous-composante
    (Composantes/Sous-composantes tables on the Project IDA / Category / Funding /
    Component detail pages) - includes the component's own activities plus every
    descendant's, mirroring how Component.effective_amount itself cascades."""
    component_ids = [component.pk] + component_descendant_ids(component)
    summary = activity_financial_summary(component_ids)
    effective = component.effective_amount or 0
    return {
        'planned_amount': summary['budgeted_amount'],
        'available_vs_plan': effective - summary['budgeted_amount'],
        'justified_amount': summary['justified_amount'],
        'available_vs_justified': effective - summary['justified_amount'],
    }


def activity_financial_summary(component_ids):
    """Justified-vs-budgeted summary for a set of Component ids (Category/Component detail pages).

    "Disbursed" has no direct meaning at Category/Component level (disbursement happens
    at Funding/DisbursementRequest level) - this is "justified vs budgeted" instead:
    budgeted = sum of effective_amount of the components, justified = sum of
    justified_amount of their activities.
    """
    from financial.models.planning import Activity

    activities_qs = Activity.objects.filter(component_id__in=list(component_ids))
    # Only top-level activities: a parent's effective_amount already cumulates
    # its children's, so summing every row would double-count them.
    budgeted = sum((activity.effective_amount or 0) for activity in activities_qs.filter(parent__isnull=True))
    justified = sum((activity.justified_amount or 0) for activity in activities_qs)
    return {
        'activity_count': activities_qs.count(),
        'budgeted_amount': budgeted,
        'justified_amount': justified,
        'available_amount': budgeted - justified,
    }
