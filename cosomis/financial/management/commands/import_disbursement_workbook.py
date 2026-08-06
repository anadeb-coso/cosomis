"""
Import the reference workbook (context/202608061408_suivi_decaissements_virements.xlsx,
see CLAUDE.md §2 and §6) into the disbursement/bank-transfer tracking models.

This command was written from the column mapping documented in CLAUDE.md (the workbook
itself is not checked into the repository - see the .gitignore entry for `context/`), so
sheet/column names are matched defensively (several candidate spellings per column,
normalized for accents/case/whitespace). Run with --dry-run first and check the summary
report; if a sheet reports 0 rows read, the sheet name or its header row likely needs a
small adjustment in COLUMN_CANDIDATES/SHEET_NAMES below to match the real file.

Import order matters: each sheet's rows are kept in an in-memory id_map (Excel string ID
-> Django instance) so that later sheets can resolve the prefixed IDs (CAT-, COMP-, ...)
used by the workbook to link sheets together. A Composante/Sous-composante can now be
linked to several Crédits & Dons (separate "Composantes-CréditDon"/"Sous-composantes-
CréditDon" link sheets, applied to the fundings M2M after the component sheets), and a
Virement can be linked to several Décaissements (separate "Virements-Décaissements" link
sheet, applied to the disbursements M2M after both Décaissements and Virements) - a
BankTransfer's project/funding are never set directly, they're computed properties
deduced from the first linked disbursement.

Upsert by `external_id`: every model touched here carries an `external_id` field (see
cosomis.models_base.ExternalIdMixin) that stores the workbook's own `ID_xxx` value. On
each row, if a record with that external_id already exists it is updated in place instead
of duplicated - so the same workbook can be re-imported after edits (add a row, correct an
amount, ...) without piling up duplicates. A record created directly in the app (not via
this command) always has external_id=None and is therefore never matched/overwritten here.
"""
import re
import unicodedata
from collections import defaultdict

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from subprojects.models import Project, CategoryIDA, Component
from financial.models.account import Account
from financial.models.bank import Bank
from financial.models.funding import Funding
from financial.models.planning import AnnualWorkPlan, Activity
from financial.models.supporting_document import SupportingDocument, SupportingDocumentActivity, SupportingDocumentActivityFile
from financial.models.financial import (
    DisbursementRequest, DisbursementRequestValidation, Disbursement, BankTransfer,
)


def normalize(value):
    if value is None:
        return ''
    value = str(value).strip()
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'\s+', ' ', value).strip().lower()


def get_value(row, *candidates):
    normalized_columns = {normalize(col): col for col in row.index}
    for candidate in candidates:
        col = normalized_columns.get(normalize(candidate))
        if col is not None and pd.notna(row[col]):
            return row[col]
    return None


def to_str(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return str(value).strip()


def to_float(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_date(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    ts = pd.to_datetime(value, errors='coerce')
    return ts.date() if pd.notna(ts) else None


def split_refs(value):
    """'Pièces justificatives' style cell: several IDs separated by , ; or /."""
    text = to_str(value)
    if not text:
        return []
    return [part.strip() for part in re.split(r'[,;/]', text) if part.strip()]


FUNDING_TYPE_MAP = {'credit': Funding.FundingType.CREDIT, 'don': Funding.FundingType.GRANT, 'grant': Funding.FundingType.GRANT}
ACCOUNT_TYPE_MAP = {
    'projet': Account.AccountType.PROJECT, 'project': Account.AccountType.PROJECT,
    'antenne regionale': Account.AccountType.REGIONAL_OFFICE, 'bureau regional': Account.AccountType.REGIONAL_OFFICE,
    'mairie': Account.AccountType.TOWN_HALL, 'commune': Account.AccountType.TOWN_HALL,
    'cvd': Account.AccountType.CVD,
    'specialiste de projet': Account.AccountType.PROJECT_SPECIALIST, 'specialiste projet': Account.AccountType.PROJECT_SPECIALIST,
    'prestataire de services': Account.AccountType.SERVICE_PROVIDER, 'prestataire': Account.AccountType.SERVICE_PROVIDER,
    'entreprise prestataire': Account.AccountType.SERVICE_PROVIDER,
}
ACCOUNT_CATEGORY_MAP = {'compte principal': Account.AccountCategory.MAIN_ACCOUNT, 'sous-compte': Account.AccountCategory.SUB_ACCOUNT, 'sous compte': Account.AccountCategory.SUB_ACCOUNT}
DOCUMENT_TYPE_MAP = {
    'facture': SupportingDocumentActivityFile.DocumentType.INVOICE, 'recu': SupportingDocumentActivityFile.DocumentType.RECEIPT,
    'contrat': SupportingDocumentActivityFile.DocumentType.CONTRACT, 'proces-verbal': SupportingDocumentActivityFile.DocumentType.MINUTES,
    'proces verbal': SupportingDocumentActivityFile.DocumentType.MINUTES, 'pv': SupportingDocumentActivityFile.DocumentType.MINUTES,
    'bon de commande': SupportingDocumentActivityFile.DocumentType.PURCHASE_ORDER, 'autre': SupportingDocumentActivityFile.DocumentType.OTHER,
}
DISBURSEMENT_REQUEST_STATUS_MAP = {
    'en attente': DisbursementRequest.Status.PENDING,
    'entierement validee': DisbursementRequest.Status.FULLY_VALIDATED, 'validee': DisbursementRequest.Status.FULLY_VALIDATED,
    'partiellement validee': DisbursementRequest.Status.PARTIALLY_VALIDATED,
    'rejetee': DisbursementRequest.Status.REJECTED,
}
VALIDATION_STATUS_AFTER_MAP = {
    'validee integralement': DisbursementRequest.Status.FULLY_VALIDATED,
    'validee partiellement': DisbursementRequest.Status.PARTIALLY_VALIDATED,
}
LEVEL_MAP = {
    '1': BankTransfer.Level.LEVEL_1_PROJECT, 'niveau 1': BankTransfer.Level.LEVEL_1_PROJECT,
    '2': BankTransfer.Level.LEVEL_2_REGIONAL_OFFICE, 'niveau 2': BankTransfer.Level.LEVEL_2_REGIONAL_OFFICE,
    '3': BankTransfer.Level.LEVEL_3_TOWN_HALL, 'niveau 3': BankTransfer.Level.LEVEL_3_TOWN_HALL,
    '4': BankTransfer.Level.LEVEL_4_CVD, 'niveau 4': BankTransfer.Level.LEVEL_4_CVD,
}
PAYMENT_METHOD_MAP = {
    'virement': BankTransfer.PaymentMethod.BANK_TRANSFER, 'virement bancaire': BankTransfer.PaymentMethod.BANK_TRANSFER,
    'cheque': BankTransfer.PaymentMethod.CHEQUE,
    'espece': BankTransfer.PaymentMethod.CASH, 'especes': BankTransfer.PaymentMethod.CASH,
}
DIRECTION_MAP = {'aller': BankTransfer.Direction.FORWARD, 'emetteur vers beneficiaire': BankTransfer.Direction.FORWARD, 'normal (emetteur vers beneficiaire)': BankTransfer.Direction.FORWARD, 'retour': BankTransfer.Direction.RETURN, 'retour (beneficiaire vers emetteur)': BankTransfer.Direction.RETURN}


def map_choice(value, mapping, default=None):
    return mapping.get(normalize(value), default)


def upsert(model, ref, defaults):
    """Create or update `model` by its external_id (the workbook's own ID_ column
    value). Returns (instance, created_bool). `ref` may be None/blank - in that
    case a plain new row is always created (no match key to upsert against)."""
    if ref:
        instance = model.objects.filter(external_id=ref).first()
        if instance:
            for field, value in defaults.items():
                setattr(instance, field, value)
            instance.save()
            return instance, False
        return model.objects.create(external_id=ref, **defaults), True
    return model.objects.create(**defaults), True


class Command(BaseCommand):
    help = 'Import the disbursement/bank-transfer reference workbook (CLAUDE.md §2/§6) into the financial models.'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Path to the .xlsx workbook')
        parser.add_argument('--project', type=str, default=None, help='Name of the IDA Project (subprojects.Project) to use as fallback / for sheets with no explicit project column')
        parser.add_argument('--dry-run', action='store_true', help='Parse and report without writing to the database')

    def handle(self, *args, **options):
        file_path = options['file_path']
        dry_run = options['dry_run']

        try:
            sheets = pd.read_excel(file_path, sheet_name=None, header=None)
        except FileNotFoundError:
            raise CommandError(f'File not found: {file_path}')

        # Every sheet starts with a title row, a description row and a blank row
        # before the real header (see the sheet dump in the command docstring) -
        # re-read each sheet telling pandas which row is the actual header.
        sheets = self._reread_with_headers(file_path, sheets)

        fallback_project = None
        if options['project']:
            fallback_project = Project.objects.filter(name=options['project']).first()
            if not fallback_project:
                raise CommandError(f'Project "{options["project"]}" not found')

        report = {}
        id_maps = {
            'project': {}, 'funding': {}, 'category': {}, 'component': {},
            'annual_work_plan': {}, 'activity': {}, 'account': {},
            'disbursement_request': {}, 'disbursement': {}, 'supporting_document': {},
            'supporting_document_activity': {}, 'bank_transfer': {},
        }

        def find_sheet(*name_candidates):
            normalized_sheets = {normalize(name): name for name in sheets}
            for candidate in name_candidates:
                key = normalized_sheets.get(normalize(candidate))
                if key:
                    return sheets[key]
            return None

        def resolve_project(row):
            project_ref = to_str(get_value(row, 'ID_ProjetIDA', 'Projet IDA'))
            if project_ref and project_ref in id_maps['project']:
                return id_maps['project'][project_ref]
            return fallback_project

        with transaction.atomic():
            sp = transaction.savepoint()

            report['Projets IDA'] = self._import_projects(find_sheet('Projets IDA'), id_maps)
            report['Crédits & Dons'] = self._import_fundings(find_sheet('Crédits & Dons', 'Credits & Dons'), id_maps, resolve_project)
            report['Catégories'] = self._import_categories(find_sheet('Catégories', 'Categories'), id_maps, resolve_project)
            report['Composantes'] = self._import_components(find_sheet('Composantes'), id_maps, category_level=True)
            report['Composantes-CréditDon'] = self._import_component_funding_links(find_sheet('Composantes-CréditDon', 'Composantes-CreditDon'), id_maps, 'ID_Composante')
            report['Sous-composantes'] = self._import_components(find_sheet('Sous-composantes', 'Sous composantes'), id_maps, category_level=False)
            report['Sous-composantes-CréditDon'] = self._import_component_funding_links(find_sheet('Sous-composantes-CréditDon', 'Sous-composantes-CreditDon'), id_maps, 'ID_SousComposante')
            report['PTBA'] = self._import_annual_work_plans(find_sheet('PTBA'), id_maps, resolve_project)
            report['Activités'] = self._import_activities(find_sheet('Activités', 'Activites'), id_maps)
            report['Acteurs & Comptes'] = self._import_accounts(find_sheet('Acteurs & Comptes', 'Acteurs et Comptes'), id_maps)
            report['Demandes de fonds'] = self._import_disbursement_requests(find_sheet('Demandes de fonds'), id_maps, resolve_project)
            report['Validations des demandes'] = self._import_disbursement_request_validations(find_sheet('Validations des demandes'), id_maps)
            report['Décaissements'] = self._import_disbursements(find_sheet('Décaissements', 'Decaissements'), id_maps)
            report['Justificatifs'] = self._import_supporting_documents(find_sheet('Justificatifs'), id_maps)
            report['Justificatifs-Activités'] = self._import_supporting_document_activities(find_sheet('Justificatifs-Activités', 'Justificatifs Activites'), id_maps)
            report['Fichiers justif. Activités'] = self._import_supporting_document_activity_files(find_sheet('Fichiers justif. Activités', 'Fichiers justif Activites'), id_maps)
            report['Virements'] = self._import_bank_transfers(find_sheet('Virements'), id_maps)
            report['Virements-Décaissements'] = self._import_bank_transfer_disbursements(find_sheet('Virements-Décaissements', 'Virements-Decaissements'), id_maps)

            if dry_run:
                transaction.savepoint_rollback(sp)
            else:
                transaction.savepoint_commit(sp)

        self.stdout.write(self.style.SUCCESS('Dry run - nothing written.' if dry_run else 'Import complete.'))
        for sheet_name, (created, updated, skipped) in report.items():
            self.stdout.write(f'  {sheet_name}: {created} created, {updated} updated, {skipped} skipped')

    def _reread_with_headers(self, file_path, sheets):
        """Every content sheet's real header row is the first row starting with an
        'ID_...' cell (title/description/blank rows come before it) - find it per
        sheet and re-read with pandas' header= so column names resolve correctly."""
        reread = {}
        for name, df in sheets.items():
            header_row_index = None
            for i in range(min(10, len(df))):
                first_cell = to_str(df.iloc[i, 0])
                if first_cell and normalize(first_cell).startswith('id_'):
                    header_row_index = i
                    break
            if header_row_index is None:
                reread[name] = df
                continue
            reread[name] = pd.read_excel(file_path, sheet_name=name, header=header_row_index)
        return reread

    # -- per-sheet importers -------------------------------------------------

    def _import_projects(self, df, id_maps):
        if df is None:
            return (0, 0, 0)
        matched, updated, skipped = 0, 0, 0
        for _, row in df.iterrows():
            ref = to_str(get_value(row, 'ID_ProjetIDA', 'ID_Projet'))
            name = to_str(get_value(row, 'Nom du Projet IDA', 'Libellé', 'Nom'))
            if not ref or not name:
                skipped += 1
                continue
            project = Project.objects.filter(external_id=ref).first() or Project.objects.filter(name=name).first()
            if not project:
                skipped += 1
                continue
            id_maps['project'][ref] = project
            if not project.external_id:
                project.external_id = ref
                project.save(update_fields=['external_id'])
                updated += 1
            else:
                matched += 1
        return (matched, updated, skipped)

    def _import_fundings(self, df, id_maps, resolve_project):
        if df is None:
            return (0, 0, 0)
        created, updated, skipped = 0, 0, 0
        for _, row in df.iterrows():
            ref = to_str(get_value(row, 'ID_CréditDon', 'ID_Credit_Don'))
            project = resolve_project(row)
            label = to_str(get_value(row, 'Libellé / Objet', 'Libellé', 'Objet'))
            if not project or not label:
                skipped += 1
                continue
            defaults = dict(
                project=project,
                funding_type=map_choice(get_value(row, 'Type'), FUNDING_TYPE_MAP, Funding.FundingType.CREDIT),
                identification_number=to_str(get_value(row, "N° d'identification IDA", 'Identification IDA')) or '',
                label=label,
                initial_amount=to_float(get_value(row, 'Montant initial')) or 0,
                notes=to_str(get_value(row, 'Observations')),
            )
            funding, was_created = upsert(Funding, ref, defaults)
            if ref:
                id_maps['funding'][ref] = funding
            created += int(was_created)
            updated += int(not was_created)
        return (created, updated, skipped)

    def _import_categories(self, df, id_maps, resolve_project):
        if df is None:
            return (0, 0, 0)
        created, updated, skipped = 0, 0, 0
        for _, row in df.iterrows():
            ref = to_str(get_value(row, 'ID_Catégorie', 'ID_Categorie'))
            name = to_str(get_value(row, 'Libellé'))
            project = resolve_project(row)
            if not name:
                skipped += 1
                continue
            defaults = dict(
                project=project,
                name=name,
                target=to_str(get_value(row, 'Cible(s)', 'Cibles')),
            )
            category, was_created = upsert(CategoryIDA, ref, defaults)
            if ref:
                id_maps['category'][ref] = category
            created += int(was_created)
            updated += int(not was_created)
        return (created, updated, skipped)

    def _import_components(self, df, id_maps, category_level):
        """A Composante/Sous-composante's Crédits & Dons are no longer read here -
        see _import_component_funding_links() for the separate link sheets."""
        if df is None:
            return (0, 0, 0)
        created, updated, skipped = 0, 0, 0
        for _, row in df.iterrows():
            id_col = 'ID_Composante' if category_level else 'ID_SousComposante'
            ref = to_str(get_value(row, id_col))
            name = to_str(get_value(row, 'Libellé'))
            if not name:
                skipped += 1
                continue

            defaults = dict(
                name=name,
                amount=to_float(get_value(row, 'Montant alloué', 'Montant')),
                target=to_str(get_value(row, 'Cible(s)', 'Cibles')),
            )
            if category_level:
                category_ref = to_str(get_value(row, 'ID_Catégorie', 'ID_Categorie'))
                category = id_maps['category'].get(category_ref)
                defaults.update(category=category, project=category.project if category else None, parent=None)
            else:
                parent_ref = to_str(get_value(row, 'ID_Composante (obligatoire)', 'ID_Composante'))
                parent = id_maps['component'].get(parent_ref)
                if not parent:
                    skipped += 1
                    continue
                # A Sous-composante's IDA category is independent of its parent's -
                # it may differ, so read its own column, falling back to the parent's
                # category only when the sheet leaves it blank.
                category_ref = to_str(get_value(row, 'ID_Catégorie', 'ID_Categorie'))
                category = id_maps['category'].get(category_ref) if category_ref else parent.category
                defaults.update(parent=parent, project=parent.project, category=category)

            component, was_created = upsert(Component, ref, defaults)
            if ref:
                id_maps['component'][ref] = component
            created += int(was_created)
            updated += int(not was_created)
        return (created, updated, skipped)

    def _import_component_funding_links(self, df, id_maps, component_id_col):
        """Composantes-CréditDon / Sous-composantes-CréditDon (ID_Lien, ID_Composante
        or ID_SousComposante, ID_CréditDon): a component can now be linked to several
        Crédits & Dons - each component's fundings M2M is fully replaced by whatever
        this sheet lists for it (idempotent on re-import)."""
        if df is None:
            return (0, 0, 0)
        applied, skipped = 0, 0
        pending = defaultdict(set)
        for _, row in df.iterrows():
            component_ref = to_str(get_value(row, component_id_col))
            funding_ref = to_str(get_value(row, 'ID_CréditDon', 'ID_Credit_Don'))
            component = id_maps['component'].get(component_ref)
            funding = id_maps['funding'].get(funding_ref)
            if not component or not funding:
                skipped += 1
                continue
            pending[component.pk].add(funding.pk)
            applied += 1
        for component_pk, funding_pks in pending.items():
            Component.objects.get(pk=component_pk).fundings.set(funding_pks)
        return (applied, 0, skipped)

    def _import_annual_work_plans(self, df, id_maps, resolve_project):
        if df is None:
            return (0, 0, 0)
        created, updated, skipped = 0, 0, 0
        for _, row in df.iterrows():
            ref = to_str(get_value(row, 'ID_PTBA'))
            project = resolve_project(row)
            name = to_str(get_value(row, 'Libellé'))
            period = to_str(get_value(row, 'Année / Période', 'Année', 'Periode'))
            if not project or not name:
                skipped += 1
                continue
            defaults = dict(
                project=project,
                period=int(re.sub(r'\D', '', period)[:4]) if period and re.search(r'\d{4}', period) else 0,
                name=name,
                notes=to_str(get_value(row, 'Observations')),
            )
            plan, was_created = upsert(AnnualWorkPlan, ref, defaults)
            if ref:
                id_maps['annual_work_plan'][ref] = plan
            created += int(was_created)
            updated += int(not was_created)
        return (created, updated, skipped)

    def _import_activities(self, df, id_maps):
        if df is None:
            return (0, 0, 0)
        created, updated, skipped = 0, 0, 0
        for _, row in df.iterrows():
            ref = to_str(get_value(row, 'ID_Activité', 'ID_Activite'))
            component_ref = to_str(get_value(row, 'ID_Composante', 'ID_SousComposante'))
            plan_ref = to_str(get_value(row, 'ID_PTBA'))
            component = id_maps['component'].get(component_ref)
            plan = id_maps['annual_work_plan'].get(plan_ref)
            name = to_str(get_value(row, 'Libellé'))
            if not component or not plan or not name:
                skipped += 1
                continue
            defaults = dict(
                component=component,
                annual_work_plan=plan,
                name=name,
                amount=to_float(get_value(row, 'Montant')) or 0,
                target=to_str(get_value(row, 'Cible(s)', 'Cibles')),
            )
            activity, was_created = upsert(Activity, ref, defaults)
            if ref:
                id_maps['activity'][ref] = activity
            created += int(was_created)
            updated += int(not was_created)
        return (created, updated, skipped)

    def _import_accounts(self, df, id_maps):
        if df is None:
            return (0, 0, 0)
        created, updated, skipped = 0, 0, 0
        for _, row in df.iterrows():
            ref = to_str(get_value(row, 'ID_Acteur'))
            name = to_str(get_value(row, "Nom de l'acteur", 'Nom'))
            if not name:
                skipped += 1
                continue
            bank_name = to_str(get_value(row, 'Banque', 'Nom de la banque'))
            defaults = dict(
                name=name,
                account_type=map_choice(get_value(row, "Type d'acteur", 'Type'), ACCOUNT_TYPE_MAP, Account.AccountType.SERVICE_PROVIDER),
                account_category=map_choice(get_value(row, 'Catégorie de compte'), ACCOUNT_CATEGORY_MAP, Account.AccountCategory.MAIN_ACCOUNT),
                account_number=to_str(get_value(row, 'N° de compte', 'Numero de compte')),
                contact=to_str(get_value(row, 'Contact')),
                notes=to_str(get_value(row, 'Statut / Observations', 'Statut', 'Observations')),
                bank=Bank.objects.filter(name=bank_name).first() if bank_name else None,
            )
            account, was_created = upsert(Account, ref, defaults)
            if ref:
                id_maps['account'][ref] = account
            created += int(was_created)
            updated += int(not was_created)
        return (created, updated, skipped)

    def _import_disbursement_requests(self, df, id_maps, resolve_project):
        if df is None:
            return (0, 0, 0)
        created, updated, skipped = 0, 0, 0
        for _, row in df.iterrows():
            ref = to_str(get_value(row, 'ID_Demande'))
            project = resolve_project(row)
            requested_date = to_date(get_value(row, 'Date demande'))
            amount_requested = to_float(get_value(row, 'Montant demandé', 'Montant demande'))
            if not project or not requested_date or amount_requested is None:
                skipped += 1
                continue
            funding_ref = to_str(get_value(row, 'ID_CréditDon', 'ID_Credit_Don'))
            defaults = dict(
                project=project,
                funding=id_maps['funding'].get(funding_ref),
                funding_type=map_choice(get_value(row, 'Type (Crédit/Don)', 'Type'), FUNDING_TYPE_MAP),
                requested_date=requested_date,
                amount_requested=amount_requested,
                # Montant demandé (USD): USD amount, distinct from the (local currency)
                # amount_requested column above.
                amount_requested_in_dollars=to_float(get_value(row, 'Montant demandé (USD)', 'Montant demande (USD)')) or 0,
                motif=to_str(get_value(row, 'Motif')),
                description=to_str(get_value(row, 'Description', 'Objet', 'Justification')),
                first_response_date=to_date(get_value(row, 'Date de première réponse', 'Date validation')),
                comment_linked_to_reply=to_str(get_value(row, 'Commentaire lié à la réponse')),
                status=map_choice(
                    get_value(row, 'Statut (manuel, si aucune validation)', 'Statut'),
                    DISBURSEMENT_REQUEST_STATUS_MAP, DisbursementRequest.Status.PENDING,
                ),
            )
            request, was_created = upsert(DisbursementRequest, ref, defaults)
            if ref:
                id_maps['disbursement_request'][ref] = request
            created += int(was_created)
            updated += int(not was_created)
        return (created, updated, skipped)

    def _import_disbursement_request_validations(self, df, id_maps):
        if df is None:
            return (0, 0, 0)
        created, updated, skipped = 0, 0, 0
        touched_requests = set()
        for _, row in df.iterrows():
            ref = to_str(get_value(row, 'ID_Validation'))
            request_ref = to_str(get_value(row, 'ID_Demande liée', 'ID_Demande'))
            request = id_maps['disbursement_request'].get(request_ref)
            validation_date = to_date(get_value(row, 'Date de validation'))
            amount_validated = to_float(get_value(row, 'Montant validé (ce tour)', 'Montant validé'))
            if not request or not validation_date or amount_validated is None:
                skipped += 1
                continue
            defaults = dict(
                disbursement_request=request,
                validation_date=validation_date,
                amount_validated=amount_validated,
                status_after=map_choice(
                    get_value(row, 'Statut après cette validation'),
                    VALIDATION_STATUS_AFTER_MAP, DisbursementRequest.Status.PARTIALLY_VALIDATED,
                ),
                comment=to_str(get_value(row, 'Commentaire')),
            )
            validation, was_created = upsert(DisbursementRequestValidation, ref, defaults)
            touched_requests.add(validation.disbursement_request_id)
            created += int(was_created)
            updated += int(not was_created)

        # §"Validations des demandes" is authoritative for amount_validated/status/
        # first_response_date/comment_linked_to_reply on any request it covers -
        # mirrors DisbursementRequestValidationCreateView's post-save resync.
        for request_id in touched_requests:
            request = DisbursementRequest.objects.get(pk=request_id)
            rounds = list(request.validations.order_by('validation_date'))
            if not rounds:
                continue
            total = sum(r.amount_validated or 0 for r in rounds)
            request.status = (
                DisbursementRequest.Status.FULLY_VALIDATED
                if total >= (request.amount_requested or 0)
                else DisbursementRequest.Status.PARTIALLY_VALIDATED
            )
            if not request.first_response_date:
                request.first_response_date = rounds[0].validation_date
            last_comment = next((r.comment for r in reversed(rounds) if r.comment), None)
            if last_comment:
                request.comment_linked_to_reply = last_comment
            request.save()
        return (created, updated, skipped)

    def _import_disbursements(self, df, id_maps):
        """Statut de justification is auto-computed (Disbursement.justification_status
        is now a property) - the sheet's own column is informational only and never
        read here."""
        if df is None:
            return (0, 0, 0)
        created, updated, skipped = 0, 0, 0
        for _, row in df.iterrows():
            ref = to_str(get_value(row, 'ID_Décaissement', 'ID_Decaissement'))
            request_ref = to_str(get_value(row, 'ID_Demande liée', 'ID_Demande'))
            request = id_maps['disbursement_request'].get(request_ref)
            disbursement_date = to_date(get_value(row, 'Date du décaissement', 'Date decaissement'))
            amount = to_float(get_value(row, 'Montant décaissé', 'Montant decaisse'))
            if not request or not disbursement_date or amount is None:
                skipped += 1
                continue
            defaults = dict(
                disbursement_request=request,
                amount_disbursed=amount,
                amount_disbursed_in_dollars=0,
                disbursement_date=disbursement_date,
                description=to_str(get_value(row, 'Motif / Objet de la dépense', 'Motif', 'Objet de la dépense')),
                notes=to_str(get_value(row, 'Observations')),
            )
            disbursement, was_created = upsert(Disbursement, ref, defaults)
            if ref:
                id_maps['disbursement'][ref] = disbursement
            created += int(was_created)
            updated += int(not was_created)
        return (created, updated, skipped)

    def _import_supporting_documents(self, df, id_maps):
        """Type de pièce / Lien-Emplacement du fichier moved to the per-activity-line
        "Fichiers justif. Activités" sheet (see _import_supporting_document_activity_files) -
        neither is read here anymore."""
        if df is None:
            return (0, 0, 0)
        created, updated, skipped = 0, 0, 0
        for _, row in df.iterrows():
            ref = to_str(get_value(row, 'ID_Justificatif'))
            disbursement_ref = to_str(get_value(row, 'ID_Décaissement lié', 'ID_Decaissement'))
            disbursement = id_maps['disbursement'].get(disbursement_ref)
            document_date = to_date(get_value(row, 'Date de la DRF', 'Date de la pièce', 'Date de la piece'))
            if not disbursement or not document_date:
                skipped += 1
                continue
            defaults = dict(
                disbursement=disbursement,
                reference=to_str(get_value(row, 'Référence de la DRF', 'Référence de la pièce', 'Reference')) or '',
                document_date=document_date,
                notes=to_str(get_value(row, 'Observations')),
            )
            document, was_created = upsert(SupportingDocument, ref, defaults)
            if ref:
                id_maps['supporting_document'][ref] = document
            created += int(was_created)
            updated += int(not was_created)
        return (created, updated, skipped)

    def _import_supporting_document_activities(self, df, id_maps):
        if df is None:
            return (0, 0, 0)
        created, updated, skipped = 0, 0, 0
        for _, row in df.iterrows():
            ref = to_str(get_value(row, 'ID_Ligne'))
            document_ref = to_str(get_value(row, 'ID_Justificatif'))
            activity_ref = to_str(get_value(row, 'ID_Activité', 'ID_Activite'))
            document = id_maps['supporting_document'].get(document_ref)
            activity = id_maps['activity'].get(activity_ref)
            allocated_amount = to_float(get_value(row, 'Montant imputé', 'Montant impute'))
            if not document or not activity or allocated_amount is None:
                skipped += 1
                continue
            defaults = dict(
                supporting_document=document,
                activity=activity,
                allocated_amount=allocated_amount,
                notes=to_str(get_value(row, 'Observations')),
            )
            line, was_created = upsert(SupportingDocumentActivity, ref, defaults)
            if ref:
                id_maps['supporting_document_activity'][ref] = line
            created += int(was_created)
            updated += int(not was_created)
        return (created, updated, skipped)

    def _import_supporting_document_activity_files(self, df, id_maps):
        """Fichiers justif. Activités (ID_Fichier, ID_JustifActivité liée, Type de
        pièce, Lien / Emplacement du fichier) - a Justificatif-Activité line can
        carry several files."""
        if df is None:
            return (0, 0, 0)
        created, updated, skipped = 0, 0, 0
        for _, row in df.iterrows():
            ref = to_str(get_value(row, 'ID_Fichier'))
            line_ref = to_str(get_value(row, 'ID_JustifActivité liée', 'ID_Ligne'))
            line = id_maps['supporting_document_activity'].get(line_ref)
            file_name = to_str(get_value(row, 'Lien / Emplacement du fichier', 'Lien', 'Emplacement du fichier'))
            if not line or not file_name:
                skipped += 1
                continue
            defaults = dict(
                supporting_document_activity=line,
                document_type=map_choice(get_value(row, 'Type de pièce', 'Type de piece'), DOCUMENT_TYPE_MAP, SupportingDocumentActivityFile.DocumentType.OTHER),
                file_name=file_name,
            )
            _file, was_created = upsert(SupportingDocumentActivityFile, ref, defaults)
            created += int(was_created)
            updated += int(not was_created)
        return (created, updated, skipped)

    def _import_bank_transfers(self, df, id_maps):
        """ID_ProjetIDA/ID_CréditDon and Décaissement lié are no longer read here:
        project/funding are computed properties deduced from the first linked
        disbursement, and the disbursement link itself is now a M2M applied via
        the separate "Virements-Décaissements" sheet (see
        _import_bank_transfer_disbursements)."""
        if df is None:
            return (0, 0, 0)
        created, updated, skipped = 0, 0, 0
        for _, row in df.iterrows():
            ref = to_str(get_value(row, 'ID_Virement'))
            sender_ref = to_str(get_value(row, 'Émetteur', 'Emetteur'))
            recipient_ref = to_str(get_value(row, 'Bénéficiaire', 'Beneficiaire'))
            sender = id_maps['account'].get(sender_ref)
            recipient = id_maps['account'].get(recipient_ref)
            amount = to_float(get_value(row, 'Montant'))
            if amount is None:
                skipped += 1
                continue
            defaults = dict(
                sender=sender,
                recipient=recipient,
                level=map_choice(get_value(row, 'Niveau'), LEVEL_MAP),
                amount_transferred=amount,
                transfer_date=to_date(get_value(row, 'Date du virement')),
                motif=to_str(get_value(row, 'Motif / Référence', 'Motif', 'Référence')),
                payment_method=map_choice(get_value(row, 'Mode de paiement'), PAYMENT_METHOD_MAP, BankTransfer.PaymentMethod.BANK_TRANSFER),
                direction=map_choice(get_value(row, 'Sens du virement'), DIRECTION_MAP, BankTransfer.Direction.FORWARD),
                description=to_str(get_value(row, 'Observations')),
            )
            transfer, was_created = upsert(BankTransfer, ref, defaults)
            if ref:
                id_maps['bank_transfer'][ref] = transfer

            document_refs = split_refs(get_value(row, 'Pièces justificatives'))
            documents = [id_maps['supporting_document'][r] for r in document_refs if r in id_maps['supporting_document']]
            if documents:
                transfer.supporting_documents.set(documents)

            created += int(was_created)
            updated += int(not was_created)
        return (created, updated, skipped)

    def _import_bank_transfer_disbursements(self, df, id_maps):
        """Virements-Décaissements (ID_Lien, ID_Virement, ID_Décaissement,
        Observations): a transfer can now be linked to several disbursements -
        each transfer's disbursements M2M is fully replaced by whatever this sheet
        lists for it (idempotent on re-import)."""
        if df is None:
            return (0, 0, 0)
        applied, skipped = 0, 0
        pending = defaultdict(set)
        for _, row in df.iterrows():
            transfer_ref = to_str(get_value(row, 'ID_Virement'))
            disbursement_ref = to_str(get_value(row, 'ID_Décaissement', 'ID_Decaissement'))
            transfer = id_maps['bank_transfer'].get(transfer_ref)
            disbursement = id_maps['disbursement'].get(disbursement_ref)
            if not transfer or not disbursement:
                skipped += 1
                continue
            pending[transfer.pk].add(disbursement.pk)
            applied += 1
        for transfer_pk, disbursement_pks in pending.items():
            BankTransfer.objects.get(pk=transfer_pk).disbursements.set(disbursement_pks)
        return (applied, 0, skipped)
