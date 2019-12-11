import logging

from django.db.models import Sum, Q

from ra.reporting.helpers import get_calculation_annotation

logger = logging.getLogger('ra.reporting')


class BalanceAPI(object):
    date_field = 'doc_date'
    plus_minus_modifier_field = 'doc_type'
    calculation_field = 'value'
    calculation_method = Sum
    report_model = None
    Q_plus_modifier = Q()
    Q_minus_modifier = Q()
    base_model_id = None
    _debit_and_credit = True

    def __init__(self, report_model, base_model_id, doc_type_plus_list, doc_type_minus_list,
                 calculation_field='value', calculation_method=Sum, *args, **kwargs):
        super(BalanceAPI, self).__init__()
        # if Q_plus_modifier:

        self.report_model = report_model if report_model else self.report_model
        self.calculation_field = calculation_field
        self.calculation_method = calculation_method
        self.report_model = report_model if report_model else self.report_model
        self.base_model_id = base_model_id

        for x in doc_type_plus_list:
            self.Q_plus_modifier = self.Q_plus_modifier | Q(doc_type=x)
        for x in doc_type_minus_list:
            self.Q_minus_modifier = self.Q_minus_modifier | Q(doc_type=x)

            # self.Q_plus_modifier = Q_plus_modifier if Q_plus_modifier  else []
            # self.Q_minus_modifier = Q_minus_modifier if Q_minus_modifier  else []

    def _get_calculation_annotation(self):

        return get_calculation_annotation(self.calculation_field, self.calculation_method)

    def get_last_transaction(self, on_date=None, object_id=None, filters=None, exclude=None):
        filter_dict = {}
        if on_date:
            filter_dict[self.date_field + '__lte'] = on_date
        if object_id:
            filter_dict[self.base_model_id] = object_id
        if filters is not None:
            filter_dict.update(filters)

        queryset = self.get_queryset(plus=True) | self.get_queryset(minus=True)
        sqs = queryset.filter(**filter_dict).filter(~Q(doc_type='fb'))
        x = sqs.order_by(self.date_field).last()
        return x

    def get_balance(self, on_date, object_id=None, filters=None, exclude=None):
        '''
        Get object Balance
        @param on_date:
        @param object_id:
        @param filters:
        @param exclude:
        @return:
        '''

        debit = 0
        credit = 0
        # todo optional enforce a begin date year

        filter_dict = {self.date_field + '__lte': on_date}
        if object_id:
            filter_dict[self.base_model_id] = object_id
        if filters is not None:
            filter_dict.update(filters)

        queryset = self.get_queryset(plus=True)
        sqs = queryset.filter(**filter_dict)
        if exclude is not None:
            sqs.exclude(**exclude)
        result = sqs.aggregate(self.calculation_method(self.calculation_field))
        debit = result[self._get_calculation_annotation()]
        if debit is None: debit = 0
        # logger.debug('Debit %s for %s     %s     [Sum of %d records]' % (self.report_field, object_id, debit, len(sqs)))

        if self._debit_and_credit:
            queryset = self.get_queryset(minus=True)
            sqs = queryset.filter(**filter_dict)
            if exclude is not None:
                sqs.exclude(**exclude)
            result = sqs.aggregate(self.calculation_method(self.calculation_field))
            credit = result[self._get_calculation_annotation()]
            if credit is None: credit = 0
            # logger.debug( 'Credit %s for %s     %s     [Sum of %d records]' % (self.report_field, object_id, credit, len(sqs)))
            # logger.debug(sqs.query)
            # logger.debug(sqs.query)
        # logger.info('Balance = %d' % (debit - credit))

        return debit - credit
        # return sqs

    def get_queryset(self, plus=False, minus=False, w_extra_filters=None):

        queryset = self.report_model.objects

        if plus is True:
            # logger.debug('plus')
            if self.Q_plus_modifier is not None: queryset = queryset.filter(self.Q_plus_modifier)
        if minus is True:
            # logger.debug('minus')
            if self.Q_minus_modifier is not None: queryset = queryset.filter(self.Q_minus_modifier)

            # if w_extra_filters is True:
            # filter_dict = self.get_extra_filters()
            filter_dict = {}
            if w_extra_filters:
                filter_dict.update(w_extra_filters)
            queryset = queryset.filter(**filter_dict)

        return queryset
