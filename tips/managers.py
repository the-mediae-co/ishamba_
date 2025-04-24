from django.db import models


class TipSeriesSubscriptionManager(models.Manager):

    def get_queryset(self, *args, **kwargs):
        return super().get_queryset(*args, **kwargs).exclude(ended=True)
