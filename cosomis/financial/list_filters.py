"""Shared cascading GET-param filters (Project / Funding / Category / Component /
Fund request / Disbursement) reused across the financial app's list views, mirroring
the CLAUDE.md budget hierarchy: each list can be filtered by any level above it.

`apply_entity_filters` takes the ORM lookup path (a string) for each dimension that
applies to the queryset being filtered - callers pass None for dimensions that don't
apply to their model. `build_filter_context` builds the dropdown option lists + the
"show this filter" flags consumed by components/entity_filters.html.
"""


def apply_entity_filters(qs, get, *, project=None, funding=None, category=None,
                          component=None, disbursement_request=None, disbursement=None):
    needs_distinct = False
    if project and get.get('project'):
        qs = qs.filter(**{project: get['project']})
    if funding and get.get('funding'):
        qs = qs.filter(**{funding: get['funding']})
        needs_distinct = True
    if category and get.get('category'):
        qs = qs.filter(**{category: get['category']})
        needs_distinct = True
    if component and get.get('component'):
        qs = qs.filter(**{component: get['component']})
        needs_distinct = True
    if disbursement_request and get.get('disbursement_request'):
        qs = qs.filter(**{disbursement_request: get['disbursement_request']})
    if disbursement and get.get('disbursement'):
        qs = qs.filter(**{disbursement: get['disbursement']})
    if needs_distinct:
        qs = qs.distinct()
    return qs


def build_filter_context(request, *, projects=False, fundings=False, categories=False,
                          components=False, disbursement_requests=False, disbursements=False,
                          bank_transfers=False, account_attrs=False, year=False):
    from subprojects.models import Project, Component, CategoryIDA
    from financial.models.funding import Funding
    from financial.models.financial import BankTransfer, DisbursementRequest, Disbursement
    from financial.models.account import Account

    get = request.GET
    ctx = {}

    ctx['show_project_filter'] = projects
    if projects:
        ctx['filter_projects'] = Project.objects.all().order_by('name')
        ctx['selected_project'] = get.get('project')

    ctx['show_funding_filter'] = fundings
    if fundings:
        ctx['filter_fundings'] = Funding.objects.all().order_by('label')
        ctx['selected_funding'] = get.get('funding')

    ctx['show_category_filter'] = categories
    if categories:
        ctx['filter_categories'] = CategoryIDA.objects.all().order_by('name')
        ctx['selected_category'] = get.get('category')

    ctx['show_component_filter'] = components
    if components:
        ctx['filter_components'] = Component.objects.all().order_by('name')
        ctx['selected_component'] = get.get('component')

    ctx['show_disbursement_request_filter'] = disbursement_requests
    if disbursement_requests:
        ctx['filter_disbursement_requests'] = DisbursementRequest.objects.all().order_by('-requested_date')
        ctx['selected_disbursement_request'] = get.get('disbursement_request')

    ctx['show_disbursement_filter'] = disbursements
    if disbursements:
        ctx['filter_disbursements'] = Disbursement.objects.all().order_by('-disbursement_date')
        ctx['selected_disbursement'] = get.get('disbursement')

    ctx['show_sender_filter'] = bank_transfers
    ctx['show_recipient_filter'] = bank_transfers
    ctx['show_level_filter'] = bank_transfers
    ctx['show_direction_filter'] = bank_transfers
    ctx['show_payment_method_filter'] = bank_transfers
    if bank_transfers:
        ctx['filter_accounts'] = Account.objects.all().order_by('name')
        ctx['selected_sender'] = get.get('sender')
        ctx['selected_recipient'] = get.get('recipient')
        ctx['filter_levels'] = BankTransfer.Level.choices
        ctx['selected_level'] = get.get('level')
        ctx['filter_directions'] = BankTransfer.Direction.choices
        ctx['selected_direction'] = get.get('direction')
        ctx['filter_payment_methods'] = BankTransfer.PaymentMethod.choices
        ctx['selected_payment_method'] = get.get('payment_method')

    ctx['show_account_type_filter'] = account_attrs
    ctx['show_account_category_filter'] = account_attrs
    ctx['show_parent_account_filter'] = account_attrs
    if account_attrs:
        ctx['filter_account_types'] = Account.AccountType.choices
        ctx['selected_account_type'] = get.get('account_type')
        ctx['filter_account_categories'] = Account.AccountCategory.choices
        ctx['selected_account_category'] = get.get('account_category')
        ctx['filter_parent_accounts'] = Account.objects.filter(account_category=Account.AccountCategory.MAIN_ACCOUNT).order_by('name')
        ctx['selected_parent_account'] = get.get('parent')

    ctx['show_year_filter'] = year
    if year:
        ctx['selected_year'] = get.get('year')

    return ctx
