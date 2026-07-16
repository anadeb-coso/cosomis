from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from urllib.parse import urlencode


class SoftDeleteViewMixin:
    """Swaps a generic DeleteView's real DB delete for a soft delete
    (`is_deleted=True`, see `cosomis.models_base.SoftDeleteMixin`), so the
    object's BaseModel.users_involved history survives past its "deletion" -
    the deletion itself just becomes one more diffed save() entry in that same
    history. DeleteView routes POST through form_valid() (self.object is set by
    post() before form_valid() runs), so this overrides form_valid() rather
    than delete()."""

    def form_valid(self, form):
        success_url = self.get_success_url()
        self.object.soft_delete(user=self.request.user)
        return HttpResponseRedirect(success_url)


class PageMixin(object):
    title = None
    active_level1 = None
    active_level2 = None
    breadcrumb = None
    form_mixin = None

    def get_context_data(self, **kwargs):
        ctx = super(PageMixin, self).get_context_data(**kwargs)
        ctx.setdefault('title', self.title)
        ctx.setdefault('active_level1', self.active_level1)
        ctx.setdefault('active_level2', self.active_level2)
        ctx.setdefault('breadcrumb', self.breadcrumb)
        ctx.setdefault('form_mixin', self.form_mixin)
        return ctx
    
    def dispatch(self, request, *args, **kwargs):
        next_url = self.request.get_full_path()
        if "/process-manager/select-project/" not in next_url and self.request.user.is_authenticated and (
            not self.request.session.get('project_id') or not self.request.session.get('tree_structure_projects_ids')
        ): # If the user is authenticated and no project selected
           
            url = reverse('process_manager:list')
            query_params = {}
            if next_url:
                query_params['next'] = next_url
            url_with_params = f"{url}?{urlencode(query_params)}"
            return redirect(url_with_params)
        return super().dispatch(request, *args, **kwargs)


class ModalFormMixin(object):
    template_name = 'common/modal_form.html'
    id_form = 'form'
    title = None
    subtitle = None
    picture = None
    picture_class = None
    submit_button = None
    form_class_color = 'primary'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault('id_form', self.id_form)
        ctx.setdefault('title', self.title)
        ctx.setdefault('subtitle', self.subtitle)
        ctx.setdefault('picture', self.picture)
        ctx.setdefault('picture_class', self.picture_class)
        ctx.setdefault('submit_button', self.submit_button)
        ctx.setdefault('form_class_color', self.form_class_color)
        return ctx


class ModalListMixin(object):
    template_name = 'common/modal_list.html'
    id_list = 'list'
    title = None
    subtitle = None
    picture = None
    picture_class = None
    submit_button = None
    list_class_color = 'primary'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault('id_list', self.id_list)
        ctx.setdefault('title', self.title)
        ctx.setdefault('subtitle', self.subtitle)
        ctx.setdefault('picture', self.picture)
        ctx.setdefault('picture_class', self.picture_class)
        ctx.setdefault('submit_button', self.submit_button)
        ctx.setdefault('list_class_color', self.list_class_color)
        return ctx
    

class AJAXRequestMixin:
    def dispatch(self, request, *args, **kwargs):
        if request.headers.get('x-requested-with') != 'XMLHttpRequest':
            raise Http404
        return super().dispatch(request, *args, **kwargs)


class JSONResponseMixin:
    def render_to_json_response(self, context, **response_kwargs):
        return JsonResponse(self.get_data(context), **response_kwargs)

    def get_data(self, context):
        return context
