from django import template

from .. import access
from .. import settings as docs_settings

register = template.Library()


@register.simple_tag(takes_context=True)
def erp_docs_admin_link(context):
    """
    Context for the built-in admin-chrome link to the guide.

    Returns a dict ``{"visible": bool, "title": str}``; ``visible`` is True
    only when ``ERP_DOCS_SHOW_ADMIN_LINK`` is on and the current request
    passes the docs access function.
    """
    request = context.get("request")
    visible = (
        docs_settings.show_admin_link()
        and request is not None
        and access.user_can_access_guide(request)
    )
    return {"visible": visible, "title": docs_settings.get_title()}
