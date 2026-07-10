from django.core.management.base import BaseCommand
from django.db.models import Q
from django.conf import settings

from subprojects.models import Subproject


class Command(BaseCommand):
    help = 'Description of your command'


    def handle(self, *args, **options):
        # Your command logic here

        if settings.DEBUG:
            subprojects = Subproject.objects.filter(
                Q(latitude__isnull=True) | Q(latitude=0) | Q(latitude=0.0) | Q(longitude__isnull=True) | Q(longitude=0) | Q(longitude=0.0)
            )
            
            for subproject in subprojects:
                subproject.latitude = subproject.get_latitude
                subproject.longitude = subproject.get_longitude

                subproject.save()
            

            self.stdout.write(self.style.SUCCESS('Successfully executed mycommand!'))
            
        else:
            self.stdout.write(self.style.ERROR("Can't execute this command!"))
