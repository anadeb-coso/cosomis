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
        'ID_Composante', 'ID_ProjetIDA', 'ID_Catégorie', 'Libellé', 'Montant alloué', 'Cible(s)', 'Montant effectif (auto)',
    ])
    for component in queryset:
        ws.append([
            component.external_id or '',
            component.project.name if component.project_id else '',
            component.category.name if component.category_id else '',
            component.name,
            component.amount,
            component.target,
            component.effective_amount,
        ])
    return ws


def build_component_funding_sheet(workbook, queryset, component_id_col, sheet_title):
    """Composantes-CréditDon / Sous-composantes-CréditDon: a component can be linked
    to several Crédits & Dons, so its funding is a M2M shown as one row per link
    rather than a column on the Composantes/Sous-composantes sheet itself."""
    ws = _new_sheet(workbook, sheet_title, ['ID_Lien', component_id_col, 'ID_CréditDon'])
    idx = 1
    for component in queryset:
        for funding in component.fundings.all():
            ws.append([idx, component.external_id or component.name, funding.external_id or funding.label])
            idx += 1
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
        'ID_Justificatif', 'ID_Décaissement lié', 'ID_Demande liée', 'Référence de la DRF',
        'Date de la DRF', 'Montant total justifié (auto)', 'Observations',
    ])
    for doc in queryset:
        ws.append([
            doc.external_id or '',
            str(doc.disbursement) if doc.disbursement_id else '',
            str(doc.disbursement_request) if doc.disbursement_request_id else '',
            doc.reference, doc.document_date,
            doc.total_justified_amount, doc.notes,
        ])
    for col_idx in range(1, len(ws[1]) + 1):
        if ws.cell(row=1, column=col_idx).value == 'Date de la DRF':
            for row_idx in range(2, ws.max_row + 1):
                ws.cell(row=row_idx, column=col_idx).number_format = 'YYYY-MM-DD'
    return ws


def build_supporting_document_activity_sheet(workbook, queryset):
    ws = _new_sheet(workbook, 'Justificatifs-Activités', ['ID_Ligne', 'ID_Justificatif', 'ID_Activité', 'Montant imputé', 'Observations'])
    for line in queryset:
        ws.append([line.external_id or '', str(line.supporting_document), str(line.activity), line.allocated_amount, line.notes])
    return ws


def build_supporting_document_activity_file_sheet(workbook, queryset):
    """Fichiers justif. Activités: a Justificatif-Activité line can carry several
    files, each with its own document type - moved off SupportingDocument itself."""
    ws = _new_sheet(workbook, 'Fichiers justif. Activités', [
        'ID_Fichier', 'ID_JustifActivité liée', 'Type de pièce', 'Lien / Emplacement du fichier',
    ])
    for file in queryset:
        ws.append([
            file.external_id or '', str(file.supporting_document_activity),
            file.get_document_type_display(), file.file_name or (file.file.name if file.file else ''),
        ])
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
            disb.description, disb.justified_amount, disb.justification_gap, str(disb.get_justification_status_display), disb.notes,
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
        'Mode de paiement', 'Sens du virement', 'ID_ProjetIDA (auto)', 'ID_CréditDon (auto)',
        'Pièces justificatives', 'Observations', 'Année (auto)',
    ])
    for transfer in queryset:
        project = transfer.project
        funding = transfer.funding
        ws.append([
            transfer.external_id or '', transfer.sender.name if transfer.sender_id else '', transfer.recipient.name if transfer.recipient_id else '',
            transfer.get_level_display() if transfer.level else '', transfer.amount_transferred, transfer.transfer_date, transfer.motif,
            transfer.get_payment_method_display(), transfer.get_direction_display(),
            (project.external_id or project.name) if project else '',
            (funding.external_id or funding.label) if funding else '',
            ', '.join(str(doc) for doc in transfer.supporting_documents.all()),
            transfer.description, transfer.year,
        ])
    return ws


def build_bank_transfer_disbursement_sheet(workbook, queryset):
    """Virements-Décaissements: a transfer can be linked to several disbursements,
    each shown as one row rather than a single 'Décaissement lié' column."""
    ws = _new_sheet(workbook, 'Virements-Décaissements', ['ID_Lien', 'ID_Virement', 'ID_Décaissement', 'Observations'])
    idx = 1
    for transfer in queryset:
        for disbursement in transfer.disbursements.all():
            ws.append([idx, transfer.external_id or str(transfer.pk), disbursement.external_id or str(disbursement.pk), ''])
            idx += 1
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
    build_component_funding_sheet(wb, queryset.filter(parent__isnull=True), 'ID_Composante', 'Composantes-CréditDon')
    build_component_funding_sheet(wb, queryset.filter(parent__isnull=False), 'ID_SousComposante', 'Sous-composantes-CréditDon')
    return workbook_response(wb, 'composantes.xlsx')


def export_annual_work_plan(queryset):
    from financial.models.planning import Activity

    wb = Workbook()
    build_annual_work_plan_sheet(wb, queryset)
    build_activity_sheet(wb, Activity.objects.filter(annual_work_plan__in=queryset))
    return workbook_response(wb, 'ptba.xlsx')


def export_supporting_document(queryset):
    from financial.models.supporting_document import SupportingDocumentActivity, SupportingDocumentActivityFile

    wb = Workbook()
    build_supporting_document_sheet(wb, queryset)
    lines = SupportingDocumentActivity.objects.filter(supporting_document__in=queryset)
    build_supporting_document_activity_sheet(wb, lines)
    build_supporting_document_activity_file_sheet(wb, SupportingDocumentActivityFile.objects.filter(supporting_document_activity__in=lines))
    return workbook_response(wb, 'justificatifs.xlsx')


def export_account(queryset):
    wb = Workbook()
    build_account_sheet(wb, queryset)
    return workbook_response(wb, 'comptes.xlsx')


def build_bank_sheet(workbook, queryset):
    ws = _new_sheet(workbook, 'Banques', [
        'Nom', 'Abréviation', 'Nombre de comptes', 'Description',
    ])
    for bank in queryset:
        ws.append([
            bank.name, bank.abbreviation, bank.accounts_count, bank.description,
        ])
    return ws


def export_bank(queryset):
    wb = Workbook()
    build_bank_sheet(wb, queryset)
    return workbook_response(wb, 'banques.xlsx')


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
    build_bank_transfer_disbursement_sheet(wb, queryset)
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
    from financial.models.supporting_document import SupportingDocument, SupportingDocumentActivity, SupportingDocumentActivityFile
    from subprojects.models import CategoryIDA, Component

    wb = Workbook()
    build_project_ida_sheet(wb, [project])
    fundings = Funding.objects.filter(project=project)
    build_funding_sheet(wb, fundings)
    build_category_sheet(wb, CategoryIDA.objects.filter(project=project))
    components = Component.objects.filter(project=project)
    top_components = components.filter(parent__isnull=True)
    sub_components = components.filter(parent__isnull=False)
    build_component_sheet(wb, top_components, 'Composantes')
    build_component_sheet(wb, sub_components, 'Sous-composantes')
    build_component_funding_sheet(wb, top_components, 'ID_Composante', 'Composantes-CréditDon')
    build_component_funding_sheet(wb, sub_components, 'ID_SousComposante', 'Sous-composantes-CréditDon')
    plans = AnnualWorkPlan.objects.filter(project=project)
    build_annual_work_plan_sheet(wb, plans)
    build_activity_sheet(wb, Activity.objects.filter(annual_work_plan__in=plans))
    requests_qs = DisbursementRequest.objects.filter(project=project)
    build_disbursement_request_sheet(wb, requests_qs)
    build_disbursement_request_validation_sheet(wb, DisbursementRequestValidation.objects.filter(disbursement_request__in=requests_qs))
    disbursements_qs = Disbursement.objects.filter(disbursement_request__project=project)
    build_disbursement_sheet(wb, disbursements_qs)
    documents_qs = SupportingDocument.objects.filter(
        Q(disbursement__disbursement_request__project=project) | Q(disbursement_request__project=project)
    ).distinct()
    lines_qs = SupportingDocumentActivity.objects.filter(supporting_document__in=documents_qs)
    build_supporting_document_sheet(wb, documents_qs)
    build_supporting_document_activity_sheet(wb, lines_qs)
    build_supporting_document_activity_file_sheet(wb, SupportingDocumentActivityFile.objects.filter(supporting_document_activity__in=lines_qs))
    transfers_qs = BankTransfer.objects.filter(disbursements__in=disbursements_qs).distinct()
    build_bank_transfer_sheet(wb, transfers_qs)
    build_bank_transfer_disbursement_sheet(wb, transfers_qs)
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
    build_bank_transfer_disbursement_sheet(wb, transfers_qs)

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
    ]
    for row in summary_rows:
        summary_ws.append(row)

    return workbook_response(wb, 'rapport_situation_fiduciaire.xlsx')
