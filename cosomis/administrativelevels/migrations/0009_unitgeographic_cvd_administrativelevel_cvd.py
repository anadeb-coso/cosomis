# Generated by Django 4.1.1 on 2023-02-24 14:33

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('administrativelevels', '0008_administrativelevel_no_sql_db_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='UnitGeographic',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('attributed_number_in_canton', models.IntegerField(blank=True, null=True, unique=True)),
                ('unique_code', models.CharField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('canton', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='administrativelevels.administrativelevel')),
            ],
            options={
                'unique_together': {('canton', 'attributed_number_in_canton')},
            },
        ),
        migrations.CreateModel(
            name='CVD',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('attributed_number_in_canton', models.IntegerField(blank=True, null=True)),
                ('unique_code', models.CharField(max_length=100, unique=True)),
                ('president_name_of_the_cvd', models.CharField(blank=True, max_length=100, null=True)),
                ('president_phone_of_the_cvd', models.CharField(blank=True, max_length=15, null=True)),
                ('treasurer_name_of_the_cvd', models.CharField(blank=True, max_length=100, null=True)),
                ('treasurer_phone_of_the_cvd', models.CharField(blank=True, max_length=15, null=True)),
                ('secretary_name_of_the_cvd', models.CharField(blank=True, max_length=100, null=True)),
                ('secretary_phone_of_the_cvd', models.CharField(blank=True, max_length=15, null=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('unit_geographic', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='administrativelevels.unitgeographic')),
            ],
        ),
        migrations.AddField(
            model_name='administrativelevel',
            name='cvd',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='administrativelevels.cvd'),
        ),
    ]