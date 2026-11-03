"""Which IDA projects a page shows data for.

The selected project (session `project_id`) comes with its linked projects, parents and children
(session `tree_structure_projects_ids`, e.g. COSO → FA-COSO → FA2-COSO): by default a page shows
the data of all of them. The page's "Project" filter narrows it to one. Only the projects the user
works on (DCC link table, see cosomis.services.get_user_projects) are ever offered or shown."""
from functools import wraps
from urllib.parse import urlencode

from django.shortcuts import redirect
from django.urls import reverse

from cosomis.services import get_user_projects
from subprojects.models import Project

FILTER_PARAM = 'project'


def project_required(view):
    """Function views: send the user to the project selection page first, like PageMixin does."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated and not (request.session.get('project_id')
                                                  and request.session.get('tree_structure_projects_ids')):
            return redirect(f"{reverse('process_manager:list')}?{urlencode({'next': request.get_full_path()})}")
        return view(request, *args, **kwargs)
    return wrapper


class ProjectRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        return project_required(super().dispatch)(request, *args, **kwargs)


def linked_project_ids(project_id):
    """The project, all its parents up to the root, and all its descendants at any depth, in tree order.

    (Project.build_the_tree_structure stops at direct children: from COSO it keeps FA-COSO but not FA2-COSO.)"""
    parents = dict(Project.objects.values_list('pk', 'parent_id'))
    if project_id not in parents:
        return []
    ancestors, current = [], parents[project_id]
    while current is not None and current not in ancestors:
        ancestors.insert(0, current)
        current = parents.get(current)
    children = {}
    for pk, parent in sorted(parents.items()):
        children.setdefault(parent, []).append(pk)
    descendants, stack = [], [project_id]
    while stack:
        node = stack.pop(0)
        descendants.append(node)
        stack[:0] = [c for c in children.get(node, []) if c not in descendants and c not in ancestors]
    return ancestors + descendants


class ProjectScope:
    def __init__(self, request):
        tree_ids = linked_project_ids(request.session.get('project_id')) or (
            request.session.get('tree_structure_projects_ids') or [])
        user_project_names = {name for _id, name in get_user_projects(request.user)}
        # Linked projects of the selection, in the tree order, that the user works on.
        by_id = {p.pk: p for p in Project.objects.filter(pk__in=tree_ids, name__in=user_project_names)}
        self.projects = [by_id[pk] for pk in tree_ids if pk in by_id]
        self.available_ids = [p.pk for p in self.projects]
        selected = request.GET.get(FILTER_PARAM, '')
        self.selected_id = int(selected) if selected.isdigit() and int(selected) in self.available_ids else None
        self.ids = [self.selected_id] if self.selected_id else self.available_ids

    def contains(self, project_ids):
        """True if one of `project_ids` is in the scope of the page."""
        return bool(set(project_ids) & set(self.ids))

    def context(self):
        return {'scope_projects': self.projects, 'scope_selected_id': self.selected_id,
                'scope_all_names': ", ".join(p.name for p in self.projects)}
