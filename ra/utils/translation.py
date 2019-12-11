import re
import datetime

from django.template.defaultfilters import capfirst
from django.utils.translation import ugettext_lazy as o_ugettext, get_language

from ra.base.cache import get_cached_name
from ra.reporting.registry import field_registry


def ugettext(message):
    translated_msg = ''
    current_language = get_language()
    swap_name_prefix = True if current_language in ['ar'] else False
    if message == '' or message is None:
        return ''

    if message == '_control_' or message == '__doc_typeid__':
        return ''
    if '__doc_type_' in message and not '_MX' in message:
        """
        >>> __doc_type_client-cash-in__
        <<< _('client-cash-in')
        """

        z = message.split('__doc_type_')
        prefix = ''
        if z[1].startswith('quan_'):
            z = z[1].split('quan_')
            prefix = o_ugettext('quan')

        translatin = o_ugettext(z[1].split('__')[0])
        prefix = capfirst(prefix)
        translatin = capfirst(translatin)

        return u'%s %s' % (translatin, prefix)

    if '_MX' in message:

        magic_field_name = message.split('_MX')
        entity = magic_field_name[1]
        magic_field_name = ugettext(magic_field_name[0] + '__')
        id = entity.split('-')[1]
        entity = entity.split('-')[0]
        if id != '':
            name = get_cached_name(entity, id)
        else:
            name = o_ugettext('the rest')

        return u'%s - %s' % (magic_field_name, name)
    if message.startswith('__') and message.endswith('__'):  # normal magic field

        return field_registry.get_field_by_name(message).verbose_name

    if '__' in message:
        re_time_series = re.compile('TS\d+')
        is_time_field = re_time_series.findall(message)
        if is_time_field:
            time_series_option = is_time_field[0]
            field = message.replace(time_series_option, '')
            field = field_registry.get_field_by_name(field).verbose_name
            ts = ugettext('TS')
            time_series_option = time_series_option.split('TS')[1]
            time_series_option = datetime.datetime.strptime(time_series_option, "%Y%m%d").date().strftime('%Y-%m-%d')
            return '%s %s %s' % (field, ts, time_series_option)
        else:
            if '__total__' in message:
                return o_ugettext('total movement')

        parts = message.split('__')
        parts = [o_ugettext(x) for x in parts if x != '']
        ret_value = ''
        parts = reversed(parts) if swap_name_prefix else parts
        for s in parts:
            ret_value += ' %s' % s
        return ret_value

    return capfirst(o_ugettext(message))
