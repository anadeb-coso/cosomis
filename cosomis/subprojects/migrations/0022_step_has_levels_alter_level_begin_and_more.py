# Generated by Django 4.1.1 on 2023-08-02 15:15

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('subprojects', '0021_step_subprojectstep_level'),
    ]

    operations = [
        migrations.AddField(
            model_name='step',
            name='has_levels',
            field=models.BooleanField(default=False, verbose_name='Has levels'),
        ),
        migrations.AlterField(
            model_name='level',
            name='begin',
            field=models.DateField(verbose_name='Begin'),
        ),
        migrations.AlterField(
            model_name='level',
            name='description',
            field=models.TextField(blank=True, null=True, verbose_name='Description'),
        ),
        migrations.AlterField(
            model_name='level',
            name='end',
            field=models.DateField(blank=True, null=True, verbose_name='End'),
        ),
        migrations.AlterField(
            model_name='level',
            name='percent',
            field=models.FloatField(verbose_name='Percent'),
        ),
        migrations.AlterField(
            model_name='level',
            name='ranking',
            field=models.IntegerField(default=0, verbose_name='Ranking'),
        ),
        migrations.AlterField(
            model_name='level',
            name='subproject_step',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='subprojects.subprojectstep', verbose_name='Step'),
        ),
        migrations.AlterField(
            model_name='level',
            name='wording',
            field=models.CharField(max_length=200, verbose_name='Wording'),
        ),
        migrations.AlterField(
            model_name='step',
            name='description',
            field=models.TextField(blank=True, null=True, verbose_name='Description'),
        ),
        migrations.AlterField(
            model_name='step',
            name='percent',
            field=models.FloatField(blank=True, null=True, verbose_name='Percent'),
        ),
        migrations.AlterField(
            model_name='step',
            name='ranking',
            field=models.IntegerField(default=0, verbose_name='Ranking'),
        ),
        migrations.AlterField(
            model_name='step',
            name='wording',
            field=models.CharField(max_length=200, verbose_name='Wording'),
        ),
        migrations.AlterField(
            model_name='subprojectstep',
            name='begin',
            field=models.DateField(verbose_name='Begin'),
        ),
        migrations.AlterField(
            model_name='subprojectstep',
            name='description',
            field=models.TextField(blank=True, null=True, verbose_name='Description'),
        ),
        migrations.AlterField(
            model_name='subprojectstep',
            name='end',
            field=models.DateField(blank=True, null=True, verbose_name='End'),
        ),
        migrations.AlterField(
            model_name='subprojectstep',
            name='percent',
            field=models.FloatField(blank=True, null=True, verbose_name='Percent'),
        ),
        migrations.AlterField(
            model_name='subprojectstep',
            name='ranking',
            field=models.IntegerField(default=0, verbose_name='Ranking'),
        ),
        migrations.AlterField(
            model_name='subprojectstep',
            name='step',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='subprojects.step', verbose_name='Step'),
        ),
        migrations.AlterField(
            model_name='subprojectstep',
            name='subproject',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='subprojects.subproject', verbose_name='Subproject'),
        ),
        migrations.AlterField(
            model_name='subprojectstep',
            name='wording',
            field=models.CharField(max_length=200, verbose_name='Wording'),
        ),
        migrations.AlterUniqueTogether(
            name='step',
            unique_together={('ranking',)},
        ),
    ]