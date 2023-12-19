import random
from datetime import datetime, timedelta

# import cryptocode
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import generic

from administrativelevels.grm.functions import get_administrative_level_descendants_using_mis
from administrativelevels.grm.forms import SearchIssueForm
from cosomis.mixins import AJAXRequestMixin, JSONResponseMixin, ModalFormMixin, PageMixin
from no_sql_client import NoSQLClient


COUCHDB_GRM_DATABASE = settings.COUCHDB_GRM_DATABASE
COUCHDB_DATABASE_ADMINISTRATIVE_LEVEL = settings.COUCHDB_DATABASE_ADMINISTRATIVE_LEVEL
COUCHDB_GRM_ATTACHMENT_DATABASE = settings.COUCHDB_GRM_ATTACHMENT_DATABASE

class ReviewIssuesFormView(AJAXRequestMixin, LoginRequiredMixin, generic.FormView):
    form_class = SearchIssueForm
    template_name = 'grm/review_issues.html'
    administrative_id = None
    def get_form_kwargs(self):
        self.initial = {'administrative_id': self.administrative_id}
        return super().get_form_kwargs()

    def dispatch(self, request, administrative_id, *args, **kwargs):
        self.administrative_id = administrative_id
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['publish_option'] = False
        context['current_region_id'] = self.administrative_id
        
        if user.groups.filter().exists():
            context['publish_option'] = True
        return context


class IssueListView(AJAXRequestMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'grm/issue_list.html'
    context_object_name = 'issues'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        index = int(self.request.GET.get('index'))
        offset = int(self.request.GET.get('offset'))
        issues = self.get_results()
        context['total_issues'] = len(list(issues))
        context['issues'] = issues[index:index + offset]
        return context
    
    def get_queryset(self):
        return []
    
    def get_results(self):
        nsc = NoSQLClient()
        grm_db = nsc.get_db(COUCHDB_GRM_DATABASE)
        adl_db = nsc.get_db(COUCHDB_DATABASE_ADMINISTRATIVE_LEVEL)
        index = int(self.request.GET.get('index'))
        offset = int(self.request.GET.get('offset'))
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        code = self.request.GET.get('code')
        assigned_to = self.request.GET.get('assigned_to')
        category = self.request.GET.get('category')
        status = self.request.GET.get('status')
        other = self.request.GET.get('other')
        region = self.request.GET.get('region')
        reported_by = self.request.GET.get('reported_by')
        publish = self.request.GET.get('publish')
        user = self.request.user

        if user.groups.filter(name__in=["Admin", "ViewerOfAllIssues"]).exists():
            selector = {
                "type": "issue",
                "confirmed": True,
                "auto_increment_id": {"$ne": ""},
            }
        else:
            selector = {
                "type": "issue",
                "publish": True,
                "confirmed": True,
                "auto_increment_id": {"$ne": ""},
            }
            
        date_range = {}
        if start_date:
            start_date = datetime.strptime(start_date, '%d/%m/%Y').strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            date_range["$gte"] = start_date
            selector["intake_date"] = date_range
        if end_date:
            end_date = (datetime.strptime(end_date, '%d/%m/%Y') + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            date_range["$lte"] = end_date
            selector["intake_date"] = date_range
        if code:
            code_filter = {"$regex": f"^{code}"}
            selector['$or'] = [{"internal_code": code_filter}, {"tracking_code": code_filter},
                               {"description": code_filter}]
        if assigned_to:
            selector["assignee.id"] = int(assigned_to)
        if category:
            selector["category.id"] = int(category)
        # if issue_type:
        #     selector["issue_type.id"] = int(issue_type)
        if status:
            selector["status.id"] = int(status)
        if other:
            if other == "Escalate":
                selector["escalation_reasons"] = {"$exists": True}
        if reported_by:
            selector["reporter.id"] = int(reported_by)
        if publish in ('True', 'False'):
            selector["publish"] = True if publish == 'True' else False
        print("region : ", region)
        if region:
            filter_regions = get_administrative_level_descendants_using_mis(adl_db, region, [], self.request.user) + [region]
            
            selector["administrative_region.administrative_id"] = {
                "$in": filter_regions
            }
            
        return grm_db.get_query_result(selector)
    


class IssuesStatisticsView(AJAXRequestMixin, LoginRequiredMixin, JSONResponseMixin, generic.View):
    def get(self, request, *args, **kwargs):
        nsc = NoSQLClient()
        grm_db = nsc.get_db(COUCHDB_GRM_DATABASE)
        
        issues_stats = grm_db.get_view_result('issues', 'by_assignee_stats')

        if issues_stats[0]:
            issues_stats = issues_stats[0][0]['value']
        else:
            issues_stats = {'count': 0}

        return self.render_to_json_response(issues_stats, safe=False)
