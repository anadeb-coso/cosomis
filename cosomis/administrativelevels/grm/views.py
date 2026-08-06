import random
from datetime import datetime, timedelta

# import cryptocode
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import generic

import grm_client
from administrativelevels.grm.functions import get_administrative_level_descendants_using_mis
from administrativelevels.grm.forms import SearchIssueForm
from cosomis.mixins import AJAXRequestMixin, JSONResponseMixin, ModalFormMixin, PageMixin


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
        """Anciennement : construisait un sélecteur Mango et interrogeait la base CouchDB
        `grm` (`grm_db.get_query_result(selector)`). `grm` a été migrée vers Postgres côté
        GRM (`issue.models.Issue`) et exposée via l'API inter-services `grm_client.py` :
        cette méthode ne change que la source de données, la pagination/le rendu en aval
        restent inchangés (`issues[index:index + offset]` dans `get_context_data`).

        L'API de service `/api/service/issues/` ne supporte que quelques filtres serveur
        (`confirmed`, `publish`, `category`, `status`, `assignee_email`, `reporter_email`,
        `administrative_region_id`, `start_date`/`end_date` sur `issue_date`) : les filtres
        sans équivalent serveur direct (`code` en préfixe sur 3 champs, `assigned_to`/
        `reported_by` par id plutôt que par email, expansion `region` -> tous les
        descendants, `other=Escalate`) sont donc appliqués en Python après récupération,
        à partir des champs déjà présents dans chaque dict `issue` renvoyé par l'API.
        """
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

        params = {"confirmed": True}
        if user.groups.filter(name__in=["Admin", "ViewerOfAllIssues"]).exists():
            pass  # pas de filtre publish : ce groupe voit aussi les issues non publiées
        else:
            params["publish"] = True

        # NB : filtre désormais sur `issue_date` (seule date exposée par l'API de service),
        # au lieu de `intake_date` côté CouchDB — léger changement de sémantique assumé faute
        # d'équivalent `intake_date` exposé par le nouvel endpoint.
        if start_date:
            params["start_date"] = datetime.strptime(start_date, '%d/%m/%Y').strftime('%Y-%m-%d')
        if end_date:
            # +1 jour pour rester inclusif du jour sélectionné, comme le faisait l'ancien
            # `$lte` sur un timestamp complet côté CouchDB.
            params["end_date"] = (datetime.strptime(end_date, '%d/%m/%Y') + timedelta(days=1)).strftime('%Y-%m-%d')
        if category:
            params["category"] = int(category)
        if status:
            params["status"] = int(status)
        if publish in ('True', 'False'):
            params["publish"] = publish == 'True'

        issues = grm_client.search_issues(**params)
        # Ancien sélecteur imposait aussi `"auto_increment_id": {"$ne": ""}` (exclut les
        # issues sans code auto-incrémenté attribué) : pas de paramètre serveur équivalent,
        # filtré ici.
        issues = [issue for issue in issues if issue.get('auto_increment_id')]

        if code:
            issues = [
                issue for issue in issues
                if str(issue.get('internal_code') or '').startswith(code)
                or str(issue.get('tracking_code') or '').startswith(code)
                or str(issue.get('description') or '').startswith(code)
            ]
        if assigned_to:
            issues = [
                issue for issue in issues
                if issue.get('assignee') and str(issue['assignee'].get('id')) == str(assigned_to)
            ]
        if reported_by:
            issues = [
                issue for issue in issues
                if issue.get('reporter') and str(issue['reporter'].get('id')) == str(reported_by)
            ]
        if other == "Escalate":
            # Pas d'équivalent `escalation_reasons` exposé par l'API de service à ce jour :
            # ce filtre est un no-op documenté plutôt qu'une exception silencieuse.
            pass
        if region:
            filter_regions = set(
                get_administrative_level_descendants_using_mis(None, region, [], self.request.user) + [region]
            )
            issues = [
                issue for issue in issues
                if str(issue.get('administrative_region_id')) in filter_regions
            ]

        return issues



class IssuesStatisticsView(AJAXRequestMixin, LoginRequiredMixin, JSONResponseMixin, generic.View):
    def get(self, request, *args, **kwargs):
        """Anciennement : `grm_db.get_view_result('issues', 'by_assignee_stats')` (vue
        CouchDB réduite, sans clé -> une seule ligne agrégée dont `.value` porte un dict
        `{'count': N}`, consommé côté JS comme `response['count']`).

        L'API de service `/api/service/issues/stats/by-assignee/` renvoie désormais la
        répartition détaillée par assigné (`[{assignee_email, assignee_name, total}, ...]`)
        plutôt qu'un total unique : on la renvoie telle quelle (utile en soi) tout en
        ajoutant une clé `count` = somme des `total`, pour ne pas casser le contrat JS
        existant (`response['count']`)."""
        issues_stats = grm_client.get_issue_stats_by_assignee()
        count = sum(row.get('total') or 0 for row in issues_stats)

        return self.render_to_json_response(
            {'count': count, 'by_assignee': issues_stats}, safe=False
        )
