# Generated by Django 4.1.1 on 2023-09-08 18:35

import cosomis.customers_fields
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('subprojects', '0031_alter_level_percent_alter_step_percent_and_more'),
        ('financial', '0011_administrativelevelallocation_amount_in_dollars_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='administrativelevelallocation',
            name='allocation_date_after_signature_of_contracts',
            field=models.DateField(blank=True, null=True, verbose_name="Allocation Date after signature of contract(s) (This is only necessary if it's a CVD)"),
        ),
        migrations.AddField(
            model_name='administrativelevelallocation',
            name='amount_after_signature_of_contracts',
            field=cosomis.customers_fields.CustomerFloatRangeField(blank=True, null=True, verbose_name="Amount allocated after signature of contract(s) (This is only necessary if it's a CVD)"),
        ),
        migrations.AddField(
            model_name='administrativelevelallocation',
            name='amount_in_dollars_after_signature_of_contracts',
            field=cosomis.customers_fields.CustomerFloatRangeField(blank=True, null=True, verbose_name="Amount allocated in dollars after signature of contract(s) (This is only necessary if it's a CVD)"),
        ),
        migrations.AlterField(
            model_name='administrativelevelallocation',
            name='allocation_date',
            field=models.DateField(blank=True, null=True, verbose_name='Allocation Date'),
        ),
        migrations.AlterField(
            model_name='administrativelevelallocation',
            name='component',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='subprojects.component', verbose_name='Component (Subcomponent)'),
        ),
    ]