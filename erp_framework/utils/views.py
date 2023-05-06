import re

eastern_western_map = {
    1776: 48,  # 0
    1777: 49,  # 1
    1778: 50,  # 2
    1779: 51,  # 3
    1780: 52,  # 4
    1781: 53,  # 5
    1782: 54,  # 6
    1783: 55,  # 7
    1784: 56,  # 8
    1785: 57,  # 9
    # another ord
    1632: 48,  # 0
    1633: 49,  # 1
    1634: 50,  # 2
    1635: 51,  # 3
    1636: 52,  # 4
    1637: 53,  # 5
    1638: 54,  # 6
    1639: 55,  # 7
    1640: 56,  # 8
    1641: 57,  # 9
}  # 9

re_time_series = re.compile("TS\d+")


def get_typed_reports_map(typed_reports, only_report_slug=None):
    """
    # todo revise
    :param typed_reports:
    :param only_report_slug:
    :return:
    """
    reports = typed_reports

    reports_map = {
        "slugs": [],
        "reports": [],
    }

    for report in reports:
        view = report
        if not only_report_slug or only_report_slug == view.get_report_slug():
            if True:  # user.has_perm(view_perm):
                reports_map["slugs"].append(view.get_report_slug())
                reports_map["reports"].append(view)
    return reports_map


def apply_order_to_typed_reports(lst, order_list):
    values = []
    unordered = list(lst)
    for o in order_list:
        for x in unordered:
            if x.get_report_slug() == o:
                values.append(x)
                unordered.remove(x)
    values += unordered
    return values


def get_typed_reports_for_templates(
    model_name, user=None, request=None, only_report_slug=None, load_func=None
):
    from erp_framework.reporting.registry import report_registry

    load_func = load_func or report_registry.get_report_classes_by_namespace
    reports = load_func(model_name)
    report_list = []
    user_reports = request.session.get("user_reports", [])
    for report in reports:
        view = report
        if not only_report_slug or only_report_slug == view.get_report_slug():
            view_perm = "%s.%s_view" % (
                view.get_base_model_name(),
                view.get_report_slug(),
            )
            if view_perm in user_reports or user.is_superuser:
                report_list.append(view)

    return report_list
