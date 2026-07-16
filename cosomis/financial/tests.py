from django.core.exceptions import ValidationError
from django.test import TestCase

from subprojects.models import Project, CategoryIDA, Component
from financial.models.account import Account
from financial.models.funding import Funding
from financial.models.planning import AnnualWorkPlan, Activity
from financial.models.supporting_document import SupportingDocument, SupportingDocumentActivity
from financial.models.financial import DisbursementRequest, DisbursementRequestValidation, Disbursement, BankTransfer


class DisbursementRequestAggregationTestCase(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name='Test Project', description='desc')
        self.request = DisbursementRequest.objects.create(
            project=self.project, amount_requested=1000, amount_requested_in_dollars=1000,
            requested_date='2026-01-01',
        )
        DisbursementRequestValidation.objects.create(
            disbursement_request=self.request, validation_date='2026-01-15',
            amount_validated=800, status_after=DisbursementRequest.Status.PARTIALLY_VALIDATED,
        )

    def test_no_disbursement_yet(self):
        self.assertEqual(self.request.total_disbursed, 0)
        self.assertEqual(self.request.available_balance, 800)

    def test_total_disbursed_sums_related_disbursements(self):
        Disbursement.objects.create(
            disbursement_request=self.request, amount_disbursed=300, amount_disbursed_in_dollars=300,
            disbursement_date='2026-02-01',
        )
        Disbursement.objects.create(
            disbursement_request=self.request, amount_disbursed=200, amount_disbursed_in_dollars=200,
            disbursement_date='2026-03-01',
        )
        self.assertEqual(self.request.total_disbursed, 500)
        self.assertEqual(self.request.available_balance, 300)


class DisbursementAggregationTestCase(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name='Test Project', description='desc')
        self.funding = Funding.objects.create(
            project=self.project, funding_type=Funding.FundingType.CREDIT,
            identification_number='IDA-1', label='Credit', initial_amount=10000,
        )
        self.request = DisbursementRequest.objects.create(
            project=self.project, funding=self.funding, amount_requested=1000,
            amount_requested_in_dollars=1000, requested_date='2026-01-01',
        )
        self.disbursement = Disbursement.objects.create(
            disbursement_request=self.request, amount_disbursed=500, amount_disbursed_in_dollars=500,
            disbursement_date='2026-02-01',
        )

    def test_project_and_funding_properties_derive_from_request(self):
        self.assertEqual(self.disbursement.project, self.project)
        self.assertEqual(self.disbursement.funding, self.funding)

    def test_justified_amount_with_no_supporting_documents(self):
        self.assertEqual(self.disbursement.justified_amount, 0)
        self.assertEqual(self.disbursement.justification_gap, 500)

    def test_justified_amount_sums_supporting_document_totals(self):
        component_category = CategoryIDA.objects.create(project=self.project, name='Cat')
        component = Component.objects.create(category=component_category, name='Comp', amount=10000)
        plan = AnnualWorkPlan.objects.create(project=self.project, period=2026, name='PTBA 2026')
        activity = Activity.objects.create(component=component, annual_work_plan=plan, name='Act', amount=1000)

        document = SupportingDocument.objects.create(
            disbursement=self.disbursement, document_type=SupportingDocument.DocumentType.INVOICE,
            reference='FACT-1', document_date='2026-02-05',
        )
        SupportingDocumentActivity.objects.create(supporting_document=document, activity=activity, allocated_amount=150)
        SupportingDocumentActivity.objects.create(supporting_document=document, activity=activity, allocated_amount=50)

        self.assertEqual(document.total_justified_amount, 200)
        self.assertEqual(self.disbursement.justified_amount, 200)
        self.assertEqual(self.disbursement.justification_gap, 300)
        self.assertEqual(activity.justified_amount, 200)
        self.assertEqual(activity.balance_to_justify, 800)


class BankTransferRulesTestCase(TestCase):
    """§2.13 transfer rules: enforce the 4-level sender/recipient hierarchy in clean()."""

    def setUp(self):
        self.project = Project.objects.create(name='Test Project', description='desc')
        self.account_project = Account.objects.create(name='Project account', account_type=Account.AccountType.PROJECT, account_category=Account.AccountCategory.MAIN_ACCOUNT)
        self.account_regional = Account.objects.create(name='Regional office', account_type=Account.AccountType.REGIONAL_OFFICE, account_category=Account.AccountCategory.MAIN_ACCOUNT)
        self.account_town_hall = Account.objects.create(name='Town hall', account_type=Account.AccountType.TOWN_HALL, account_category=Account.AccountCategory.MAIN_ACCOUNT)
        self.account_cvd = Account.objects.create(name='CVD', account_type=Account.AccountType.CVD, account_category=Account.AccountCategory.MAIN_ACCOUNT)
        self.account_provider = Account.objects.create(name='Provider', account_type=Account.AccountType.SERVICE_PROVIDER, account_category=Account.AccountCategory.MAIN_ACCOUNT)

    def _transfer(self, sender, recipient, direction=BankTransfer.Direction.FORWARD, level=None):
        return BankTransfer(
            project=self.project, sender=sender, recipient=recipient, level=level,
            direction=direction, amount_transferred=100, transfer_date='2026-01-01',
        )

    def test_level_1_project_to_regional_office_is_valid(self):
        transfer = self._transfer(self.account_project, self.account_regional)
        transfer.clean()  # should not raise
        self.assertEqual(transfer.level, BankTransfer.Level.LEVEL_1_PROJECT)

    def test_level_1_project_to_service_provider_is_valid(self):
        transfer = self._transfer(self.account_project, self.account_provider)
        transfer.clean()

    def test_level_3_town_hall_to_regional_office_is_invalid(self):
        """A town hall (level 3) may only send to a service provider."""
        transfer = self._transfer(self.account_town_hall, self.account_regional)
        with self.assertRaises(ValidationError):
            transfer.clean()

    def test_level_4_cvd_to_regional_office_is_invalid(self):
        transfer = self._transfer(self.account_cvd, self.account_regional)
        with self.assertRaises(ValidationError):
            transfer.clean()

    def test_level_3_town_hall_to_service_provider_is_valid(self):
        transfer = self._transfer(self.account_town_hall, self.account_provider)
        transfer.clean()
        self.assertEqual(transfer.level, BankTransfer.Level.LEVEL_3_TOWN_HALL)

    def test_reverse_direction_is_allowed(self):
        """A RETURN transfer swaps the roles for the rule check (e.g. contract cancellation)."""
        transfer = self._transfer(self.account_provider, self.account_town_hall, direction=BankTransfer.Direction.RETURN)
        transfer.clean()  # provider -> town hall is invalid forward, but valid as a RETURN of town hall -> provider

    def test_explicit_level_mismatch_is_invalid(self):
        transfer = self._transfer(self.account_project, self.account_regional, level=BankTransfer.Level.LEVEL_3_TOWN_HALL)
        with self.assertRaises(ValidationError):
            transfer.clean()

    def test_no_validation_when_sender_or_recipient_missing(self):
        """A transfer with no sender/recipient Account set (neither leg known yet) is not validated."""
        transfer = BankTransfer(
            project=self.project, sender=None, recipient=None,
            amount_transferred=100, transfer_date='2026-01-01',
        )
        transfer.clean()  # should not raise


class AccountBalanceTestCase(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name='Test Project', description='desc')
        self.sender = Account.objects.create(name='Project account', account_type=Account.AccountType.PROJECT, account_category=Account.AccountCategory.MAIN_ACCOUNT)
        self.recipient = Account.objects.create(name='CVD account', account_type=Account.AccountType.CVD, account_category=Account.AccountCategory.MAIN_ACCOUNT)

    def test_balance_counts_only_executed_transfers(self):
        BankTransfer.objects.create(
            project=self.project, sender=self.sender, recipient=self.recipient,
            amount_transferred=500, transfer_date='2026-01-01', status=BankTransfer.Status.EXECUTED,
        )
        BankTransfer.objects.create(
            project=self.project, sender=self.sender, recipient=self.recipient,
            amount_transferred=999, transfer_date='2026-01-02', status=BankTransfer.Status.PENDING,
        )
        self.assertEqual(self.recipient.available_balance(), 500)
        self.assertEqual(self.sender.available_balance(), -500)

    def test_return_transfer_credited_back_to_original_sender(self):
        BankTransfer.objects.create(
            project=self.project, sender=self.sender, recipient=self.recipient,
            amount_transferred=500, transfer_date='2026-01-01', status=BankTransfer.Status.EXECUTED,
            direction=BankTransfer.Direction.FORWARD,
        )
        BankTransfer.objects.create(
            project=self.project, sender=self.recipient, recipient=self.sender,
            amount_transferred=200, transfer_date='2026-02-01', status=BankTransfer.Status.EXECUTED,
            direction=BankTransfer.Direction.RETURN,
        )
        self.assertEqual(self.recipient.available_balance(), 300)

    def test_balance_filtered_by_year(self):
        BankTransfer.objects.create(
            project=self.project, sender=self.sender, recipient=self.recipient,
            amount_transferred=500, transfer_date='2025-06-01', status=BankTransfer.Status.EXECUTED,
        )
        BankTransfer.objects.create(
            project=self.project, sender=self.sender, recipient=self.recipient,
            amount_transferred=300, transfer_date='2026-06-01', status=BankTransfer.Status.EXECUTED,
        )
        self.assertEqual(self.recipient.available_balance(year=2026), 300)
        self.assertEqual(self.recipient.available_balance(), 800)
