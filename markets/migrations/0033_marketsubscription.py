# Generated by Django 4.1.6 on 2023-02-14 13:39

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0116_nps_response"),
        ("markets", "0032_delete_marketpricesentsms"),
    ]

    operations = [
        migrations.CreateModel(
            name="MarketSubscription",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("creator_id", models.IntegerField(blank=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                ("last_editor_id", models.IntegerField(blank=True, null=True)),
                (
                    "backup",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="new_backup_subscriptions",
                        to="markets.market",
                    ),
                ),
                (
                    "customer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="new_markets",
                        to="customers.customer",
                    ),
                ),
                (
                    "market",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="new_primary_subscriptions",
                        to="markets.market",
                    ),
                ),
            ],
            options={
                "verbose_name": "Market subscription",
                "unique_together": {("customer", "market")},
            },
        ),
    ]
