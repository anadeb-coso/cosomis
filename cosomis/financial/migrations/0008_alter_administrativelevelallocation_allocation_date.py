# Generated by Django 4.1.1 on 2023-09-04 11:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('financial', '0007_alter_disbursementrequest_reply_date'),
    ]

    operations = [
        migrations.AlterField(
            model_name='administrativelevelallocation',
            name='allocation_date',
            field=models.DateField(blank=True, null=True, verbose_name='Date'),
        ),
    ]
