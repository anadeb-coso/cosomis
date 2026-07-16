from django.test import TestCase

from subprojects.models import Project, CategoryIDA, Component


class ProjectTotalAmountTestCase(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name='Test Project', description='desc')

    def test_total_amount_with_no_funding(self):
        self.assertEqual(self.project.total_amount, 0)

    def test_total_amount_sums_credit_and_grant(self):
        from financial.models.funding import Funding

        Funding.objects.create(
            project=self.project, funding_type=Funding.FundingType.CREDIT,
            identification_number='IDA-1', label='Credit', initial_amount=1000,
        )
        Funding.objects.create(
            project=self.project, funding_type=Funding.FundingType.GRANT,
            identification_number='IDA-2', label='Grant', initial_amount=500,
        )
        self.assertEqual(self.project.total_amount, 1500)


class ComponentAggregationTestCase(TestCase):
    """§1.3: Category/Component effective_amount rollup rules."""

    def setUp(self):
        self.project = Project.objects.create(name='Test Project', description='desc')
        self.category = CategoryIDA.objects.create(project=self.project, name='Category 1')

    def test_category_with_no_components_has_zero_amount(self):
        self.assertEqual(self.category.effective_amount, 0)

    def test_component_with_own_amount_counts_own_amount(self):
        component = Component.objects.create(category=self.category, name='Component 1', amount=1000)
        self.assertEqual(component.effective_amount, 1000)
        self.assertEqual(self.category.effective_amount, 1000)

    def test_component_without_own_amount_sums_children(self):
        component = Component.objects.create(category=self.category, name='Component 1')
        Component.objects.create(parent=component, name='Sub-component 1', amount=300)
        Component.objects.create(parent=component, name='Sub-component 2', amount=200)

        self.assertEqual(component.effective_amount, 500)
        self.assertEqual(self.category.effective_amount, 500)

    def test_own_amount_and_children_are_never_both_counted(self):
        """A component with an own amount set must NOT also add its children's amounts."""
        component = Component.objects.create(category=self.category, name='Component 1', amount=1000)
        Component.objects.create(parent=component, name='Sub-component 1', amount=999999)

        self.assertEqual(component.effective_amount, 1000)
        self.assertEqual(self.category.effective_amount, 1000)

    def test_category_sums_only_its_direct_components_not_orphan_subcomponents(self):
        """A sub-component's amount must only roll up through its parent component,
        never counted directly at the category level even if it also carries a
        (redundant, optional) direct `category` FK."""
        component = Component.objects.create(category=self.category, name='Component 1')
        subcomponent = Component.objects.create(parent=component, name='Sub-component 1', amount=300)
        subcomponent.category = self.category  # optional direct link, allowed per business decision
        subcomponent.save()

        self.assertEqual(self.category.effective_amount, 300)

    def test_category_sums_multiple_components(self):
        Component.objects.create(category=self.category, name='Component 1', amount=100)
        Component.objects.create(category=self.category, name='Component 2', amount=250)
        self.assertEqual(self.category.effective_amount, 350)
