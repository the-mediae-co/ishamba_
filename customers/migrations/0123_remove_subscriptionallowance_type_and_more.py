# Generated by Django 4.1.9 on 2023-10-16 09:33

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0122_auto_20230926_2209'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name='subscriptionallowance',
                    name='type',
                ),
            ],
            database_operations=[],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(
                    name='Subscription',
                ),
            ],
            database_operations=[
                migrations.AlterModelTable(
                    name='Subscription',
                    table='subscriptions_subscription',
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(
                    name='SubscriptionAllowance',
                ),
            ],
            database_operations=[
                migrations.AlterModelTable(
                    name='SubscriptionAllowance',
                    table='subscriptions_subscriptionallowance',
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(
                    name='SubscriptionType',
                ),
            ],
            database_operations=[
                migrations.AlterModelTable(
                    name='SubscriptionType',
                    table='subscriptions_subscriptiontype',
                ),
            ],
        ),
    ]
