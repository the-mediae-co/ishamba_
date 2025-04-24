from django.db.backends.postgresql.features import DatabaseFeatures

# A somewhat inelegant solution to weird test errors with factory boy created
# test data.
# See: https://stackoverflow.com/a/70312265
DatabaseFeatures.can_defer_constraint_checks = False
