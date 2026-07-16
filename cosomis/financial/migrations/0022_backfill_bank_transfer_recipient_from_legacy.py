# Data migration: before dropping BankTransfer.administrative_level/cvd (next
# migration), point BankTransfer.recipient at the Account already backfilled
# (migration 0018) for that same administrative_level/cvd, on any row where
# recipient is still unset - so no traceability is lost once the legacy
# columns are removed.

from django.db import migrations


def backfill_recipient(apps, schema_editor):
    BankTransfer = apps.get_model('financial', 'BankTransfer')
    Account = apps.get_model('financial', 'Account')

    for transfer in BankTransfer.objects.filter(recipient__isnull=True, administrative_level__isnull=False):
        account = Account.objects.filter(administrative_level_id=transfer.administrative_level_id).first()
        if account:
            transfer.recipient_id = account.pk
            transfer.save(update_fields=['recipient'])

    for transfer in BankTransfer.objects.filter(recipient__isnull=True, cvd__isnull=False):
        account = Account.objects.filter(cvd_id=transfer.cvd_id).first()
        if account:
            transfer.recipient_id = account.pk
            transfer.save(update_fields=['recipient'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('financial', '0021_account_parent'),
    ]

    operations = [
        migrations.RunPython(backfill_recipient, noop_reverse),
    ]
