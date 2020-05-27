import datetime
import logging

from crequest.middleware import CrequestMiddleware
from django.contrib.auth import get_user_model
from django.db import models
from django.urls import reverse, NoReverseMatch
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _

from . import app_settings, registry

logger = logging.getLogger(__name__)
User = get_user_model()


class DiffingMixin(object):
    def __init__(self, *args, **kwargs):
        super(DiffingMixin, self).__init__(*args, **kwargs)
        self._original_state = dict(self.__dict__)
        self.pre_current_state = None

    def save(self, *args, **kwargs):
        state = dict(self.__dict__)
        del state['_original_state']
        super(DiffingMixin, self).save(*args, **kwargs)
        self.pre_current_state = self._original_state
        self._original_state = state

    def is_dirty(self):
        missing = object()
        for key, value in self._original_state.items():
            try:
                if value != self.__dict__.get(key, missing):
                    return True
            except TypeError as e:
                o = self.__dict__.get(key, missing)
                if type(value) == datetime.datetime and type(o) == datetime.datetime:
                    # Make both unaware
                    o = o.replace(tzinfo=None)
                    value = value.replace(tzinfo=None)
                    if value != o:
                        return True

                else:
                    raise e
        return False

    def changed_columns(self):
        missing = object()
        result = {}
        for key, value in self._original_state.items():
            try:
                if value != self.__dict__.get(key, missing):
                    result[key] = {'old': value, 'new': self.__dict__.get(key, missing)}
            except TypeError:
                result[key] = {'old': value, 'new': self.__dict__.get(key, missing)}
        return result


class RAModel(DiffingMixin, models.Model):
    owner = models.ForeignKey(User, related_name='%(app_label)s_%(class)s_related', verbose_name=_('owner'),
                              on_delete=models.CASCADE)
    creation_date = models.DateTimeField(_('creation date and time'), default=now)
    lastmod = models.DateTimeField(_('last modification'), db_index=True)
    lastmod_user = models.ForeignKey(User, related_name='%(app_label)s_%(class)s_lastmod_related',
                                     verbose_name=_('last modification by'), on_delete=models.CASCADE)

    class Meta:
        abstract = True


class RaModelMixin(object):
    """
    This is a sample interface for integrating with teh framework
    """


class EntityModel(RAModel):
    """
    The Main base for Ra `static` models
    Example: Client , Expense etc..
    """
    slug = models.SlugField(_('refer code'), help_text=_('For fast recall'), max_length=50,
                            unique=True, db_index=True, blank=True)
    title = models.CharField(_('name'), max_length=255, unique=True, db_index=True)
    notes = models.TextField(_('notes'), null=True, blank=True)

    # fb = models.DecimalField(_('beginning balance'), help_text=_('Opening Balance or initial balance '), max_digits=19,
    #                          decimal_places=2, default=0)

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        super(EntityModel, self).__init__(*args, **kwargs)
        # self.reporting_model = None
        if not getattr(self, 'pk_name', False):
            self.pk_name = None

    def __str__(self):
        return self.title

    @classmethod
    def get_class_name(cls):
        """
        return the class name, usable when a ra model is mimicking (ie:proxying)
        another model.
        This method is used is get_doc_type_* functions,
        This method is made to avoid to repeat registered doc_type to make adjustments
        """
        return cls.__name__

    @classmethod
    def get_model_name(cls):
        """
        A convenience method to get the base model name, needed in templates
        :return:
        """

        return cls._meta.model_name.lower()

    @classmethod
    def get_verbose_name_plural(cls):
        """
        A convenience method to get the base model verbose name, needed in templates
        :return:
        """
        return cls._meta.verbose_name_plural

    def get_absolute_url(self):
        model_name = self._meta.model_name.lower()
        try:
            url = reverse('%s:%s_%s_view' % (app_settings.RA_ADMIN_SITE_NAME, self._meta.app_label, model_name)
                          , args=(self.pk,))
        except NoReverseMatch:
            url = reverse(
                '%s:%s_%s_change' % (
                    app_settings.RA_ADMIN_SITE_NAME, self._meta.app_label, self.get_class_name().lower())
                , args=(self.pk,))
        return url

    @property
    def name(self):
        return self.title

    def get_next_slug(self):
        """
        Get the next slug
        If it's a new instance and the slug is not provided, we try and attempt a serial over the already added slugs
        in relation to the model
        :return:
        """
        from .helpers import get_next_serial
        return get_next_serial(self.__class__)  # repr(time.time()).replace('.', '')

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        if self.pk is None:
            if not self.slug:
                self.slug = self.get_next_slug()
            if not self.owner_id:
                try:
                    self.owner = self.lastmod_user
                except:
                    self.owner_id = self.lastmod_user_id
                    logger.info('lastmod_user_id is used instead of lastmod_user object')

        self.lastmod = now()

        super(EntityModel, self).save(force_insert, force_update, using, update_fields)

    @classmethod
    def _get_doc_type_plus_list(cls):
        '''

        Returns List of Identified doctype that a plus effect on the entity
        '''
        return ['fb'] + registry.get_model_doc_type_map(cls.get_class_name()).get('plus_list', [])

    @classmethod
    def _get_doc_type_minus_list(cls):
        """ Returns List of Identified doctype that a minus effect on the entity"""

        return registry.get_model_doc_type_map(cls.get_class_name()).get('minus_list', [])

    @classmethod
    def get_doc_type_neuter_list(cls):
        """ Returns List of Identified doctype that have a neuttral effect on the entity"""

        return []

    #
    # @classmethod
    # def get_doc_type_full_map(cls):
    #     from .registry import model_doc_type_full_map
    #
    #     doc_types_unfiltered = model_doc_type_full_map.get(cls.get_class_name(), [])
    #     doc_typed_filtered = []
    #     for doc_type in doc_types_unfiltered:
    #         if not doc_type.get('hidden', False):
    #             doc_typed_filtered.append(doc_type)
    #
    #     return doc_typed_filtered

    # @classmethod
    # def get_doc_types(cls):
    #     """
    #     Return a list of the doc_types supported by the current model , Must implemented when needed by children
    #     @return:
    #     """
    #     return cls._get_doc_type_plus_list() + cls._get_doc_type_minus_list() + cls.get_doc_type_neuter_list()

    def get_pk_name(self):
        """
        This is used to get the full name of the primary key,
        a bit hackish but is important for reports.
        :return:
        """
        if self.pk_name:
            return self.pk_name
        else:
            # return self._meta.pk.column #not now
            return '%s_id' % self.__class__.__name__.lower()

    def get_title(self):
        """
        A helper function to get a custom title of the instance if needed
        :return:
        """
        return self.title

    @classmethod
    def get_report_list_url(cls):
        """
        Return the url for the report list for this model
        :return: a string url
        """

        return reverse('%s:report_list' % app_settings.RA_ADMIN_SITE_NAME, args=(cls.get_class_name().lower(),))

    @classmethod
    def get_redirect_url_prefix(cls):
        """
        Get the url for the change list of this model
        :return: a string url
        """
        return reverse('%s:%s_%s_changelist' % (
            app_settings.RA_ADMIN_SITE_NAME, cls._meta.app_label, cls.get_class_name().lower()))


# class BasePersonInfo(BaseInfo):
#     address = models.CharField(_('address'), max_length=260, null=True, blank=True)
#     telephone = models.CharField(_('telephone'), max_length=130, null=True, blank=True)
#     email = models.EmailField(_('email'), null=True, blank=True)
#
#     class Meta:
#         abstract = True
#         # swappable = swapper.swappable_setting('ra', 'BasePersonInfo')


class TransactionModel(EntityModel):
    title = None

    slug = models.SlugField(_('refer code'), max_length=50, db_index=True, validators=[], blank=True)
    doc_date = models.DateTimeField(_('date'), db_index=True)
    doc_type = models.CharField(max_length=30, db_index=True)
    notes = models.TextField(_('notes'), null=True, blank=True)
    value = models.DecimalField(_('value'), max_digits=19, decimal_places=2, default=0)

    owner = models.ForeignKey(User, related_name='%(app_label)s_%(class)s_related', verbose_name=_('owner'),
                              on_delete=models.CASCADE)
    creation_date = models.DateTimeField(_('creation date and time'), default=now)
    lastmod = models.DateTimeField(_('last modification'), db_index=True)
    lastmod_user = models.ForeignKey(User, related_name='%(app_label)s_%(class)s_lastmod_related',
                                     verbose_name=_('last modification by'), on_delete=models.CASCADE)

    @classmethod
    def get_doc_type(cls):
        """
        Return the doc_type
        :return:
        """
        raise NotImplementedError(
            f'Class {cls} dont have a get_doc_type override. Each Transaction should define a *doc_type*')

    def __str__(self):
        return '%s-%s' % (self._meta.verbose_name, self.slug)

    def __repr__(self):
        return '<%s pk:%s slug:%s doc_type:%s>' % (self.__class__.__name__, self.pk, self.slug, self.doc_type)

    class Meta:
        abstract = True

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        """
        Custom save, it assign the user  As owner and the last modifed
        it sets the doc_type
        make sure that dlc_date has correct timezone ?!
        :param force_insert:
        :param force_update:
        :param using:
        :param update_fields:
        :return:
        """

        from ra.base.helpers import get_next_serial
        request = CrequestMiddleware.get_request()
        self.doc_type = self.get_doc_type()
        if not self.slug:
            self.slug = get_next_serial(self.__class__)

        # self.slug = slugify(self.slug)
        if not self.pk:
            if not self.lastmod_user_id:
                self.lastmod_user_id = request.user.pk
            if not self.owner_id:
                self.owner_id = self.lastmod_user_id
        self.lastmod = now()
        # if self.doc_date:
        #     if self.doc_date.tzinfo is None:
        #         self.doc_date = pytz.utc.localize(self.doc_date)

        super(EntityModel, self).save(force_insert, force_update, using, update_fields)

    #
    # @classmethod
    # def get_doc_type_verbose_name(cls, doc_type):
    #     """
    #     Return the doc_type verbose name , Must be implemented when needed by children
    #     @param doc_type: the doc_type field value
    #     @return: the description of the doc_type
    #     Example: In: get_doc_type_verbose_name('1')
    #             Out: Purchase
    #     """
    #     # Example :
    #     # if doc_type == '1': return _('purchase')
    #     raise NotImplemented()

    def get_absolute_url(self):
        doc_types = registry.get_doc_type_settings()
        if self.doc_type in doc_types:
            return '%sslug/%s/' % (doc_types[self.doc_type]['redirect_url_prefix'], self.slug)
        else:
            return self.doc_type

    @property
    def title(self):
        return self.doc_date.strftime('%Y/%m/%d %H:%M')


class TransactionItemModel(TransactionModel):
    """
    Abstract model to identify a movement with a value
    """

    class Meta:
        abstract = True


class QuantitativeTransactionItemModel(TransactionItemModel):
    quantity = models.DecimalField(_('quantity'), max_digits=19, decimal_places=2, default=0)
    price = models.DecimalField(_('price'), max_digits=19, decimal_places=2, default=0)
    discount = models.DecimalField(_('discount'), max_digits=19, decimal_places=2, default=0)

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        self.value = self.quantity * self.price
        if self.discount:
            self.value -= self.value * self.discount / 100
        super(QuantitativeTransactionItemModel, self).save(force_insert, force_update, using, update_fields)

    class Meta:
        abstract = True


class BaseReportModel(DiffingMixin, models.Model):
    slug = models.SlugField(_('refer code'), max_length=50, db_index=True, validators=[], blank=True)
    doc_date = models.DateTimeField(_('date'), db_index=True)
    doc_type = models.CharField(max_length=30, db_index=True)
    notes = models.TextField(_('notes'), null=True, blank=True)
    value = models.DecimalField(_('value'), max_digits=19, decimal_places=2, default=0)

    owner = models.ForeignKey(User, related_name='%(app_label)s_%(class)s_related', verbose_name=_('owner'),
                              on_delete=models.DO_NOTHING)
    creation_date = models.DateTimeField(_('creation date and time'), default=now)
    lastmod = models.DateTimeField(_('last modification'), db_index=True)
    lastmod_user = models.ForeignKey(User, related_name='%(app_label)s_%(class)s_lastmod_related',
                                     verbose_name=_('last modification by'), on_delete=models.DO_NOTHING)

    @classmethod
    def get_doc_type_plus_list(cls):
        '''

        Returns List of Identified doctype that a plus effect on the entity
        '''
        return []  # ['0','3' , 'client-cash-in','supplier-cash-in']

    @classmethod
    def get_doc_type_minus_list(cls):
        ''' Returns List of Identified doctype that a minus effect on the entity'''

        return []  # ['1', '2', 'client-cash-out', 'supplier-cash-out']

    # @classmethod
    # def get_doc_types(cls):
    #     """
    #     Return a list of the doc_types supported by the current model , Must implemented when needed by children
    #     @return:
    #     """
    #     return cls.get_doc_type_plus_list() + cls.get_doc_type_minus_list()

    class Meta:
        abstract = True


class QuanValueReport(BaseReportModel):
    quantity = models.DecimalField(_('quantity'), max_digits=19, decimal_places=2, default=0)
    price = models.DecimalField(_('price'), max_digits=19, decimal_places=2, default=0)
    discount = models.DecimalField(_('discount'), max_digits=19, decimal_places=2, default=0)

    @classmethod
    def get_doc_type_plus_list(cls):
        '''

        Returns List of Identified doctype that a plus effect on the entity
        '''
        return []  # ['0','3' , 'client-cash-in','supplier-cash-in']

    @classmethod
    def get_doc_type_minus_list(cls):
        ''' Returns List of Identified doctype that a minus effect on the entity'''

        return []  # ['1', '2', 'client-cash-out', 'supplier-cash-out']

    # @classmethod
    # def get_doc_types(cls):
    #     """
    #     Return a list of the doc_types supported by the current model , Must implemented when needed by children
    #     @return:
    #     """
    #     return cls.get_doc_type_plus_list() + cls.get_doc_type_minus_list()

    class Meta:
        abstract = True


class ProxyMovementManager(models.Manager):
    def get_queryset(self):
        return super(ProxyMovementManager, self).get_queryset().filter(doc_type=self.model.get_doc_type())


class ProxyMovement(object):
    objects = ProxyMovementManager()

    @classmethod
    def get_doc_type(cls):
        """
        Get the doc-type of the row.
        This method is called internally during save to ensure that the record in the
        proxy model always have the right doc_type
        :return: string (doc_type)
        """
        return ''

    def __init__(self, *args, **kwargs):
        super(ProxyMovement, self).__init__(*args, **kwargs)
        self._doc_type = ''

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        self.doc_type = self.__class__.get_doc_type()
        super(ProxyMovement, self).save(force_insert, force_update, using, update_fields)

    class Meta:
        proxy = True
