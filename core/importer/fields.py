from import_export.fields import Field


class PhonesField(Field):
    phones = None

    def get_value(self, customer):
        """
        Returns the value of the CustomerPhone object's phone number.
        """
        return self.phones

    def save(self, customer, data, is_m2m=False, **kwargs):
        """
        Override the default behavior. This method name is misleading.
        The intention is not to save the record, but to record the value
        in the object so that when it is later saved, this value will be included.
        By default, if readonly is set, the value is ignored.
        We ignore the readonly attribute on the Field and always
        set to the value returned by :meth:`~import_export.fields.Field.clean`.
        """
        cleaned = self.clean(data, **kwargs)
        self.phones = cleaned
