from django import forms
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext_lazy as _

from .models.allocation import AdministrativeLevelAllocation
from administrativelevels.models import AdministrativeLevel, CVD
from financial.models.account import Account
from financial.models.bank import Bank
from financial.models.financial import BankTransfer, DisbursementRequest, DisbursementRequestValidation, Disbursement
from financial.models.funding import Funding
from financial.models.planning import AnnualWorkPlan, Activity
from financial.models.supporting_document import SupportingDocument, SupportingDocumentActivity, SupportingDocumentActivityFile
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
    is needed here.

    A transfer can be linked to several disbursements (§ Virements-Décaissements);
    `project`/`funding` are computed properties deduced from the first linked
    disbursement (see BankTransfer.project/.funding), never chosen here."""

    def __init__(self, *args, **kwargs):
        super(BankTransferForm, self).__init__(*args, **kwargs)
        self.fields['sender'].queryset = Account.objects.all().order_by('name')
        self.fields['recipient'].queryset = Account.objects.all().order_by('name')
        self.fields['sender'].help_text = _bank_transfer_rules_help_text()
        self.fields['disbursements'].queryset = Disbursement.objects.all().order_by('-disbursement_date')
        self.fields['linked_to_allocation'].queryset = AdministrativeLevelAllocation.objects.all().order_by('-allocation_date')

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


class BankForm(forms.ModelForm):
    class Meta:
        model = Bank
        exclude = FORM_FIELDS_TO_EXCLUDE_WITH_DELETED


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
        self.fields['bank'].queryset = Bank.objects.all().order_by('name')

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
            # Sous-composante: project is derived from the parent, not user-chosen, but
            # its IDA category is independent and may differ from the parent's own category.
            del self.fields['project']
            del self.fields['parent']
            self.fields['category'].queryset = (
                CategoryIDA.objects.filter(project=project).order_by('name') if project else CategoryIDA.objects.none()
            )
            if not (instance and instance.pk):
                self.fields['category'].initial = parent.category_id
            self.fields['fundings'].queryset = (
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
            self.fields['fundings'].queryset = Funding.objects.all().order_by('label')

    class Meta:
        model = Component
        exclude = FORM_FIELDS_TO_EXCLUDE_WITH_EXTERNAL_ID


class CategoryComponentForm(forms.ModelForm):
    """One row of the Composantes/Sous-composantes formset embedded in the IDA
    category add/edit page - `category` itself is set by the inline formset
    (fk_name='category'), `project` is derived server-side from the category, so
    neither is exposed here. `parent` lets a row register as a Sous-composante of
    an already-existing component of this same category (a brand new sibling row
    can't be picked as a parent - it doesn't have a pk yet)."""

    def __init__(self, project=None, category_pk=None, *args, **kwargs):
        super(CategoryComponentForm, self).__init__(*args, **kwargs)
        self.fields['parent'].queryset = (
            Component.objects.filter(category_id=category_pk).order_by('name') if category_pk else Component.objects.none()
        )
        self.fields['parent'].required = False
        self.fields['fundings'].queryset = (
            Funding.objects.filter(project=project).order_by('label') if project else Funding.objects.none()
        )

    class Meta:
        model = Component
        fields = ['name', 'parent', 'amount', 'target', 'description', 'fundings']


CategoryComponentFormSet = forms.inlineformset_factory(
    CategoryIDA,
    Component,
    form=CategoryComponentForm,
    fk_name='category',
    fields=['name', 'parent', 'amount', 'target', 'description', 'fundings'],
    extra=1,
    can_delete=True,
)


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
        widgets = {
            'name': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'target': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class PTBAActivityForm(forms.ModelForm):
    """One row of the Activités formset embedded directly in the PTBA detail page
    - `annual_work_plan` is set by the inline formset (fk_name='annual_work_plan'),
    never user-chosen. `name`/`target` are small Textareas (a line break should
    stay possible), `amount` is a plain text input - the space-grouped thousands
    display is purely a JS presentation layer (see the sheet/detail templates),
    the field itself still expects a plain number on submit."""

    def __init__(self, project=None, *args, **kwargs):
        super(PTBAActivityForm, self).__init__(*args, **kwargs)
        self.fields['component'].queryset = (
            Component.objects.filter(project=project).order_by('name') if project else Component.objects.none()
        )

    class Meta:
        model = Activity
        fields = ['component', 'name', 'amount', 'target']
        widgets = {
            'name': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'amount': forms.TextInput(attrs={'class': 'form-control amount-field', 'inputmode': 'decimal'}),
            'target': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


PTBAActivityFormSet = forms.inlineformset_factory(
    AnnualWorkPlan,
    Activity,
    form=PTBAActivityForm,
    fk_name='annual_work_plan',
    fields=['component', 'name', 'amount', 'target'],
    extra=1,
    can_delete=True,
)


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


class SupportingDocumentActivityFileForm(forms.ModelForm):
    """`supporting_document_activity` is fixed from the URL (see
    SupportingDocumentActivityFileCreateView), not user-chosen - a line can carry
    several files (§ Fichiers justif. Activités)."""

    class Meta:
        model = SupportingDocumentActivityFile
        fields = ['document_type', 'file', 'file_name']
