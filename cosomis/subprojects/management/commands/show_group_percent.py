from django.core.management.base import BaseCommand, CommandError
import time
from django.db.models import Q

from subprojects.models import Subproject, Project


class Command(BaseCommand):

    def handle(self, *args, **options):
        # Your command logic here

        projects_ids = Project.objects.filter(name__in=input("Enter project names separated by commas: ").upper().split(",")).values_list('id', flat=True)
        
        print("\n--- En tenant compte que des infrastructures principes ---\n")
        subprojects = Subproject.objects.filter(
            component__name__icontains="Composante 1.1",
            subproject_type_designation="Subproject"
        ).get_actifs(projects_ids)
        subprojects_exclude_groups_not_one = subprojects.exclude(Q(
            Q(breeders_farmers_group__isnull=True) | Q(breeders_farmers_group=False),
            Q(women_s_group__isnull=True) | Q(women_s_group=False),
            Q(youth_group__isnull=True) | Q(youth_group=False),
            Q(ethnic_minority_group__isnull=True) | Q(ethnic_minority_group=False)
        ))

        nbr_breeders_farmers_group = subprojects.filter(breeders_farmers_group=True).count()
        nbr_women_s_group = subprojects.filter(women_s_group=True).count()
        nbr_youth_group = subprojects.filter(youth_group=True).count()
        nbr_ethnic_minority_group = subprojects.filter(ethnic_minority_group=True).count()
        nbr_refugee_and_internally_displaced_persons_group = subprojects.filter(refugee_and_internally_displaced_persons_group=True).count()

        
        print("Total sous-projets : ", subprojects.count())
        print("Total sous-projets sans groupe : ", subprojects.count() - subprojects_exclude_groups_not_one.count())

        # Pourcentage arrondi 2 chiffres après la virgule ex. 11.11 %
        print(f"Pourcentage sous-projets avec groupe d'agriculteurs et éleveurs : {(nbr_breeders_farmers_group / subprojects.count() * 100) if subprojects.count() > 0 else 0:.2f} %")
        print(f"Pourcentage sous-projets avec groupe de femmes : {(nbr_women_s_group / subprojects.count() * 100) if subprojects.count() > 0 else 0:.2f} %")
        print(f"Pourcentage sous-projets avec groupe de jeunes : {(nbr_youth_group / subprojects.count() * 100) if subprojects.count() > 0 else 0:.2f} %")
        print(f"Pourcentage sous-projets avec groupe ethnique minoritaire : {(nbr_ethnic_minority_group / subprojects.count() * 100) if subprojects.count() > 0 else 0:.2f} %")
        print(f"Pourcentage sous-projets avec groupe des réfugiés et des déplacés internes : {(nbr_refugee_and_internally_displaced_persons_group / subprojects.count() * 100) if subprojects.count() > 0 else 0:.2f} %")


        print("\n--- En comptant toutes les infrastructures ---\n")
        subprojects = Subproject.objects.filter(
            component__name__icontains="Composante 1.1"
        ).get_actifs(projects_ids)
        subprojects_exclude_groups_not_one = subprojects.exclude(Q(
            Q(breeders_farmers_group__isnull=True) | Q(breeders_farmers_group=False),
            Q(women_s_group__isnull=True) | Q(women_s_group=False),
            Q(youth_group__isnull=True) | Q(youth_group=False),
            Q(ethnic_minority_group__isnull=True) | Q(ethnic_minority_group=False)
        ))

        nbr_breeders_farmers_group = subprojects.filter(breeders_farmers_group=True).count()
        nbr_women_s_group = subprojects.filter(women_s_group=True).count()
        nbr_youth_group = subprojects.filter(youth_group=True).count()
        nbr_ethnic_minority_group = subprojects.filter(ethnic_minority_group=True).count()
        nbr_refugee_and_internally_displaced_persons_group = subprojects.filter(refugee_and_internally_displaced_persons_group=True).count()


        print("Total infrastructures : ", subprojects.count())
        print("Total infrastructures sans groupe : ", subprojects.count() - subprojects_exclude_groups_not_one.count())
        # Pourcentage arrondi 2 chiffres après la virgule ex. 11.11 %
        print(f"Pourcentage infrastructures avec groupe d'agriculteurs et éleveurs : {(nbr_breeders_farmers_group / subprojects.count() * 100) if subprojects.count() > 0 else 0:.2f} %")
        print(f"Pourcentage infrastructures avec groupe de femmes : {(nbr_women_s_group / subprojects.count() * 100) if subprojects.count() > 0 else 0:.2f} %")
        print(f"Pourcentage infrastructures avec groupe de jeunes : {(nbr_youth_group / subprojects.count() * 100) if subprojects.count() > 0 else 0:.2f} %")
        print(f"Pourcentage infrastructures avec groupe ethnique minoritaire : {(nbr_ethnic_minority_group / subprojects.count() * 100) if subprojects.count() > 0 else 0:.2f} %")
        print(f"Pourcentage infrastructures avec groupe des réfugiés et des déplacés internes : {(nbr_refugee_and_internally_displaced_persons_group / subprojects.count() * 100) if subprojects.count() > 0 else 0:.2f} %")


        self.stdout.write(self.style.SUCCESS('Successfully executed mycommand!'))

