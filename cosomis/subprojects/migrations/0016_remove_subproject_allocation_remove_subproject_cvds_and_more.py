# Generated by Django 4.1.1 on 2023-03-07 16:15

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('administrativelevels', '0016_alter_administrativelevel_unique_together'),
        ('subprojects', '0015_subproject_latitude_subproject_longitude_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='subproject',
            name='allocation',
        ),
        migrations.RemoveField(
            model_name='subproject',
            name='cvds',
        ),
        migrations.RemoveField(
            model_name='subproject',
            name='description',
        ),
        migrations.RemoveField(
            model_name='subproject',
            name='short_name',
        ),
        migrations.AddField(
            model_name='subproject',
            name='amount_of_the_care_and_maintenance_fund_expected_to_be_mobilized',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='amount_of_the_contract_for_construction_supervisors',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='amount_of_the_controllers_contract_in_SES',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='amount_of_the_facilitator_contract',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='approval_date_cora',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='canton',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='administrativelevels.administrativelevel'),
        ),
        migrations.AddField(
            model_name='subproject',
            name='care_and_maintenance_amount_on_village_account',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='comments',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='contract_amount_work_companies',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='contract_companies_amount_for_efme',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='contract_number_of_work_companies',
            field=models.CharField(blank=True, max_length=15, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='convention',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='current_level_of_physical_realization_of_the_work',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='current_status_of_the_site',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='cvd',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='administrativelevels.cvd'),
        ),
        migrations.AddField(
            model_name='subproject',
            name='date_of_provisional_acceptance_of_work_contracts',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='date_of_signature_of_contract_for_construction_supervisors',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='date_of_technical_acceptance_of_work_contracts',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='date_signature_contract_controllers_in_SES',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='date_signature_contract_efme',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='date_signature_contract_facilitator',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='date_signature_contract_work_companies',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='depth_of_drilling',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='drilling_flow_rate',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='estimated_cost',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='existence_of_maintenance_and_upkeep_plan_developed_by_community',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='subproject',
            name='expected_duration_of_the_work',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='expected_end_date_of_the_contract',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='facilitator_name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='full_title_of_approved_subproject',
            field=models.CharField(default='', max_length=255),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='subproject',
            name='intervention_unit',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='launch_date_of_the_construction_site_in_the_village',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='length_of_the_track',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='level_of_achievement_donation_certificate',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='link_to_subproject',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='subprojects.subproject'),
        ),
        migrations.AddField(
            model_name='subproject',
            name='location_subproject_realized',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='location_subproject_realized', to='administrativelevels.administrativelevel'),
        ),
        migrations.AddField(
            model_name='subproject',
            name='lot',
            field=models.CharField(blank=True, max_length=2, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='name_of_company_awarded_efme',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='name_of_the_awarded_company_works_companies',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='number',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='official_handover_date_of_the_microproject_to_the_community',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='official_handover_date_of_the_microproject_to_the_sector',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='provisional_acceptance_date_for_efme_contracts',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='subproject_sector',
            field=models.CharField(default='', max_length=100),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='subproject',
            name='technical_acceptance_date_for_efme_contracts',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='total_contract_amount_paid',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='type_of_subproject',
            field=models.CharField(default='', max_length=100),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='subproject',
            name='wave',
            field=models.CharField(blank=True, max_length=2, null=True),
        ),
        migrations.AddField(
            model_name='subproject',
            name='works_type',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='subproject',
            name='ranking',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='subproject',
            name='target_female_beneficiaries',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='subproject',
            name='target_male_beneficiaries',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='subproject',
            name='target_youth_beneficiaries',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='vulnerablegroup',
            name='created_date',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AlterField(
            model_name='vulnerablegroup',
            name='updated_date',
            field=models.DateTimeField(auto_now=True, null=True),
        ),
        migrations.CreateModel(
            name='SubprojectImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_date', models.DateTimeField(auto_now_add=True, null=True)),
                ('updated_date', models.DateTimeField(auto_now=True, null=True)),
                ('name', models.CharField(max_length=255)),
                ('url', models.CharField(max_length=255)),
                ('order', models.IntegerField(default=0)),
                ('principal', models.BooleanField(default=False)),
                ('date_taken', models.DateField()),
                ('subproject', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='subprojects.subproject')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]