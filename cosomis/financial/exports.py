"""Excel (.xlsx) export helpers for the financial app.

Column headers mirror financial/management/commands/import_disbursement_workbook.py
(the authoritative column-name mapping for the reference workbook), so an export
stays plausible as a re-import. One `build_<x>_sheet` function per sheet, reused
both by the plain per-section "Exporter" views and by the consolidated
Project-IDA / dashboard workbooks - never duplicated.
"""
from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter


def _new_sheet(workbook, title, headers):
    if workbook.worksheets and workbook.active.max_row == 1 and workbook.active.max_column == 1 and workbook.active['A1'].value is None:
        ws = workbook.active
        ws.title = title[:31]
    else:
        ws = workbook.create_sheet(title=title[:31])
    ws.append(headers)
    for col_idx in range(1, len(headers) + 1):
        ws.cell(row=1, column=col_idx).font = Font(bold=True)
        ws.column_dimensions[get_column_letter(col_idx)].width = 22
    return ws


def workbook_response(workbook, filename):
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    workbook.save(response)
    return response


# -- per-sheet builders -------------------------------------------------------

def build_project_ida_sheet(workbook, queryset):
    ws = _new_sheet(workbook, 'Projets IDA', ['ID_ProjetIDA', 'Nom du Projet IDA', 'Description', 'Statut', 'Montant total (auto)'])
    for project in queryset:
        ws.append([project.external_id or '', project.name, project.description, project.get_status_display(), project.total_amount])
    return ws


def build_funding_sheet(workbook, queryset):
    ws = _new_sheet(workbook, 'Crédits & Dons', [
        'ID_CréditDon', 'Type', "N° d'identification IDA", 'ID_ProjetIDA', 'Libellé / Objet', 'Montant initial', 'Observations',
    ])
    for funding in queryset:
        ws.append([
            funding.external_id or '', funding.get_funding_type_display(), funding.identification_number,
            funding.project.name, funding.label, funding.initial_amount, funding.notes,
        ])
    return ws


def build_category_sheet(workbook, queryset):
    ws = _new_sheet(workbook, 'Catégories', ['ID_Catégorie', 'ID_ProjetIDA', 'Libellé', 'Montant (auto)', 'Cible(s)'])
    for category in queryset:
        ws.append([
            category.external_id or '', category.project.name if category.project_id else '', category.name,
            category.effective_amount, category.target,
        ])
    return ws


def build_component_sheet(workbook, queryset, sheet_title='Composantes'):
    ws = _new_sheet(workbook, sheet_title, [
        'ID_Composante', 'ID_ProjetIDA', 'ID_Catégorie', 'Libellé', 'ID_CréditDon', 'Montant alloué', 'Cible(s)', 'Montant effectif (auto)',
    ])
    for component in queryset:
        ws.append([
            component.external_id or '',
            component.project.name if component.project_id else '',
            component.category.name if component.category_id else '',
            component.name,
            component.funding.label if component.funding_id else '',
            component.amount,
            component.target,
            component.effective_amount,
        ])
    return ws


def build_annual_work_plan_sheet(workbook, queryset):
    ws = _new_sheet(workbook, 'PTBA', ['ID_PTBA', 'ID_ProjetIDA', 'Année / Période', 'Libellé', 'Montant budgétisé (auto)', 'Observations'])
    for plan in queryset:
        ws.append([plan.external_id or '', plan.project.name, plan.period, plan.name, plan.budgeted_amount, plan.notes])
    return ws


def build_activity_sheet(workbook, queryset):
    ws = _new_sheet(workbook, 'Activités', [
        'ID_Activité', 'ID_Composante', 'ID_SousComposante', 'ID_PTBA', 'Libellé', 'Montant', 'Cible(s)',
        'Montant justifié (auto)', 'Solde à justifier (auto)',
    ])
    for activity in queryset:
        is_sub_component = activity.component.parent_id is not None
        ws.append([
            activity.external_id or '',
            '' if is_sub_component else activity.component.name,
            activity.component.name if is_sub_component else '',
            activity.annual_work_plan.name,
            activity.name,
            activity.amount, activity.target, activity.justified_amount, activity.balance_to_justify,
        ])
    return ws


def build_supporting_document_sheet(workbook, queryset):
    ws = _new_sheet(workbook, 'Justificatifs', [
        'ID_Justificatif', 'ID_Décaissement lié', 'ID_Demande liée', 'Type de pièce', 'Référence de la pièce',
        'Date de la pièce', 'Montant total justifié (auto)', 'Lien / Emplacement du fichier', 'Observations',
    ])
    for doc in queryset:
        ws.append([
            doc.external_id or '',
            str(doc.disbursement) if doc.disbursement_id else '',
            str(doc.disbursement_request) if doc.disbursement_request_id else '',
            doc.get_document_type_display(), doc.reference, doc.document_date,
            doc.total_justified_amount, doc.file_name or (doc.file.name if doc.file else ''), doc.notes,
        ])
    return ws


def build_supporting_document_activity_sheet(workbook, queryset):
    ws = _new_sheet(workbook, 'Justificatifs-Activités', ['ID_Ligne', 'ID_Justificatif', 'ID_Activité', 'Montant imputé', 'Observations'])
    for line in queryset:
        ws.append([line.external_id or '', str(line.supporting_document), str(line.activity), line.allocated_amount, line.notes])
    return ws


def build_disbursement_request_sheet(workbook, queryset):
    ws = _new_sheet(workbook, 'Demandes de fonds', [
        'ID_Demande', 'ID_ProjetIDA', 'Type (Crédit/Don)', 'ID_CréditDon', 'Date demande', 'Montant demandé',
        'Montant demandé (USD)', 'Motif', 'Description', 'Date de première réponse', 'Commentaire lié à la réponse',
        'Statut (manuel, si aucune validation)', 'Montant validé (auto)', 'Statut affiché (auto)',
        'Total décaissé (auto)', 'Solde disponible (auto)', 'Année (auto)',
    ])
    for req in queryset:
        ws.append([
            req.external_id or '', req.project.name, req.get_funding_type_display() if req.funding_type else '',
            req.funding.label if req.funding_id else '', req.requested_date, req.amount_requested,
            req.amount_requested_in_dollars, req.motif, req.description, req.first_response_date,
            req.comment_linked_to_reply, req.get_status_display(), req.amount_validated, req.get_status_display(),
            req.total_disbursed, req.available_balance, req.year,
        ])
    return ws


def build_disbursement_request_validation_sheet(workbook, queryset):
    ws = _new_sheet(workbook, 'Validations des demandes', [
        'ID_Validation', 'ID_Demande liée', 'Date de validation', 'Montant validé (ce tour)',
        'Statut après cette validation', 'Commentaire',
    ])
    for validation in queryset:
        ws.append([
            validation.external_id or '', str(validation.disbursement_request), validation.validation_date,
            validation.amount_validated, validation.get_status_after_display(), validation.comment,
        ])
    return ws


def build_disbursement_sheet(workbook, queryset):
    ws = _new_sheet(workbook, 'Décaissements', [
        'ID_Décaissement', 'ID_Demande liée', 'Montant décaissé', 'Date du décaissement',
        'Motif / Objet de la dépense', 'Montant justifié (auto)', 'Écart à justifier (auto)',
        'Statut de justification', 'Observations',
    ])
    for disb in queryset:
        ws.append([
            disb.external_id or '', str(disb.disbursement_request), disb.amount_disbursed, disb.disbursement_date,
            disb.description, disb.justified_amount, disb.justification_gap, disb.get_justification_status_display(), disb.notes,
        ])
    return ws


def build_account_sheet(workbook, queryset):
    ws = _new_sheet(workbook, 'Acteurs & Comptes', [
        'ID_Acteur', 'Nom de l\'acteur', 'Type d\'acteur', 'Catégorie de compte', 'Compte parent',
        'N° de compte', 'Contact', 'Statut / Observations',
    ])
    for account in queryset:
        ws.append([
            account.external_id or '', account.name, account.get_account_type_display(), account.get_account_category_display(),
            account.parent.name if account.parent_id else '', account.account_number, account.contact, account.notes,
        ])
    return ws


def build_bank_transfer_sheet(workbook, queryset):
    ws = _new_sheet(workbook, 'Virements', [
        'ID_Virement', 'Émetteur', 'Bénéficiaire', 'Niveau', 'Montant', 'Date du virement', 'Motif / Référence',
        'Mode de paiement', 'Sens du virement', 'Statut', 'ID_ProjetIDA', 'ID_CréditDon',
        'Pièces justificatives', 'Décaissement lié', 'Observations', 'Année (auto)',
    ])
    for transfer in queryset:
        ws.append([
            transfer.external_id or '', transfer.sender.name if transfer.sender_id else '', transfer.recipient.name if transfer.recipient_id else '',
            transfer.get_level_display() if transfer.level else '', transfer.amount_transferred, transfer.transfer_date, transfer.motif,
            transfer.get_payment_method_display(), transfer.get_direction_display(), transfer.get_status_display(),
            transfer.project.external_id or transfer.project.name if transfer.project_id else '',
            transfer.funding.external_id or transfer.funding.label if transfer.funding_id else '',
            ', '.join(str(doc) for doc in transfer.supporting_documents.all()),
            str(transfer.disbursement) if transfer.disbursement_id else '',
            transfer.description, transfer.year,
        ])
    return ws


# -- per-section export entry points ------------------------------------------

def export_project_ida(queryset):
    wb = Workbook()
    build_project_ida_sheet(wb, queryset)
    return workbook_response(wb, 'projets_ida.xlsx')


def export_funding(queryset):
    wb = Workbook()
    build_funding_sheet(wb, queryset)
    return workbook_response(wb, 'credits_dons.xlsx')


def export_category(queryset):
    wb = Workbook()
    build_category_sheet(wb, queryset)
    return workbook_response(wb, 'categories.xlsx')


def export_component(queryset):
    wb = Workbook()
    build_component_sheet(wb, queryset)
    return workbook_response(wb, 'composantes.xlsx')


def export_annual_work_plan(queryset):
    from financial.models.planning import Activity

    wb = Workbook()
    build_annual_work_plan_sheet(wb, queryset)
    build_activity_sheet(wb, Activity.objects.filter(annual_work_plan__in=queryset))
    return workbook_response(wb, 'ptba.xlsx')


def export_supporting_document(queryset):
    from financial.models.supporting_document import SupportingDocumentActivity

    wb = Workbook()
    build_supporting_document_sheet(wb, queryset)
    build_supporting_document_activity_sheet(wb, SupportingDocumentActivity.objects.filter(supporting_document__in=queryset))
    return workbook_response(wb, 'justificatifs.xlsx')


def export_account(queryset):
    wb = Workbook()
    build_account_sheet(wb, queryset)
    return workbook_response(wb, 'comptes.xlsx')


def export_disbursement_request(queryset):
    from financial.models.financial import DisbursementRequestValidation

    wb = Workbook()
    build_disbursement_request_sheet(wb, queryset)
    build_disbursement_request_validation_sheet(wb, DisbursementRequestValidation.objects.filter(disbursement_request__in=queryset))
    return workbook_response(wb, 'demandes_de_fonds.xlsx')


def export_disbursement(queryset):
    wb = Workbook()
    build_disbursement_sheet(wb, queryset)
    return workbook_response(wb, 'decaissements.xlsx')


def export_bank_transfer(queryset):
    wb = Workbook()
    build_bank_transfer_sheet(wb, queryset)
    return workbook_response(wb, 'virements.xlsx')


def build_allocation_sheet(workbook, queryset):
    ws = _new_sheet(workbook, 'Allocations', [
        'Niveau administratif', 'CVD', 'Projet', 'Composante', 'Montant alloué', 'Montant alloué (USD)',
        "Date d'allocation", 'Montant après signature de contrat(s)', 'Montant après signature de contrat(s) (USD)',
        "Date d'allocation après signature de contrat(s)", 'Description',
    ])
    for allocation in queryset:
        ws.append([
            allocation.administrative_level.name if allocation.administrative_level_id else '',
            allocation.cvd.name if allocation.cvd_id else '',
            allocation.project.name, str(allocation.component) if allocation.component_id else '',
            allocation.amount, allocation.amount_in_dollars, allocation.allocation_date,
            allocation.amount_after_signature_of_contracts, allocation.amount_in_dollars_after_signature_of_contracts,
            allocation.allocation_date_after_signature_of_contracts, allocation.description,
        ])
    return ws


def export_allocation(queryset):
    wb = Workbook()
    build_allocation_sheet(wb, queryset)
    return workbook_response(wb, 'allocations.xlsx')


def export_project_ida_detail(project):
    from django.db.models import Q
    from financial.models.funding import Funding
    from financial.models.planning import AnnualWorkPlan, Activity
    from financial.models.financial import DisbursementRequest, DisbursementRequestValidation, Disbursement, BankTransfer
    from financial.models.supporting_document import SupportingDocument, SupportingDocumentActivity
    from subprojects.models import CategoryIDA, Component

    wb = Workbook()
    build_project_ida_sheet(wb, [project])
    fundings = Funding.objects.filter(project=project)
    build_funding_sheet(wb, fundings)
    build_category_sheet(wb, CategoryIDA.objects.filter(project=project))
    components = Component.objects.filter(project=project)
    build_component_sheet(wb, components.filter(parent__isnull=True), 'Composantes')
    build_component_sheet(wb, components.filter(parent__isnull=False), 'Sous-composantes')
    plans = AnnualWorkPlan.objects.filter(project=project)
    build_annual_work_plan_sheet(wb, plans)
    build_activity_sheet(wb, Activity.objects.filter(annual_work_plan__in=plans))
    requests_qs = DisbursementRequest.objects.filter(project=project)
    build_disbursement_request_sheet(wb, requests_qs)
    build_disbursement_request_validation_sheet(wb, DisbursementRequestValidation.objects.filter(disbursement_request__in=requests_qs))
    build_disbursement_sheet(wb, Disbursement.objects.filter(disbursement_request__project=project))
    documents_qs = SupportingDocument.objects.filter(
        Q(disbursement__disbursement_request__project=project) | Q(disbursement_request__project=project)
    ).distinct()
    build_supporting_document_sheet(wb, documents_qs)
    build_supporting_document_activity_sheet(wb, SupportingDocumentActivity.objects.filter(supporting_document__in=documents_qs))
    build_bank_transfer_sheet(wb, BankTransfer.objects.filter(project=project))
    return workbook_response(wb, f'projet_ida_{project.pk}.xlsx')


def export_dashboard_report(ctx):
    """Consolidated 'rapport de situation fiduciaire' - every sheet plus a KPI summary,
    respecting whatever project/funding/year filters produced `ctx` (see
    financial.views_dashboard.build_dashboard_context)."""
    from financial.models.funding import Funding
    from financial.models.financial import DisbursementRequest, DisbursementRequestValidation, Disbursement, BankTransfer
    from subprojects.models import Project

    wb = Workbook()
    build_project_ida_sheet(wb, Project.objects.all())
    build_funding_sheet(wb, Funding.objects.all())

    requests_qs = DisbursementRequest.objects.all()
    if ctx.get('selected_project'):
        requests_qs = requests_qs.filter(project_id=ctx['selected_project'])
    if ctx.get('selected_funding'):
        requests_qs = requests_qs.filter(funding_id=ctx['selected_funding'])
    if ctx.get('selected_year'):
        requests_qs = requests_qs.filter(requested_date__year=ctx['selected_year'])
    build_disbursement_request_sheet(wb, requests_qs)
    build_disbursement_request_validation_sheet(wb, DisbursementRequestValidation.objects.filter(disbursement_request__in=requests_qs))
    build_disbursement_sheet(wb, Disbursement.objects.filter(disbursement_request__in=requests_qs))

    transfers_qs = BankTransfer.objects.all()
    if ctx.get('selected_year'):
        transfers_qs = transfers_qs.filter(transfer_date__year=ctx['selected_year'])
    build_bank_transfer_sheet(wb, transfers_qs)

    summary_ws = _new_sheet(wb, 'Tableau de bord', ['Indicateur', 'Valeur'])
    summary_rows = [
        ('Nombre de demandes de fonds', ctx['fund_requests']['count']),
        ('Total demandé', ctx['fund_requests']['total_requested']),
        ('Total validé', ctx['fund_requests']['total_validated']),
        ('Taux de validation', ctx['fund_requests']['validation_rate']),
        ('Total décaissé', ctx['fund_requests']['total_disbursed']),
        ('Solde disponible (demandes)', ctx['fund_requests']['available_balance']),
        ('Solde disponible du projet', ctx.get('available_balance_project')),
        ('Nombre de décaissements', ctx['disbursements']['count']),
        ('Total décaissé (décaissements)', ctx['disbursements']['total_disbursed']),
        ('Total justifié', ctx['disbursements']['total_justified']),
        ('Écart à justifier', ctx['disbursements']['justification_gap']),
        ('Nombre de virements', ctx['bank_transfers']['count']),
        ('Total viré', ctx['bank_transfers']['total_transferred']),
        ('Virements exécutés', ctx['bank_transfers']['executed']),
        ('Virements en attente', ctx['bank_transfers']['pending']),
        ('Virements annulés', ctx['bank_transfers']['cancelled']),
    ]
    for row in summary_rows:
        summary_ws.append(row)

    return workbook_response(wb, 'rapport_situation_fiduciaire.xlsx')
