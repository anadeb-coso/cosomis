# Generated by Django 4.1.1 on 2023-09-04 11:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('financial', '0006_alter_banktransfer_cvd'),
    ]

    operations = [
        migrations.AlterField(
            model_name='disbursementrequest',
            name='reply_date',
            field=models.DateField(blank=True, null=True, verbose_name='Reply date'),
        ),
    ]
