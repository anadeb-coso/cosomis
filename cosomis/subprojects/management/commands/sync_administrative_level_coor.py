from django.core.management.base import BaseCommand
from django.db.models import Q

from no_sql_client import NoSQLClient
from administrativelevels.models import AdministrativeLevel


class Command(BaseCommand):
    help = 'Description of your command'

    def check_for_valid_facilitator(self, facilitator):
        db = self.nsc.get_db(facilitator).get_query_result({
            "type": "facilitator"
        })
        for document in db:
            try:
                if not document['develop_mode'] and not document["training_mode"]:
                    # print("Facilitator is valid", document)
                    return True
            except:
                return False
        return False

    def handle(self, *args, **options):
        # Your command logic here

        self.nsc = NoSQLClient()
        facilitator_dbs = self.nsc.list_all_databases('facilitator')
        for db_name in facilitator_dbs:
            if self.check_for_valid_facilitator(db_name):
                # Getting only priorities tasks validated
                db = self.nsc.get_db(db_name).get_query_result({
                    "type": "geolocation"
                })

                for document in db:
                    if document.get('administrativelevels'):
                        update_or_create_administrative_level_coor(document['administrativelevels'])
            
        self.stdout.write(self.style.SUCCESS('Successfully executed mycommand!'))


def update_or_create_administrative_level_coor(administrativelevels):

    for adm in administrativelevels:
        adm_id = adm.get('id')
        latitude = adm.get('latitude')
        longitude = adm.get('longitude')

        if not latitude or not longitude:
            continue

        administrative_levels = AdministrativeLevel.objects.filter(id=adm_id).filter(
            Q(latitude__isnull=True) | Q(latitude=0) | Q(latitude=0.0) | Q(longitude__isnull=True) | Q(longitude=0) | Q(longitude=0.0)
        )

        if administrative_levels.exists():
            administrative_level = administrative_levels.first()
            updated = False
            if not administrative_level.latitude:
                administrative_level.latitude = latitude
                updated = True
            if not administrative_level.longitude:
                administrative_level.longitude = longitude
                updated = True

            if updated:
                administrative_level.save()
                print(f"Updated Administrative Level ID: {administrative_level.name} with coordinates ({latitude}, {longitude})")

