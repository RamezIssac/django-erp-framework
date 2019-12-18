from inspect import getfullargspec

from django.template import Library
from django.template.library import InclusionNode, parse_bits
from django.template.loader import get_template

register = Library()
from django.contrib.admin.templatetags.admin_list import result_list, pagination, date_hierarchy, search_form, admin_actions
from django.contrib.admin.templatetags.admin_modify import submit_row

from ra.base import app_settings

class InclusionAdminNode(InclusionNode):
    """
    Template tag that allows its template to be overridden per model, per app,
    or globally.
    """

    def __init__(self, parser, token, func, template_name, takes_context=True):
        self.template_name = template_name
        params, varargs, varkw, defaults, kwonly, kwonly_defaults, _ = getfullargspec(func)
        bits = token.split_contents()
        args, kwargs = parse_bits(
            parser, bits[1:], params, varargs, varkw, defaults, kwonly,
            kwonly_defaults, takes_context, bits[0],
        )
        super().__init__(func, takes_context, args, kwargs, filename=None)

    def render(self, context):
        opts = context['opts']
        app_label = opts.app_label.lower()
        object_name = opts.object_name.lower()
        # Load template for this render call. (Setting self.filename isn't
        # thread-safe.)
        context.render_context[self] = context.template.engine.select_template([
            '%s/%s/%s' % (app_label, object_name, self.template_name),
            '%s/%s' % (app_label, self.template_name),
            '%s' % (self.template_name,),
        ])
        return super().render(context)


@register.tag(name='ra_result_list')
def result_list_tag(parser, token):
    return InclusionAdminNode(
        parser, token,
        func=result_list,
        template_name=f'{app_settings.RA_THEME}/change_list_results.html',
        takes_context=False,
    )


@register.tag(name='ra_pagination')
def pagination_tag(parser, token):
    return InclusionAdminNode(
        parser, token,
        func=pagination,
        template_name=f'{app_settings.RA_THEME}/pagination.html',
        takes_context=False,
    )


@register.tag(name='ra_date_hierarchy')
def date_hierarchy_tag(parser, token):
    return InclusionAdminNode(
        parser, token,
        func=date_hierarchy,
        template_name=f'{app_settings.RA_THEME}/date_hierarchy.html',
        takes_context=False,
    )


@register.tag(name='ra_search_form')
def search_form_tag(parser, token):
    return InclusionAdminNode(parser, token, func=search_form,
                              template_name=f'{app_settings.RA_THEME}/search_form.html', takes_context=False)


@register.tag(name='ra_admin_actions')
def admin_actions_tag(parser, token):
    return InclusionAdminNode(parser, token, func=admin_actions, template_name=f'{app_settings.RA_THEME}/actions.html')


@register.tag(name='ra_change_list_object_tools')
def change_list_object_tools_tag(parser, token):
    """Display the row of change list object tools."""
    return InclusionAdminNode(
        parser, token,
        func=lambda context: context,
        template_name=f'{app_settings.RA_THEME}/change_list_object_tools.html',
    )


@register.tag(name='ra_change_form_object_tools')
def change_form_object_tools_tag(parser, token):
    """Display the row of change form object tools."""
    return InclusionAdminNode(
        parser, token,
        func=lambda context: context,
        template_name=f'{app_settings.RA_THEME}/change_form_object_tools.html',
    )


@register.simple_tag
def ra_admin_list_filter(cl, spec):
    tpl = get_template(f'{app_settings.RA_THEME}/filter.html')
    return tpl.render({
        'title': spec.title,
        'choices': list(spec.choices(cl)),
        'spec': spec,
    })




@register.tag(name='ra_submit_row')
def submit_row_tag(parser, token):
    return InclusionAdminNode(parser, token, func=submit_row, template_name=f'{app_settings.RA_THEME}/submit_line.html')
