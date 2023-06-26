# Generated by Django 4.1.1 on 2023-06-26 10:49

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('subprojects', '0018_alter_subproject_full_title_of_approved_subproject'),
    ]

    operations = [
        migrations.CreateModel(
            name='Financier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_date', models.DateTimeField(auto_now_add=True, null=True)),
                ('updated_date', models.DateTimeField(auto_now=True, null=True)),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField()),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Project',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_date', models.DateTimeField(auto_now_add=True, null=True)),
                ('updated_date', models.DateTimeField(auto_now=True, null=True)),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField()),
                ('financier', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='subprojects.financier')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='subproject',
            name='financier',
            field=models.ManyToManyField(blank=True, default=[], to='subprojects.financier'),
        ),
        migrations.AddField(
            model_name='subproject',
            name='project',
            field=models.ManyToManyField(blank=True, default=[], to='subprojects.project'),
        ),
    ]
