# Generated by Django 3.2.12 on 2022-03-07 12:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0053_populate_cost_and_gateway_details'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dailyoutgoingsmssummary',
            name='message_type',
            field=models.CharField(choices=[('?', 'Unknown'), ('bulk', 'Bulk'), ('one', 'Individual'), ('task', 'Task_Response'), ('auto', 'Template_Response'), ('new', 'New_Customer_Response'), ('tip', 'Agri_Tip'), ('wxke', 'Weather_Kenmet'), ('wxpv', 'Weather_Plantvillage'), ('mkt', 'Market_Price'), ('sub', 'Subscription_Notification'), ('vchr', 'Voucher'), ('wxmkt', 'Weather_And_Market'), ('query', 'Data_Request')], default='?', max_length=8),
        ),
        migrations.AlterField(
            model_name='outgoingsms',
            name='message_type',
            field=models.CharField(choices=[('?', 'Unknown'), ('bulk', 'Bulk'), ('one', 'Individual'), ('task', 'Task_Response'), ('auto', 'Template_Response'), ('new', 'New_Customer_Response'), ('tip', 'Agri_Tip'), ('wxke', 'Weather_Kenmet'), ('wxpv', 'Weather_Plantvillage'), ('mkt', 'Market_Price'), ('sub', 'Subscription_Notification'), ('vchr', 'Voucher'), ('wxmkt', 'Weather_And_Market'), ('query', 'Data_Request')], default='?', max_length=8),
        ),
    ]
