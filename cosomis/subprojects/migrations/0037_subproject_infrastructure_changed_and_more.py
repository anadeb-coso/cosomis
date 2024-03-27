# Generated by Django 4.1.1 on 2024-03-22 15:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subprojects', '0036_alter_subproject_contract_companies_amount_for_efme'),
    ]

    operations = [
        migrations.AddField(
            model_name='subproject',
            name='infrastructure_changed',
            field=models.BooleanField(blank=True, null=True, verbose_name='Infrastructure changed?'),
        ),
        migrations.AddField(
            model_name='subproject',
            name='infrastructure_deleted',
            field=models.BooleanField(blank=True, null=True, verbose_name='Infrastructure deleted?'),
        ),
    ]