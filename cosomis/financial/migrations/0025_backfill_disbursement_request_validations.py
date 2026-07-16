# Data migration: for every DisbursementRequest that already has an
# amount_validated set, log that as the first (round 1) entry in the new
# DisbursementRequestValidation history table - so existing data isn't
# silently missing from the new history view.

from django.db import migrations


def backfill_validations(apps, schema_editor):
    DisbursementRequest = apps.get_model('financial', 'DisbursementRequest')
    DisbursementRequestValidation = apps.get_model('financial', 'DisbursementRequestValidation')

    for request in DisbursementRequest.objects.filter(amount_validated__isnull=False):
        DisbursementRequestValidation.objects.create(
            disbursement_request=request,
            validation_date=request.validation_date or request.requested_date,
            amount_validated=request.amount_validated,
            status_after=request.status,
            comment=request.comment_linked_to_reply,
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('financial', '0024_disbursementrequestvalidation'),
    ]

    operations = [
        migrations.RunPython(backfill_validations, noop_reverse),
    ]
