"""Shared aggregation helpers for the financial app's dashboard and detail pages.

Kept in one place so every section (Project IDA, Funding, Category, Component, ...)
computes "requested/validated/disbursed/available" and "budgeted/justified/available"
the exact same way the dashboard does - no drift between the KPI cards and the detail
pages of the objects those KPIs are built from.
"""
from django.db.models import Sum


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


def allocation_cascade_meta():
    """Maps each AdministrativeLevelAllocation id to its owning project id - lets
    the BankTransfer add/edit form narrow the linked_to_allocation select once a
    project is chosen (see bank_transfer_add.html's JS)."""
    from financial.models.allocation import AdministrativeLevelAllocation

    return {
        str(allocation.pk): {'project_id': allocation.project_id}
        for allocation in AdministrativeLevelAllocation.objects.all()
    }


def bank_transfer_cascade_meta():
    """Client-side cascade data for the BankTransfer add/edit form (§2.13): picking
    a disbursement, project or funding must narrow the other two selects down to
    only the values actually linked to it - see bank_transfer_add.html's JS."""
    from financial.models.financial import Disbursement

    disbursement_meta = {}
    for disbursement in Disbursement.objects.select_related(
        'disbursement_request__project', 'disbursement_request__funding'
    ):
        project = disbursement.project
        funding = disbursement.funding
        disbursement_meta[str(disbursement.pk)] = {
            'project_id': project.pk if project else None,
            'funding_id': funding.pk if funding else None,
        }
    return disbursement_meta, funding_cascade_meta()


def component_descendant_ids(component):
    """All descendant Component ids at any depth - a Sous-composante can itself have
    its own Sous-composantes, so a single component_set.all() only reaches one level."""
    ids = []
    for child in component.component_set.all():
        ids.append(child.pk)
        ids.extend(component_descendant_ids(child))
    return ids


def activity_financial_summary(component_ids):
    """Justified-vs-budgeted summary for a set of Component ids (Category/Component detail pages).

    "Disbursed" has no direct meaning at Category/Component level (disbursement happens
    at Funding/DisbursementRequest level) - this is "justified vs budgeted" instead:
    budgeted = sum of effective_amount of the components, justified = sum of
    justified_amount of their activities.
    """
    from financial.models.planning import Activity

    activities_qs = Activity.objects.filter(component_id__in=list(component_ids))
    budgeted = activities_qs.aggregate(total=Sum('amount'))['total'] or 0
    justified = sum((activity.justified_amount or 0) for activity in activities_qs)
    return {
        'activity_count': activities_qs.count(),
        'budgeted_amount': budgeted,
        'justified_amount': justified,
        'available_amount': budgeted - justified,
    }
