import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import generic
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum, Count

from cosomis.mixins import PageMixin
from subprojects.models import Project
from financial.models.account import Account
from financial.models.funding import Funding
from financial.models.financial import BankTransfer, DisbursementRequest, Disbursement
from financial.models.supporting_document import SupportingDocumentActivity
from financial.aggregations import requests_indicators as _requests_indicators
from financial.exports import export_dashboard_report

# Fixed categorical hue order (never cycled/reassigned) - see CLAUDE.md dataviz conventions.
CATEGORICAL_PALETTE = ['#2a78d6', '#1baf7a', '#eda100', '#008300', '#4a3aa7', '#e34948', '#e87ba4', '#eb6834']
STATUS_COLORS = {'good': '#0ca30c', 'warning': '#fab219', 'serious': '#ec835a', 'critical': '#d03b3b'}


class FinancialDashboardView(PageMixin, LoginRequiredMixin, generic.TemplateView):
    """Consolidated dashboard (§2.15/§3 + the "Tableau de bord" and "Soldes des
    comptes" reference sheets), filterable by Project / Funding / Year."""

    template_name = 'financial_dashboard.html'
    title = _('Financial dashboard')
    active_level1 = 'financial'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        project_id = self.request.GET.get('project')
        funding_id = self.request.GET.get('funding')
        year = self.request.GET.get('year')
        account_year = int(year) if year else None

        ctx['projects'] = Project.objects.all().order_by('name')
        ctx['fundings'] = Funding.objects.all().order_by('label')
        ctx['selected_project'] = project_id
        ctx['selected_funding'] = funding_id
        ctx['selected_year'] = year

        # "Demandes de fonds" block: filtered by Project / Funding / Year together.
        requests_qs = DisbursementRequest.objects.all()
        if project_id:
            requests_qs = requests_qs.filter(project_id=project_id)
        if funding_id:
            requests_qs = requests_qs.filter(funding_id=funding_id)
        if year:
            requests_qs = requests_qs.filter(requested_date__year=year)

        ctx['fund_requests'] = _requests_indicators(requests_qs)

        # §"Tableau de bord": "Montant disponible sur le compte du projet" ignores
        # the funding filter (project + year only) - distinct from the funding-scoped
        # figure above, which only makes sense once a funding is actually selected.
        requests_qs_project_only = DisbursementRequest.objects.all()
        if project_id:
            requests_qs_project_only = requests_qs_project_only.filter(project_id=project_id)
        if year:
            requests_qs_project_only = requests_qs_project_only.filter(requested_date__year=year)
        ctx['available_balance_project'] = _requests_indicators(requests_qs_project_only)['available_balance']
        if funding_id:
            selected_funding = Funding.objects.filter(pk=funding_id).first()
            ctx['available_balance_funding'] = (
                (selected_funding.initial_amount or 0) - ctx['fund_requests']['total_disbursed']
                if selected_funding else None
            )
        else:
            ctx['available_balance_funding'] = None

        disbursements_qs = Disbursement.objects.filter(disbursement_request__in=requests_qs)
        total_disbursed = ctx['fund_requests']['total_disbursed']
        total_justified = SupportingDocumentActivity.objects.filter(
            supporting_document__disbursement__in=disbursements_qs
        ).aggregate(total=Sum('allocated_amount'))['total'] or 0

        ctx['disbursements'] = {
            'count': disbursements_qs.count(),
            'total_disbursed': total_disbursed,
            'total_justified': total_justified,
            'justification_gap': total_disbursed - total_justified,
        }

        transfers_qs = BankTransfer.objects.all()
        if year:
            transfers_qs = transfers_qs.filter(transfer_date__year=year)

        transfers_by_status = dict(
            transfers_qs.values_list('status').annotate(total=Count('id'))
        )
        ctx['bank_transfers'] = {
            'count': transfers_qs.count(),
            'total_transferred': transfers_qs.aggregate(total=Sum('amount_transferred'))['total'] or 0,
            'executed': transfers_by_status.get(BankTransfer.Status.EXECUTED, 0),
            'pending': transfers_by_status.get(BankTransfer.Status.PENDING, 0),
            'cancelled': transfers_by_status.get(BankTransfer.Status.CANCELLED, 0),
        }

        # -- §"Soldes des comptes": full breakdown per actor (Antennes, Mairies, CVD,
        # Spécialistes, Entreprises), filterable by year -------------------------

        actor_types = [
            Account.AccountType.REGIONAL_OFFICE,
            Account.AccountType.TOWN_HALL,
            Account.AccountType.CVD,
            Account.AccountType.PROJECT_SPECIALIST,
            Account.AccountType.SERVICE_PROVIDER,
        ]
        accounts = Account.objects.filter(account_type__in=actor_types)
        account_balances = [
            {'account': account, **account.balance_breakdown(year=account_year)}
            for account in accounts
        ]
        ctx['account_balances'] = account_balances

        # -- §"Montant actuellement disponible ... par projet IDA" ------------------

        project_breakdown = []
        for project in ctx['projects']:
            project_requests_qs = DisbursementRequest.objects.filter(project=project)
            if year:
                project_requests_qs = project_requests_qs.filter(requested_date__year=year)
            indicators = _requests_indicators(project_requests_qs)
            project_breakdown.append({
                'project': project,
                'total_amount': project.total_amount,
                **indicators,
            })
        ctx['project_breakdown'] = project_breakdown

        # -- §"... pour le crédit et le don ... par projet IDA, crédit, don" --------

        fundings_qs = Funding.objects.all()
        if project_id:
            fundings_qs = fundings_qs.filter(project_id=project_id)
        funding_breakdown = []
        for funding in fundings_qs:
            funding_requests_qs = DisbursementRequest.objects.filter(funding=funding)
            if year:
                funding_requests_qs = funding_requests_qs.filter(requested_date__year=year)
            indicators = _requests_indicators(funding_requests_qs)
            # "Montant actuellement disponible" for a Crédit/Don = initial amount minus
            # what's been disbursed - not validated-minus-disbursed (see Funding.available_balance).
            indicators['available_balance'] = (funding.initial_amount or 0) - indicators['total_disbursed']
            funding_breakdown.append({
                'funding': funding,
                **indicators,
            })
        ctx['funding_breakdown'] = funding_breakdown

        # -- Chart-ready data (Chart.js v2, see CLAUDE.md dataviz conventions) -----

        ctx['chart_fund_requests'] = json.dumps({
            'labels': [str(_('Requested')), str(_('Validated')), str(_('Disbursed'))],
            'data': [ctx['fund_requests']['total_requested'], ctx['fund_requests']['total_validated'], total_disbursed],
            'colors': CATEGORICAL_PALETTE[:3],
        })

        transfer_status_labels = [str(_('Pending')), str(_('Executed')), str(_('Cancelled'))]
        transfer_status_data = [
            ctx['bank_transfers']['pending'],
            ctx['bank_transfers']['executed'],
            ctx['bank_transfers']['cancelled'],
        ]
        ctx['chart_bank_transfers_status'] = json.dumps({
            'labels': transfer_status_labels,
            'data': transfer_status_data,
            'colors': [STATUS_COLORS['warning'], STATUS_COLORS['good'], STATUS_COLORS['critical']],
        })

        balances_by_type = {}
        for row in account_balances:
            label = row['account'].get_account_type_display()
            balances_by_type[label] = balances_by_type.get(label, 0) + row['available_balance']
        ctx['chart_balances_by_type'] = json.dumps({
            'labels': list(balances_by_type.keys()),
            'data': list(balances_by_type.values()),
            'colors': CATEGORICAL_PALETTE[:len(balances_by_type)],
        })

        ctx['chart_project_breakdown'] = json.dumps({
            'labels': [row['project'].name for row in project_breakdown],
            'data': [row['available_balance'] for row in project_breakdown],
            'colors': CATEGORICAL_PALETTE[:max(len(project_breakdown), 1)],
        })

        ctx['chart_funding_breakdown'] = json.dumps({
            'labels': [str(f['funding']) for f in funding_breakdown],
            'data': [f['available_balance'] for f in funding_breakdown],
            'colors': [
                CATEGORICAL_PALETTE[0] if f['funding'].funding_type == Funding.FundingType.CREDIT else CATEGORICAL_PALETTE[1]
                for f in funding_breakdown
            ],
        })

        return ctx


class FinancialDashboardExportView(PageMixin, LoginRequiredMixin, generic.View):
    """Consolidated 'rapport de situation fiduciaire' - reuses FinancialDashboardView's
    own aggregation so the export can never drift from what the dashboard page shows."""

    def get(self, request, *args, **kwargs):
        dashboard_view = FinancialDashboardView()
        dashboard_view.request = request
        dashboard_view.kwargs = kwargs
        ctx = dashboard_view.get_context_data()
        return export_dashboard_report(ctx)
