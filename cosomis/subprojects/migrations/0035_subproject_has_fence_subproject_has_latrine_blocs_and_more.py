# Generated by Django 4.1.1 on 2024-03-15 16:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subprojects', '0034_alter_subproject_contract_number_of_work_companies_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='subproject',
            name='has_fence',
            field=models.BooleanField(blank=True, null=True, verbose_name='Has a fence?'),
        ),
        migrations.AddField(
            model_name='subproject',
            name='has_latrine_blocs',
            field=models.BooleanField(blank=True, null=True, verbose_name='Latrine blocks?'),
        ),
        migrations.AddField(
            model_name='subproject',
            name='number_of_classrooms',
            field=models.IntegerField(blank=True, null=True, verbose_name='Number of classrooms'),
        ),
        migrations.AddField(
            model_name='subproject',
            name='number_of_latrine_blocks',
            field=models.IntegerField(blank=True, null=True, verbose_name='Number of latrine blocks'),
        ),
    ]