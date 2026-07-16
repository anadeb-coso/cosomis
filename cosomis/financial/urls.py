from django.urls import path
from django.conf.urls import include

from financial import (
    views, views_bank_transfer, views_disbursement_request,
    views_disbursement, views_account, views_dashboard,
    views_funding, views_category, views_component, views_project,
    views_ptba, views_supporting_document,
)

app_name = 'financial'



urlpatterns = [
    path('', views.FinancialTemplateView.as_view(), name='financials'), # financial path
    path('allocations', views.AdministrativeLevelAllocationsListView.as_view(), name='allocations_list'), # allocations list path
    path('allocation/create/', views.AdministrativeLevelAllocationCreateView.as_view(), name='allocation_create'), # allocation path to create
    path('allocation/update/<int:pk>/', views.AdministrativeLevelAllocationUpdateView.as_view(), name='allocation_update'), # allocation path to update
    path('allocation/detail/<int:pk>/', views.AdministrativeLevelAllocationDetailView.as_view(), name='allocation_detail'), #The path of the detail of allocation
    path('allocation/delete/<int:pk>/', views.AdministrativeLevelAllocationDeleteView.as_view(), name='allocation_delete'),
    path('allocation/export/', views.AdministrativeLevelAllocationExportView.as_view(), name='allocation_export'),

    path('bank-transfers', views_bank_transfer.BankTransfersListView.as_view(), name='bank_transfers_list'), # bank transfers list path
    path('bank-transfer/create/', views_bank_transfer.BankTransferCreateView.as_view(), name='bank_transfer_create'), # bank transfer path to create
    path('bank-transfer/update/<int:pk>/', views_bank_transfer.BankTransferUpdateView.as_view(), name='bank_transfer_update'), # bank transfer path to update
    path('bank-transfer/detail/<int:pk>/', views_bank_transfer.BankTransferDetailView.as_view(), name='bank_transfer_detail'), #The path of the detail of bank transfer
    path('bank-transfer/delete/<int:pk>/', views_bank_transfer.BankTransferDeleteView.as_view(), name='bank_transfer_delete'),
    path('bank-transfer/export/', views_bank_transfer.BankTransferExportView.as_view(), name='bank_transfer_export'),
    path('bank-transfer/status/<int:pk>/', views_bank_transfer.BankTransferStatusUpdateView.as_view(), name='bank_transfer_status_update'),
    path('bank-transfers/status/bulk/', views_bank_transfer.BankTransferBulkStatusUpdateView.as_view(), name='bank_transfer_bulk_status_update'),
    
    path('disbursement-requests', views_disbursement_request.DisbursementRequestsListView.as_view(), name='disbursement_requests_list'),
    path('disbursement-request/create/', views_disbursement_request.DisbursementRequestCreateView.as_view(), name='disbursement_request_create'), 
    path('disbursement-request/update/<int:pk>/', views_disbursement_request.DisbursementRequestUpdateView.as_view(), name='disbursement_request_update'), 
    path('disbursement-request/detail/<int:pk>/', views_disbursement_request.DisbursementRequestDetailView.as_view(), name='disbursement_request_detail'),
    path('disbursement-request/delete/<int:pk>/', views_disbursement_request.DisbursementRequestDeleteView.as_view(), name='disbursement_request_delete'),
    path('disbursement-request/export/', views_disbursement_request.DisbursementRequestExportView.as_view(), name='disbursement_request_export'),
    path('disbursement-request/<int:disbursement_request_pk>/validation/create/', views_disbursement_request.DisbursementRequestValidationCreateView.as_view(), name='disbursement_request_validation_create'),
    path('disbursement-request-validation/update/<int:pk>/', views_disbursement_request.DisbursementRequestValidationUpdateView.as_view(), name='disbursement_request_validation_update'),
    path('disbursement-request-validation/delete/<int:pk>/', views_disbursement_request.DisbursementRequestValidationDeleteView.as_view(), name='disbursement_request_validation_delete'),

    path('disbursements', views_disbursement.DisbursementsListView.as_view(), name='disbursements_list'),
    path('disbursement/create/', views_disbursement.DisbursementCreateView.as_view(), name='disbursement_create'), 
    path('disbursement/update/<int:pk>/', views_disbursement.DisbursementUpdateView.as_view(), name='disbursement_update'), 
    path('disbursement/detail/<int:pk>/', views_disbursement.DisbursementDetailView.as_view(), name='disbursement_detail'),
    path('disbursement/delete/<int:pk>/', views_disbursement.DisbursementDeleteView.as_view(), name='disbursement_delete'),
    path('disbursement/export/', views_disbursement.DisbursementExportView.as_view(), name='disbursement_export'),

    path('accounts', views_account.AccountListView.as_view(), name='account_list'),
    path('account/create/', views_account.AccountCreateView.as_view(), name='account_create'),
    path('account/update/<int:pk>/', views_account.AccountUpdateView.as_view(), name='account_update'),
    path('account/delete/<int:pk>/', views_account.AccountDeleteView.as_view(), name='account_delete'),
    path('account/detail/<int:pk>/', views_account.AccountDetailView.as_view(), name='account_detail'),
    path('account/export/', views_account.AccountExportView.as_view(), name='account_export'),

    path('account-balances', views_account.AccountBalancesListView.as_view(), name='account_balances_list'),
    path('dashboard', views_dashboard.FinancialDashboardView.as_view(), name='financial_dashboard'),
    path('dashboard/export/', views_dashboard.FinancialDashboardExportView.as_view(), name='financial_dashboard_export'),

    path('fundings', views_funding.FundingListView.as_view(), name='funding_list'),
    path('funding/create/', views_funding.FundingCreateView.as_view(), name='funding_create'),
    path('funding/update/<int:pk>/', views_funding.FundingUpdateView.as_view(), name='funding_update'),
    path('funding/delete/<int:pk>/', views_funding.FundingDeleteView.as_view(), name='funding_delete'),
    path('funding/detail/<int:pk>/', views_funding.FundingDetailView.as_view(), name='funding_detail'),
    path('funding/export/', views_funding.FundingExportView.as_view(), name='funding_export'),

    path('categories', views_category.CategoryListView.as_view(), name='category_list'),
    path('category/create/', views_category.CategoryCreateView.as_view(), name='category_create'),
    path('category/update/<int:pk>/', views_category.CategoryUpdateView.as_view(), name='category_update'),
    path('category/delete/<int:pk>/', views_category.CategoryDeleteView.as_view(), name='category_delete'),
    path('category/detail/<int:pk>/', views_category.CategoryDetailView.as_view(), name='category_detail'),
    path('category/export/', views_category.CategoryExportView.as_view(), name='category_export'),

    path('components', views_component.ComponentListView.as_view(), name='component_list'),
    path('component/create/', views_component.ComponentCreateView.as_view(), name='component_create'),
    path('component/update/<int:pk>/', views_component.ComponentUpdateView.as_view(), name='component_update'),
    path('component/detail/<int:pk>/', views_component.ComponentDetailView.as_view(), name='component_detail'),
    path('component/export/', views_component.ComponentExportView.as_view(), name='component_export'),

    path('projects-ida', views_project.ProjectIDAListView.as_view(), name='project_ida_list'),
    path('project-ida/create/', views_project.ProjectIDACreateView.as_view(), name='project_ida_create'),
    path('project-ida/update/<int:pk>/', views_project.ProjectIDAUpdateView.as_view(), name='project_ida_update'),
    path('project-ida/detail/<int:pk>/', views_project.ProjectIDADetailView.as_view(), name='project_ida_detail'),
    path('project-ida/export/', views_project.ProjectIDAExportView.as_view(), name='project_ida_export'),
    path('project-ida/export/<int:pk>/', views_project.ProjectIDAExportDetailView.as_view(), name='project_ida_export_detail'),

    path('ptbas', views_ptba.AnnualWorkPlanListView.as_view(), name='annual_work_plan_list'),
    path('ptba/create/', views_ptba.AnnualWorkPlanCreateView.as_view(), name='annual_work_plan_create'),
    path('ptba/update/<int:pk>/', views_ptba.AnnualWorkPlanUpdateView.as_view(), name='annual_work_plan_update'),
    path('ptba/delete/<int:pk>/', views_ptba.AnnualWorkPlanDeleteView.as_view(), name='annual_work_plan_delete'),
    path('ptba/detail/<int:pk>/', views_ptba.AnnualWorkPlanDetailView.as_view(), name='annual_work_plan_detail'),
    path('ptba/export/', views_ptba.AnnualWorkPlanExportView.as_view(), name='annual_work_plan_export'),
    path('ptba/<int:annual_work_plan_pk>/activity/create/', views_ptba.ActivityCreateView.as_view(), name='activity_create'),
    path('activity/update/<int:pk>/', views_ptba.ActivityUpdateView.as_view(), name='activity_update'),
    path('activity/delete/<int:pk>/', views_ptba.ActivityDeleteView.as_view(), name='activity_delete'),

    path('supporting-documents', views_supporting_document.SupportingDocumentListView.as_view(), name='supporting_document_list'),
    path('supporting-document/create/', views_supporting_document.SupportingDocumentCreateView.as_view(), name='supporting_document_create'),
    path('supporting-document/update/<int:pk>/', views_supporting_document.SupportingDocumentUpdateView.as_view(), name='supporting_document_update'),
    path('supporting-document/delete/<int:pk>/', views_supporting_document.SupportingDocumentDeleteView.as_view(), name='supporting_document_delete'),
    path('supporting-document/detail/<int:pk>/', views_supporting_document.SupportingDocumentDetailView.as_view(), name='supporting_document_detail'),
    path('supporting-document/export/', views_supporting_document.SupportingDocumentExportView.as_view(), name='supporting_document_export'),
]