"""Who may add or change data on the procurement and results framework pages."""
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

EDITOR_GROUPS = ('Accountant', 'Evaluator', 'Admin')


def can_edit(user):
    return user.is_authenticated and (user.is_superuser or user.groups.filter(name__in=EDITOR_GROUPS).exists())


class EditorRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return can_edit(self.request.user)


class SaveWithHistoryMixin:
    """ModelForm views: save through BaseModel history (who created/changed the record)."""
    page_title = None
    active_level1 = None
    back_url = None

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.save_and_return_object(self.request.user)
        form.save_m2m()
        from django.shortcuts import redirect
        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({'title': self.page_title, 'active_level1': self.active_level1, 'back_url': self.get_back_url()})
        return ctx

    def get_back_url(self):
        return self.back_url
