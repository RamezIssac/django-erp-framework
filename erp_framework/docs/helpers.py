def user_can_access_docs(request):
    """
    Default whole-guide access function: any active staff member.

    The views are additionally wrapped in ``erp_admin_site.admin_view``, so
    anonymous and non-staff users never reach this check.
    """
    user = request.user
    return user.is_active and user.is_staff
