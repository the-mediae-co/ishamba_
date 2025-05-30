# Generated by Django 4.1.7 on 2023-02-21 20:33

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("agri", "0025_delete_agritipsentsms"),
        ("customers", "0118_alter_customercategory_sorting"),
        ("tips", "0026_alter_tipseriessubscription_customer"),
    ]

    operations = [
        migrations.AddField(
            model_name="tipseries",
            name="commodity",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="tip_series",
                to="agri.commodity",
            ),
        ),
        migrations.AlterField(
            model_name="tipseriessubscription",
            name="start",
            field=models.DateTimeField(help_text="The date to start this subscription"),
        ),
        migrations.CreateModel(
            name="BulkTipSeriesSubscription",
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
                    "start",
                    models.DateTimeField(
                        help_text="The date to start these subscriptions"
                    ),
                ),
                ("categories", models.ManyToManyField(to="customers.customercategory")),
                (
                    "tip_series",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="bulk_subscriptions",
                        to="tips.tipseries",
                        verbose_name="Tip series",
                    ),
                ),
            ],
            options={
                "verbose_name": "Bulk TipSeries Subscription",
                "verbose_name_plural": "Bulk TipSeries Subscriptions",
            },
        ),
    ]
