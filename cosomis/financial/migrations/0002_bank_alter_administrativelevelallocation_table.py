# Generated by Django 4.1.1 on 2023-09-01 11:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('financial', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Bank',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_date', models.DateTimeField(auto_now_add=True, null=True)),
                ('updated_date', models.DateTimeField(auto_now=True, null=True)),
                ('name', models.CharField(max_length=255, verbose_name='Name')),
                ('abbreviation', models.CharField(max_length=255, verbose_name='Abbreviation')),
                ('description', models.TextField(blank=True, null=True, verbose_name='Description')),
            ],
            options={
                'db_table': 'financial_bank',
            },
        ),
        migrations.AlterModelTable(
            name='administrativelevelallocation',
            table='financial_administrativeLevel_allocation',
        ),
    ]
