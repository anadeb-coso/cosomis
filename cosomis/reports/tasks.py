from celery import shared_task

from reports.sending import send_due_reports


@shared_task
def send_periodic_reports():
    return send_due_reports()
