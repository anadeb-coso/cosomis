from django import forms
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext_lazy as _

from .models.allocation import AdministrativeLevelAllocation
from administrativelevels.models import AdministrativeLevel, CVD
from financial.models.account import Account
from financial.models.financial import BankTransfer, DisbursementRequest, DisbursementRequestValidation, Disbursement
from financial.models.funding import Funding
from financial.models.planning import AnnualWorkPlan, Activity
from financial.models.supporting_document import SupportingDocument, SupportingDocumentActivity
from subprojects.models import Project, CategoryIDA, Component
from cosomis import FORM_FIELDS_TO_EXCLUDE_WITH_EXTERNAL_ID, FORM_FIELDS_TO_EXCLUDE_WITH_DELETED, FORM_FIELDS_TO_EXCLUDE_WITH_EXTERNAL_ID_AND_DELETED


class AdministrativeLevelAllocationForm(forms.ModelForm):
    def __init__(self, adl_type: str = None, *args, **kwargs):
        super(AdministrativeLevelAllocationForm, self).__init__(*args, **kwargs)
        instance = kwargs.get('instance')

        self.fields['administrative_level'].queryset = AdministrativeLevel.objects.none()
        self.fields['cvd'].queryset = CVD.objects.none()
        self.fields['project'].queryset = Project.objects.all().order_by('name')
        self.fields['component'].queryset = Component.objects.all().order_by('name')

        if adl_type:
            if adl_type == 'cvd':
                qs = CVD.objects.order_by('name')
                if instance and instance.cvd:
                    qs = CVD.objects.filter(pk=instance.cvd.pk) | qs

                self.fields['cvd'].queryset = qs.distinct()

                self.fields['cvd'].choices = [('', '---------')] + [
                    (o.id, f'{o.name} ({o.headquarters_village.parent.name})') for o in self.fields['cvd'].queryset
                ]
            else:
                qs = AdministrativeLevel.objects.filter(type=adl_type.capitalize()).order_by('name')
                
                if instance and instance.administrative_level:
                    qs = AdministrativeLevel.objects.filter(pk=instance.administrative_level.pk) | qs
                
                self.fields['administrative_level'].queryset = qs.distinct()

                self.fields['administrative_level'].choices = [('', '---------')] + [
                    (o.id, f'{o.name} ({o.type} {_("Of")} {o.parent if o.parent else "TOGO" })') for o in self.fields['administrative_level'].queryset
                ]
        
        # self.fields['administrative_level'].choices = [('', '---------')] + [
        #     (o.id, f'{o.name} ({o.type} {_("Of")} {o.parent if o.parent else "TOGO" })') for o in AdministrativeLevel.objects.filter().order_by('name')
        # ]

        # self.fields['cvd'].choices = [('', '---------')] + [
        #     (o.id, f'{o.name} ({o.headquarters_village.parent.name})') for o in CVD.objects.filter().order_by('name')
        # ]

    class Meta:
        model = AdministrativeLevelAllocation
        # fields = '__all__'
        exclude  = FORM_FIELDS_TO_EXCLUDE_WITH_DELETED # specify the fields to be hid


    def clean(self):
        administrative_level = self.cleaned_data['administrative_level']
        cvd = self.cleaned_data['cvd']
        if cvd and administrative_level:
            raise forms.ValidationError(_("You must select either an administrative level or a CVD"))
        elif not cvd and not administrative_level:
            raise forms.ValidationError(_("You must choose an administrative level or a CVD"))
        return super().clean()


def _bank_transfer_rules_help_text():
    """Renders BankTransfer.TRANSFER_RULES (§2.13 "Transfer rules") as an HTML
    table, so the help shown to users can never drift from the rule actually
    enforced in BankTransfer.clean()."""
    account_type_order = [value for value, _label in Account.AccountType.choices]
    rows = format_html_join(
        '',
        '<tr><td>{}</td><td>{}</td><td>{}</td></tr>',
        (
            (
                level.label,
                sender_type.label,
                ', '.join(
                    str(Account.AccountType(value).label)
                    for value in sorted(allowed_types, key=account_type_order.index)
                ),
            )
            for level, (sender_type, allowed_types) in BankTransfer.TRANSFER_RULES.items()
        ),
    )
    return format_html(
        '<p class="mb-1" style="color: black;">{intro}</p>'
        '<table class="table table-sm table-bordered mb-2">'
        '<thead><tr><th>{level}</th><th>{sender}</th><th>{recipients}</th></tr></thead>'
        '<tbody>{rows}</tbody>'
        '</table>'
        '<p class="small mb-0" style="color: black;">{note}</p>',
        intro=_("Authorized recipients depend on the sender's level:"),
        level=_("Level"),
        sender=_("Sender"),
        recipients=_("Authorized recipients"),
        rows=rows,
        note=_(
            "A reverse transfer (recipient to sender) is possible, for example when a "
            "contract is cancelled and the recipient must return the funds to the "
            "sender. A cheque can be handed directly to a service provider."
        ),
    )


class BankTransferForm(forms.ModelForm):
    """Sender/recipient are Account references (§2.13) - the transfer-level
    hierarchy (§2.13 "Transfer rules") is enforced by BankTransfer.clean(),
    triggered by ModelForm.is_valid(), so no extra form-level validation
    is needed here."""

    def __init__(self, *args, **kwargs):
        super(BankTransferForm, self).__init__(*args, **kwargs)
        self.fields['sender'].queryset = Account.objects.all().order_by('name')
        self.fields['recipient'].queryset = Account.objects.all().order_by('name')
        self.fields['sender'].help_text = _bank_transfer_rules_help_text()
        self.fields['project'].queryset = Project.objects.all().order_by('name')
        self.fields['funding'].queryset = Funding.objects.all().order_by('label')

    class Meta:
        model = BankTransfer
        # fields = '__all__'
        exclude  = FORM_FIELDS_TO_EXCLUDE_WITH_EXTERNAL_ID_AND_DELETED # specify the fields to be hid


class DisbursementRequestForm(forms.ModelForm):
    """`amount_validated` is a computed property (see DisbursementRequest model) so
    it's never a form field. `status` can only be manually set to PENDING/REJECTED
    here - FULLY_VALIDATED/PARTIALLY_VALIDATED are only ever reached by adding a
    DisbursementRequestValidation round (see DisbursementRequestValidationCreateView)."""

    def __init__(self, *args, **kwargs):
        super(DisbursementRequestForm, self).__init__(*args, **kwargs)
        instance = kwargs.get('instance')
        choices = [
            (DisbursementRequest.Status.PENDING, DisbursementRequest.Status.PENDING.label),
            (DisbursementRequest.Status.REJECTED, DisbursementRequest.Status.REJECTED.label),
        ]
        if instance and instance.status in (DisbursementRequest.Status.FULLY_VALIDATED, DisbursementRequest.Status.PARTIALLY_VALIDATED):
            choices.append((instance.status, instance.get_status_display()))
        self.fields['status'].choices = choices

    class Meta:
        model = DisbursementRequest
        # fields = '__all__'
        exclude  = FORM_FIELDS_TO_EXCLUDE_WITH_EXTERNAL_ID_AND_DELETED # specify the fields to be hid

class DisbursementRequestFormCreate(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(DisbursementRequestFormCreate, self).__init__(*args, **kwargs)

    class Meta:
        model = DisbursementRequest
        # fields = '__all__'
        exclude  = ['first_response_date', 'comment_linked_to_reply', 'status'] + FORM_FIELDS_TO_EXCLUDE_WITH_EXTERNAL_ID_AND_DELETED # specify the fields to be hid



class DisbursementRequestValidationForm(forms.ModelForm):
    """Logs one validation round (§ history of partial fund agreements) - the
    resulting status is computed by the view (see DisbursementRequestValidationCreateView),
    not chosen here; the parent request's amount_validated is itself computed from
    these rows, so there's nothing to set on it directly."""

    class Meta:
        model = DisbursementRequestValidation
        fields = ['validation_date', 'amount_validated', 'comment']


class DisbursementForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(DisbursementForm, self).__init__(*args, **kwargs)

    class Meta:
        model = Disbursement
        # fields = '__all__'
        exclude  = FORM_FIELDS_TO_EXCLUDE_WITH_EXTERNAL_ID_AND_DELETED # specify the fields to be hid


class AccountForm(forms.ModelForm):
    """A sub-account's `parent` may only be a main account (Account.clean() enforces
    this) - the dropdown is pre-scoped to main accounts so invalid choices aren't
    even offered."""

    def __init__(self, *args, **kwargs):
        super(AccountForm, self).__init__(*args, **kwargs)
        instance = kwargs.get('instance')
        qs = Account.objects.filter(account_category=Account.AccountCategory.MAIN_ACCOUNT).order_by('name')
        if instance and instance.pk:
            qs = qs.exclude(pk=instance.pk)
        self.fields['parent'].queryset = qs

    class Meta:
        model = Account
        exclude = FORM_FIELDS_TO_EXCLUDE_WITH_EXTERNAL_ID_AND_DELETED


class ProjectForm(forms.ModelForm):
    """IDA Project (subprojects.Project). financiers/administrative_levels keep
    their existing cascade-aware workflow in subprojects/admin.py and aren't
    exposed here."""

    def __init__(self, *args, **kwargs):
        super(ProjectForm, self).__init__(*args, **kwargs)
        self.fields['parent'].queryset = Project.objects.all().order_by('name')

    class Meta:
        model = Project
        exclude = ['financiers', 'administrative_levels'] + FORM_FIELDS_TO_EXCLUDE_WITH_EXTERNAL_ID


class FundingForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(FundingForm, self).__init__(*args, **kwargs)
        self.fields['project'].queryset = Project.objects.all().order_by('name')

    class Meta:
        model = Funding
        exclude = FORM_FIELDS_TO_EXCLUDE_WITH_EXTERNAL_ID_AND_DELETED


class CategoryIDAForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(CategoryIDAForm, self).__init__(*args, **kwargs)
        self.fields['project'].queryset = Project.objects.all().order_by('name')

    class Meta:
        model = CategoryIDA
        exclude = FORM_FIELDS_TO_EXCLUDE_WITH_EXTERNAL_ID_AND_DELETED


class ComponentForm(forms.ModelForm):
    """Handles both a top-level Composante (category set, parent=None) and a
    Sous-composante (parent set to another Component) - which one depends on
    whether category_id or parent_id is passed in.

    `restrict_name=True` disables the `name` field: Financial/Evaluator/Accountant
    users may edit category/funding/description/amount/target, but renaming a
    component stays a superuser-only action (ComponentUpdateView sets this from
    the requesting user)."""

    def __init__(self, category_id=None, parent_id=None, restrict_name=False, *args, **kwargs):
        super(ComponentForm, self).__init__(*args, **kwargs)
        instance = kwargs.get('instance')

        if restrict_name:
            self.fields['name'].disabled = True

        parent = None
        if parent_id:
            parent = Component.objects.filter(pk=parent_id).first()
        elif instance and instance.pk and instance.parent_id:
            parent = instance.parent

        project = None
        if parent:
            project = parent.project
        elif category_id:
            category = CategoryIDA.objects.filter(pk=category_id).first()
            project = category.project if category else None
        elif instance and instance.pk:
            project = instance.project

        if parent:
            # Sous-composante: category/project are derived from the parent, not user-chosen.
            del self.fields['category']
            del self.fields['project']
            del self.fields['parent']
            self.fields['funding'].queryset = (
                Funding.objects.filter(project=project).order_by('label') if project else Funding.objects.none()
            )
        else:
            # Composante: parent is always None, category is required and drives project.
            del self.fields['parent']
            del self.fields['project']
            self.fields['category'].queryset = CategoryIDA.objects.all().order_by('name')
            # Funding <-> Category is cascaded client-side (see component_add.html) -
            # the category the user is about to pick isn't known yet at render time,
            # so show every funding and let JS narrow it down once one is selected.
            self.fields['funding'].queryset = Funding.objects.all().order_by('label')

    class Meta:
        model = Component
        exclude = FORM_FIELDS_TO_EXCLUDE_WITH_EXTERNAL_ID


class AnnualWorkPlanForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(AnnualWorkPlanForm, self).__init__(*args, **kwargs)
        self.fields['project'].queryset = Project.objects.all().order_by('name')

    class Meta:
        model = AnnualWorkPlan
        exclude = FORM_FIELDS_TO_EXCLUDE_WITH_EXTERNAL_ID_AND_DELETED


class ActivityForm(forms.ModelForm):
    """Activities are always managed from a PTBA's detail page - annual_work_plan
    is fixed from the URL, never user-chosen."""

    def __init__(self, annual_work_plan=None, *args, **kwargs):
        super(ActivityForm, self).__init__(*args, **kwargs)
        instance = kwargs.get('instance')
        if annual_work_plan is None and instance and instance.pk:
            annual_work_plan = instance.annual_work_plan

        del self.fields['annual_work_plan']
        self.fields['component'].queryset = (
            Component.objects.filter(project=annual_work_plan.project).order_by('name')
            if annual_work_plan else Component.objects.none()
        )

    class Meta:
        model = Activity
        exclude = FORM_FIELDS_TO_EXCLUDE_WITH_EXTERNAL_ID_AND_DELETED


class SupportingDocumentForm(forms.ModelForm):
    """mode is 'disbursement' or 'disbursement_request': the entry point the
    Justificatif was created from - the other FK is hidden and stays unset,
    matching the model's clean() XOR rule."""

    def __init__(self, mode=None, *args, **kwargs):
        super(SupportingDocumentForm, self).__init__(*args, **kwargs)
        instance = kwargs.get('instance')
        if mode is None and instance and instance.pk:
            mode = 'disbursement' if instance.disbursement_id else 'disbursement_request'

        if mode == 'disbursement_request':
            del self.fields['disbursement']
            self.fields['disbursement_request'].queryset = DisbursementRequest.objects.all()
        else:
            del self.fields['disbursement_request']
            self.fields['disbursement'].queryset = Disbursement.objects.all()

    class Meta:
        model = SupportingDocument
        exclude = FORM_FIELDS_TO_EXCLUDE_WITH_EXTERNAL_ID_AND_DELETED


class SupportingDocumentActivityForm(forms.ModelForm):
    def __init__(self, project=None, *args, **kwargs):
        super(SupportingDocumentActivityForm, self).__init__(*args, **kwargs)
        self.fields['activity'].queryset = (
            Activity.objects.filter(annual_work_plan__project=project).order_by('name')
            if project else Activity.objects.all().order_by('name')
        )

    class Meta:
        model = SupportingDocumentActivity
        fields = ['activity', 'allocated_amount', 'notes']


SupportingDocumentActivityFormSet = forms.inlineformset_factory(
    SupportingDocument,
    SupportingDocumentActivity,
    form=SupportingDocumentActivityForm,
    fields=['activity', 'allocated_amount', 'notes'],
    extra=1,
    can_delete=True,
)
