from crispy_forms.bootstrap import InlineField, Accordion, Field


class StackedField(InlineField):
    template = "ra/%s/layout/stacked_field.html"


class StackedField2(InlineField):
    template = "ra/reporting/%s/layout/stacked_field2.html"


class EnhancedAccordion(Accordion):
    template = "ra/%s/enhanced-accordion.html"


class UserName(Field):
    template = "ra/%s/username_field.html"
