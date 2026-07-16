# Data migration: legacy BankTransfer rows never had a sender Account set (only
# a Project FK) - so "sender" displayed as blank everywhere. Create one
# PROJECT-type Account per distinct Project referenced by such rows (reusing
# an existing one with the same name if present) and backfill `sender` so the
# sender is always a proper Account, like the recipient already is.

from django.db import migrations


def backfill_sender(apps, schema_editor):
    BankTransfer = apps.get_model('financial', 'BankTransfer')
    Account = apps.get_model('financial', 'Account')

    project_ids = BankTransfer.objects.filter(
        sender__isnull=True, project__isnull=False
    ).values_list('project_id', flat=True).distinct()

    for project_id in project_ids:
        transfer = BankTransfer.objects.filter(project_id=project_id).select_related('project').first()
        project_name = transfer.project.name
        account, _created = Account.objects.get_or_create(
            name=project_name,
            account_type='PROJECT',
            defaults={'account_category': 'MAIN_ACCOUNT'},
        )
        BankTransfer.objects.filter(sender__isnull=True, project_id=project_id).update(sender_id=account.pk)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('financial', '0025_backfill_disbursement_request_validations'),
    ]

    operations = [
        migrations.RunPython(backfill_sender, noop_reverse),
    ]
