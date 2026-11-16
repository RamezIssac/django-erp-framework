"""
Fast row rendering for prepopulated inline grids.

A journal sheet is hundreds of rows x ~15 inputs. Rendering each input through
Django's widget templates dominates page time (~2 ms per row), so plain
``<input>`` widgets are rendered here with string formatting, producing the
same markup as ``django/forms/widgets/input.html``. Any other widget (selects,
custom widgets, widgets with an overridden ``render``/``get_context``) falls
back to the regular ``BoundField`` rendering.
"""

from django import forms, template
from django.forms.widgets import Input
from django.utils.html import conditional_escape, escape
from django.utils.safestring import mark_safe

register = template.Library()

_INPUT_TEMPLATES = {
    f"django/forms/widgets/{name}.html"
    for name in ("input", "text", "number", "hidden", "email", "url", "tel", "search")
}
_CHECKBOX_TEMPLATE = "django/forms/widgets/checkbox.html"


def _is_fast(widget):
    cls = type(widget)
    if cls.render is not forms.Widget.render:
        return False
    if isinstance(widget, forms.CheckboxInput):
        return cls.get_context is forms.CheckboxInput.get_context and widget.template_name == _CHECKBOX_TEMPLATE
    return (
        isinstance(widget, Input)
        and cls.get_context is Input.get_context
        and widget.template_name in _INPUT_TEMPLATES
    )


def _attrs_html(attrs):
    # Mirrors django/forms/widgets/attrs.html
    out = []
    for name, value in attrs.items():
        if value is False or value is None:
            continue
        if value is True:
            out.append(f" {name}")
        else:
            out.append(f' {name}="{escape(value)}"')
    return "".join(out)


def render_bound_field(bound_field):
    """Render a ``BoundField`` widget, fast for plain inputs."""
    field = bound_field.field
    widget = field.widget
    if field.show_hidden_initial or not _is_fast(widget):
        return str(bound_field)
    if field.localize:
        widget.is_localized = True
    attrs = bound_field.build_widget_attrs({}, widget)
    if bound_field.auto_id and "id" not in widget.attrs:
        attrs.setdefault("id", bound_field.auto_id)
    attrs = {**widget.attrs, **attrs}
    raw = bound_field.value()
    if isinstance(widget, forms.CheckboxInput) and widget.check_test(raw):
        attrs["checked"] = True
    value = widget.format_value(raw)
    value_html = "" if value is None else f' value="{escape(value)}"'
    return f'<input type="{widget.input_type}" name="{escape(bound_field.html_name)}"{value_html}{_attrs_html(attrs)}>'


def _render_row(inline_admin_formset, inline_admin_form, index, colspan):
    form = inline_admin_form.form
    prefix = inline_admin_formset.formset.prefix
    parts = []
    errors = form.non_field_errors()
    if errors:
        parts.append(f'<tr class="row-form-errors"><td colspan="{colspan}">{errors}</td></tr>')

    hidden, cells = [], []
    if inline_admin_form.needs_explicit_pk_field():
        hidden.append(render_bound_field(inline_admin_form.pk_field().field))
    fk_field = inline_admin_form.fk_field()
    if fk_field:
        hidden.append(render_bound_field(fk_field.field))
    for fieldset in inline_admin_form:
        for line in fieldset:
            for admin_field in line:
                if admin_field.is_readonly:
                    name = admin_field.field["name"]
                    cells.append(f'<td class="field-{name}"><p>{conditional_escape(admin_field.contents())}</p></td>')
                    continue
                bound = admin_field.field
                if bound.field.widget.is_hidden:
                    hidden.append(render_bound_field(bound))
                    continue
                error_html = ""
                if bound.errors:
                    error_html = f'<div class="help-block text-danger small">{bound.errors.as_ul()}</div>'
                cells.append(f'<td class="field-{bound.name}">{render_bound_field(bound)}{error_html}</td>')

    row_class = "form-row has_original" if inline_admin_form.original else "form-row"
    parts.append(
        f'<tr class="{row_class}" id="{prefix}-{index}"><td class="original">{"".join(hidden)}</td>'
        f'{"".join(cells)}</tr>'
    )
    return "".join(parts)


@register.simple_tag
def erp_grid_rows(inline_admin_formset):
    """All rows of a prepopulated inline (without Django's empty-form template row)."""
    def visible(field):
        widget = field["widget"]
        return not (widget.get("is_hidden") if isinstance(widget, dict) else widget.is_hidden)

    colspan = len([f for f in inline_admin_formset.fields() if visible(f)]) + 1
    rows = []
    index = 0
    for inline_admin_form in inline_admin_formset:
        if inline_admin_form.form.prefix.endswith("__prefix__"):
            continue  # empty-form template: rows are locked, never cloned
        rows.append(_render_row(inline_admin_formset, inline_admin_form, index, colspan))
        index += 1
    return mark_safe("".join(rows))
