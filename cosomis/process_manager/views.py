from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views import generic
from django.db.models import Q
from datetime import datetime
from django.utils.translation import gettext_lazy
from django.urls import reverse_lazy
from django.conf import settings
from django.shortcuts import resolve_url
from django.http import HttpResponseRedirect
from django.contrib import messages

from cosomis.mixins import PageMixin
from subprojects.models import Project
from cosomis.services import get_user_projects

class ProjectListView(PageMixin, LoginRequiredMixin, generic.ListView):
    model = Project
    template_name = 'process_manager/list.html'
    context_object_name = 'projects'
    title = gettext_lazy('Projects')
    active_level1 = 'projects'
    breadcrumb = [
       {
                'url': '',
                'title': title
            },
    ]

    def get(self, request, *args, **kwargs):
        projects = self.get_queryset()
        project_id = self.request.GET.get('project_id')
        
        if project_id is not None:
            projects = projects.filter(id=int(project_id))
        if len(projects) == 1:
            self.request.session['project_id'] = projects[0].id
            self.request.session['project_name'] = projects[0].name
            tree_structure_projects = projects[0].build_the_tree_structure()
            self.request.session['tree_structure_projects_ids'] = [p.id for p in tree_structure_projects]
            self.request.session['tree_structure_projects_names'] = [p.name for p in tree_structure_projects]
            
            next_page = self.request.GET.get('next')
            if next_page:
                return HttpResponseRedirect(resolve_url(next_page or settings.LOGIN_REDIRECT_URL))
            return redirect('dashboard:dashboard')
        
        return super().get(request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        projects = get_user_projects(self.request.user)

        context['projects'] = list(self.object_list.filter(name__in=[p[1] for p in projects]))
        context['next_url'] = self.request.GET.get('next')

        return context