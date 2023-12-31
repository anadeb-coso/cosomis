# Generated by Django 4.1.1 on 2023-08-09 12:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subprojects', '0026_remove_subproject_joint_project_number_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='subproject',
            name='subproject_type_designation',
            field=models.CharField(choices=[('Subproject', 'Subproject'), ('Infrastructure', 'Infrastructure')], default='Subproject', max_length=100, verbose_name='Subproject type designation (Subproject or Infrastructure)'),
        ),
    ]
