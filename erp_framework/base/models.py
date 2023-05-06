import datetime
import logging

from crequest.middleware import CrequestMiddleware
from django.contrib.auth import get_user_model
from django.db import models
from django.urls import reverse, NoReverseMatch
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

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
        del state["_original_state"]
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
                    result[key] = {"old": value, "new": self.__dict__.get(key, missing)}
            except TypeError:
                result[key] = {"old": value, "new": self.__dict__.get(key, missing)}
        return result


class RAModel(DiffingMixin, models.Model):
    owner = models.ForeignKey(
        User,
        related_name="%(app_label)s_%(class)s_related",
        verbose_name=_("owner"),
        on_delete=models.CASCADE,
    )
    creation_date = models.DateTimeField(_("creation date and time"), default=now)
    lastmod = models.DateTimeField(_("last modification"), db_index=True)
    lastmod_user = models.ForeignKey(
        User,
        related_name="%(app_label)s_%(class)s_lastmod_related",
        verbose_name=_("last modification by"),
        on_delete=models.CASCADE,
    )

    class Meta:
        abstract = True


class ERPMixin:
    @classmethod
    def get_class_name(cls):
        """
        return the class name, usable when a ra model is mimicking (ie:proxying)
        another model.
        This method is used is get_doc_type_* functions,
        This method is made to avoid to repeat registered type to make adjustments
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


class EntityModel(ERPMixin, RAModel):
    """
    The Main base for Ra `static` models
    Example: Client , Expense etc..
    """

    slug = models.SlugField(
        _("Identifier slug"),
        help_text=_("For fast recall"),
        max_length=50,
        unique=True,
        db_index=True,
        blank=True,
    )
    name = models.CharField(_("Name"), max_length=255, unique=True, db_index=True)
    notes = models.TextField(_("Notes"), null=True, blank=True)

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        super(EntityModel, self).__init__(*args, **kwargs)
        # self.reporting_model = None
        if not getattr(self, "pk_name", False):
            self.pk_name = None

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        model_name = self._meta.model_name.lower()
        try:
            url = reverse(
                "%s:%s_%s_view"
                % (app_settings.RA_ADMIN_SITE_NAME, self._meta.app_label, model_name),
                args=(self.pk,),
            )
        except NoReverseMatch:
            url = reverse(
                "%s:%s_%s_change"
                % (
                    app_settings.RA_ADMIN_SITE_NAME,
                    self._meta.app_label,
                    self.get_class_name().lower(),
                ),
                args=(self.pk,),
            )
        return url

    def get_next_slug(self, suggestion=None):
        """
        Get the next slug
        If it's a new instance and the slug is not provided, we try and attempt a serial over the already added slugs
        in relation to the model
        :return:
        """
        from .helpers import get_next_serial

        return get_next_serial(self.__class__)  # repr(time.time()).replace('.', '')

    def save(self, *args, **kwargs):
        if self.pk is None:
            if not self.slug:
                self.slug = self.get_next_slug(self.name)
                # print(self.slug)
            if not self.owner_id:
                try:
                    self.owner = self.lastmod_user
                except:
                    self.owner_id = self.lastmod_user_id
                    logger.info(
                        "lastmod_user_id is used instead of lastmod_user object"
                    )

        self.lastmod = now()

        super(EntityModel, self).save(*args, **kwargs)

    @classmethod
    def _get_doc_type_plus_list(cls):
        """

        Returns List of Identified doctype that a plus effect on the entity
        """
        return ["fb"] + registry.get_model_doc_type_map(cls.get_class_name()).get(
            "plus_list", []
        )

    @classmethod
    def _get_doc_type_minus_list(cls):
        """Returns List of Identified doctype that a minus effect on the entity"""

        return registry.get_model_doc_type_map(cls.get_class_name()).get(
            "minus_list", []
        )

    @classmethod
    def get_doc_type_neuter_list(cls):
        """Returns List of Identified doctype that have a neuttral effect on the entity"""

        return []

    #
    # @classmethod
    # def get_doc_type_full_map(cls):
    #     from .registry import model_doc_type_full_map
    #
    #     doc_types_unfiltered = model_doc_type_full_map.get(cls.get_class_name(), [])
    #     doc_typed_filtered = []
    #     for type in doc_types_unfiltered:
    #         if not type.get('hidden', False):
    #             doc_typed_filtered.append(type)
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
            return "%s_id" % self.__class__.__name__.lower()

    def get_title(self):
        """
        A helper function to get a custom name of the instance if needed
        :return:
        """
        return self.name

    @classmethod
    def get_report_list_url(cls):
        """
        Return the url for the report list for this model
        :return: a string url
        """

        return reverse(
            "%s:report_list" % app_settings.RA_ADMIN_SITE_NAME,
            args=(cls.get_class_name().lower(),),
        )

    @classmethod
    def get_redirect_url_prefix(cls):
        """
        Get the url for the change list of this model
        :return: a string url
        """
        return reverse(
            "%s:%s_%s_changelist"
            % (
                app_settings.RA_ADMIN_SITE_NAME,
                cls._meta.app_label,
                cls.get_class_name().lower(),
            )
        )


# class BasePersonInfo(BaseInfo):
#     address = models.CharField(_('address'), max_length=260, null=True, blank=True)
#     telephone = models.CharField(_('telephone'), max_length=130, null=True, blank=True)
#     email = models.EmailField(_('email'), null=True, blank=True)
#
#     class Meta:
#         abstract = True
#         # swappable = swapper.swappable_setting('ra', 'BasePersonInfo')


class TransactionModel(EntityModel):
    name = None

    slug = models.SlugField(
        _("Slug"), max_length=50, db_index=True, validators=[], blank=True
    )
    date = models.DateTimeField(_("Date"), db_index=True)
    type = models.CharField(max_length=30, db_index=True)
    notes = models.TextField(_("Notes"), null=True, blank=True)
    value = models.DecimalField(_("Value"), max_digits=19, decimal_places=2, default=0)

    owner = models.ForeignKey(
        User,
        related_name="%(app_label)s_%(class)s_related",
        verbose_name=_("Created By"),
        on_delete=models.CASCADE,
    )
    creation_date = models.DateTimeField(_("Creation timestamp"), default=now)
    lastmod = models.DateTimeField(_("Last modification"), db_index=True)
    lastmod_user = models.ForeignKey(
        User,
        related_name="%(app_label)s_%(class)s_lastmod_related",
        verbose_name=_("Last modification by"),
        on_delete=models.CASCADE,
    )

    @classmethod
    def get_doc_type(cls):
        """
        Return the type
        :return:
        """
        return cls.__name__.lower()
        # raise NotImplementedError(
        #     f'Class {cls} dont have a get_doc_type override. Each Transaction should define a *type*')

    def __str__(self):
        return "%s-%s" % (self._meta.verbose_name, self.slug)

    def __repr__(self):
        return "<%s pk:%s slug:%s type:%s>" % (
            self.__class__.__name__,
            self.pk,
            self.slug,
            self.type,
        )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        """
        Custom save, it assign the user  As owner and the last modifed
        it sets the type
        make sure that dlc_date has correct timezone ?!
        :param force_insert:
        :param force_update:
        :param using:
        :param update_fields:
        :return:
        """

        from erp_framework.base.helpers import get_next_serial

        request = CrequestMiddleware.get_request()
        self.type = self.get_doc_type()
        if not self.slug:
            self.slug = get_next_serial(self.__class__)

        # self.slug = slugify(self.slug)
        if not self.pk:
            if not self.lastmod_user_id:
                self.lastmod_user_id = request.user.pk
            if not self.owner_id:
                self.owner_id = request.user.pk
            self.date = self.date if self.date else now()
        self.lastmod = now()

        super(EntityModel, self).save(*args, **kwargs)

    #
    # @classmethod
    # def get_doc_type_verbose_name(cls, type):
    #     """
    #     Return the type verbose name , Must be implemented when needed by children
    #     @param type: the type field value
    #     @return: the description of the type
    #     Example: In: get_doc_type_verbose_name('1')
    #             Out: Purchase
    #     """
    #     # Example :
    #     # if type == '1': return _('purchase')
    #     raise NotImplemented()

    # def get_absolute_url(self):
    #     doc_types = registry.get_doc_type_settings()
    #     if self.type in doc_types:
    #         return '%sslug/%s/' % (doc_types[self.type]['redirect_url_prefix'], self.slug)
    #     else:
    #         return self.type

    @property
    def name(self):
        return self.date.strftime("%Y/%m/%d %H:%M")


class TransactionItemModel(TransactionModel):
    """
    Abstract model to identify a movement with a value
    """

    class Meta:
        abstract = True


class QuantitativeTransactionItemModel(TransactionItemModel):
    quantity = models.DecimalField(
        _("Quantity"), max_digits=19, decimal_places=2, default=0
    )
    price = models.DecimalField(_("Price"), max_digits=19, decimal_places=2, default=0)
    discount = models.DecimalField(
        _("Discount"), max_digits=19, decimal_places=2, default=0
    )

    def save(self, *args, **kwargs):
        self.value = self.quantity * self.price
        if self.discount:
            self.value -= self.value * self.discount / 100
        super(QuantitativeTransactionItemModel, self).save(*args, **kwargs)

    class Meta:
        abstract = True


class BaseReportModel(DiffingMixin, models.Model):
    slug = models.SlugField(
        _("Slug"), max_length=50, db_index=True, validators=[], blank=True
    )
    date = models.DateTimeField(_("Date"), db_index=True)
    type = models.CharField(max_length=30, db_index=True, verbose_name=_("Type"))
    notes = models.TextField(_("Notes"), null=True, blank=True)
    value = models.DecimalField(_("Value"), max_digits=19, decimal_places=2, default=0)

    owner = models.ForeignKey(
        User,
        related_name="%(app_label)s_%(class)s_related",
        verbose_name=_("Created By"),
        on_delete=models.DO_NOTHING,
    )
    creation_date = models.DateTimeField(_("Creation Timestamp"), default=now)
    lastmod = models.DateTimeField(_("Last modified"), db_index=True)
    lastmod_user = models.ForeignKey(
        User,
        related_name="%(app_label)s_%(class)s_lastmod_related",
        verbose_name=_("Last modification by"),
        on_delete=models.DO_NOTHING,
    )

    @classmethod
    def get_doc_type_plus_list(cls):
        """

        Returns List of Identified doctype that a plus effect on the entity
        """
        return []  # ['0','3' , 'client-cash-in','supplier-cash-in']

    @classmethod
    def get_doc_type_minus_list(cls):
        """Returns List of Identified doctype that a minus effect on the entity"""

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
    quantity = models.DecimalField(
        _("quantity"), max_digits=19, decimal_places=2, default=0
    )
    price = models.DecimalField(_("price"), max_digits=19, decimal_places=2, default=0)
    discount = models.DecimalField(
        _("discount"), max_digits=19, decimal_places=2, default=0
    )

    @classmethod
    def get_doc_type_plus_list(cls):
        """

        Returns List of Identified doctype that a plus effect on the entity
        """
        return []  # ['0','3' , 'client-cash-in','supplier-cash-in']

    @classmethod
    def get_doc_type_minus_list(cls):
        """Returns List of Identified doctype that a minus effect on the entity"""

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
        return (
            super(ProxyMovementManager, self)
            .get_queryset()
            .filter(type=self.model.get_doc_type())
        )


class ProxyMovement(object):
    objects = ProxyMovementManager()

    @classmethod
    def get_doc_type(cls):
        """
        Get the doc-type of the row.
        This method is called internally during save to ensure that the record in the
        proxy model always have the right type
        :return: string (type)
        """
        return ""

    def __init__(self, *args, **kwargs):
        super(ProxyMovement, self).__init__(*args, **kwargs)
        self._doc_type = ""

    def save(self, *args, **kwargs):
        self.type = self.__class__.get_doc_type()
        super(ProxyMovement, self).save(*args, **kwargs)

    class Meta:
        proxy = True
