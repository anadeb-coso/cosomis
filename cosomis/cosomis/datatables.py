from django.db.models import F
from django.http import JsonResponse
from django.template.loader import get_template
from django.utils.translation import gettext_lazy as _


# Options of a table with the Copy / Excel / PDF buttons (which export the rows
# displayed) next to the page length select; the page must include
# components/datatable/export_buttons_js.html.
DATATABLE_EXPORT_BUTTONS_OPTIONS = {
    'dom': "<'row dt-toolbar'<'col-sm-12 col-md-6'l><'col-sm-12 col-md-6 text-right'B>>"
           "<'row'<'col-sm-12'tr>>"
           "<'row'<'col-sm-12 col-md-5'i><'col-sm-12 col-md-7'p>>",
    'buttons': ['copy', 'excel', 'pdf'],
}


class DatatableColumn:
    """One column of a server-side DataTables table.

    `ordering` is the ORM ordering of the column (a field name, an expression or
    a tuple of them), None when the column can't be sorted. `switchable` lists
    it in "Choose the columns to display". `css_class` goes on the header cell,
    e.g. 'all' so that Responsive never collapses the column.
    """

    def __init__(self, title, ordering=None, switchable=True, css_class=''):
        self.title = title
        self.ordering = ordering
        self.switchable = switchable
        self.css_class = css_class


class ServerSideDatatableMixin:
    """Server-side DataTables for a ListView, like the /investments/ list of the
    local development portal.

    The HTML page only renders the filters and an empty table: DataTables then
    fetches each page of rows from the same URL with `?format=datatables`, so
    the filters of the query string apply to every page and only the rows of
    the current page are queried and rendered.

    A view using it defines:
      - get_datatable_queryset(): the filtered (unpaginated) queryset;
      - get_datatable_columns(): the DatatableColumn of each table column;
      - datatable_row_template: template rendering one row, each cell wrapped in
        {% datatable_cell %}...{% enddatatable_cell %} (see custom_tags).
    """

    datatable_row_template = None
    datatable_page_length = 10
    datatable_length_menu = (10, 20, 50, 100)
    # DataTables "order" option: [[column index, 'asc' | 'desc'], ...]. Empty
    # keeps the ordering of get_datatable_queryset().
    datatable_default_order = ()
    datatable_options = None

    def get_datatable_queryset(self):
        raise NotImplementedError

    def get_datatable_columns(self):
        raise NotImplementedError

    def get_datatable_default_order(self):
        return [list(order) for order in self.datatable_default_order]

    def get_datatable_shared_context(self):
        """Context common to every row (e.g. permissions), computed once per page."""
        return {'user': self.request.user, 'request': self.request}

    def get_datatable_row_context(self, obj):
        return {'object': obj}

    def get_queryset(self):
        # Rows are served by datatable_response(), the page itself lists nothing.
        return self.model._default_manager.none()

    def get(self, request, *args, **kwargs):
        if request.GET.get('format') == 'datatables':
            return self.datatable_response()
        return super().get(request, *args, **kwargs)

    def get_datatable_config(self, columns):
        config = {
            'serverSide': True,
            'processing': True,
            'searching': False,
            'responsive': True,
            'pagingType': 'full_numbers',
            'pageLength': self.datatable_page_length,
            'lengthMenu': [
                list(self.datatable_length_menu) + [-1],
                list(self.datatable_length_menu) + [_('Show all')],
            ],
            'order': self.get_datatable_default_order(),
            'columns': [{'orderable': column.ordering is not None} for column in columns],
        }
        config.update(self.datatable_options or {})
        return config

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        columns = self.get_datatable_columns()
        ctx['datatable_columns'] = columns
        ctx['datatable_column_switches'] = [
            {'index': index, 'title': column.title}
            for index, column in enumerate(columns) if column.switchable
        ]
        ctx['datatable_config'] = self.get_datatable_config(columns)
        return ctx

    def _int_param(self, name, default):
        try:
            return int(self.request.GET.get(name, default))
        except (TypeError, ValueError):
            return default

    def get_datatable_ordering(self, queryset):
        columns = self.get_datatable_columns()
        ordering = []
        i = 0
        while 'order[%s][column]' % i in self.request.GET:
            index = self._int_param('order[%s][column]' % i, -1)
            descending = self.request.GET.get('order[%s][dir]' % i) == 'desc'
            spec = columns[index].ordering if 0 <= index < len(columns) else None
            for field in (spec if isinstance(spec, (list, tuple)) else [spec]):
                if field is not None:
                    ordering.append(_order_by(field, descending))
            i += 1

        if not ordering:
            ordering = list(queryset.query.order_by) or list(queryset.model._meta.ordering)
        # A unique tie-breaker so that OFFSET/LIMIT pages never overlap.
        if not any(o in ('pk', '-pk', 'id', '-id') for o in ordering if isinstance(o, str)):
            ordering.append('pk')
        return ordering

    def datatable_response(self):
        start = max(self._int_param('start', 0), 0)
        length = self._int_param('length', self.datatable_page_length)

        queryset = self.get_datatable_queryset()
        count = queryset.count()
        queryset = queryset.order_by(*self.get_datatable_ordering(queryset))
        objects = queryset[start:start + length] if length > 0 else queryset[start:]

        return JsonResponse({
            'draw': self._int_param('draw', 0),
            'recordsTotal': count,
            'recordsFiltered': count,
            'data': self.render_datatable_rows(objects),
        })

    def render_datatable_rows(self, objects):
        # Rendered without the request so the context processors (which query
        # the databases) don't run once per row.
        template = get_template(self.datatable_row_template)
        shared_context = self.get_datatable_shared_context()
        rows = []
        for obj in objects:
            cells = []
            context = dict(shared_context, **self.get_datatable_row_context(obj))
            context['datatable_cells'] = cells
            template.render(context)
            rows.append(cells)
        return rows


def _order_by(field, descending):
    """`field` (a field name, possibly '-' prefixed, or an expression) as an
    ORDER BY clause, empty values last in both directions."""
    if isinstance(field, str):
        if field.startswith('-'):
            field, descending = field[1:], not descending
        field = F(field)
    return field.desc(nulls_last=True) if descending else field.asc(nulls_last=True)


def get_filter_badges(form, labels):
    """The active filters of `form` as [{'label', 'value'}] for the filter
    badges of a list page; `labels` maps each field name to its label."""
    badges = []
    for name, label in labels.items():
        field = form.fields[name]
        values = field.initial if isinstance(field.initial, (list, tuple)) else [field.initial]
        values = [str(value) for value in values if value not in (None, '')]
        if values:
            choices = {str(key): text for key, text in getattr(field.widget, 'choices', [])}
            badges.append({'label': label, 'value': ', '.join(str(choices.get(v, v)) for v in values)})
    return badges
