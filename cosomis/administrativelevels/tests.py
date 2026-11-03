from django.test import TestCase

from administrativelevels.functions import save_csv_file_datas_in_db
from administrativelevels.functions_lookup import AdministrativeLevelResolver, match_by_name
from administrativelevels.models import AdministrativeLevel as A


def columns(rows):
    """Lignes [(région, préfecture, commune, canton, village)] -> dict de colonnes comme le lit l'import."""
    names = ["Région", "Préfecture", "Commune", "Canton", "Village/localité"]
    return {name: {i: row[j] for i, row in enumerate(rows)} for j, name in enumerate(names)}


class HomonymCantonsTestCase(TestCase):
    """Deux cantons LOKO : un à OTI 2, un à TANDJOUARE 1 (cas réel de l'import FA2-COSO)."""

    def setUp(self):
        self.savanes = savanes = A.objects.create(name="ZZTEST SAVANES", type=A.REGION)
        oti = A.objects.create(name="OTI", type=A.PREFECTURE, parent=savanes)
        tandjouare = A.objects.create(name="TANDJOUARE", type=A.PREFECTURE, parent=savanes)
        self.oti_2 = A.objects.create(name="OTI 2", type=A.COMMUNE, parent=oti)
        self.tandjouare_1 = A.objects.create(name="TANDJOUARE 1", type=A.COMMUNE, parent=tandjouare)
        self.loko_oti = A.objects.create(name="LOKO", type=A.CANTON, parent=self.oti_2)
        self.loko_tandjouare = A.objects.create(name="LOKO", type=A.CANTON, parent=self.tandjouare_1)

    def test_import_attaches_villages_to_the_canton_of_their_commune(self):
        save_csv_file_datas_in_db(columns([
            ("ZZTEST SAVANES", "OTI", "OTI 2", "LOKO", "KEREKETE 2"),
            ("ZZTEST SAVANES", "OTI", "OTI 2", "LOKO", "TOMONGUE"),
            # orthographe du fichier : TANDJOARE au lieu de TANDJOUARE
            ("ZZTEST SAVANES", "TANDJOARE", "TANDJOARE 1", "LOKO", "BAMONGUE"),
            ("ZZTEST SAVANES", "TANDJOARE", "TANDJOARE 1", "LOKO", "YOUAK I"),
            ("ZZTEST SAVANES", "TANDJOARE", "TANDJOARE 1", "LOKO", "YOUAK II"),
        ]))
        self.assertEqual(set(A.objects.filter(parent=self.loko_oti).values_list("name", flat=True)), {"KEREKETE 2", "TOMONGUE"})
        self.assertEqual(set(A.objects.filter(parent=self.loko_tandjouare).values_list("name", flat=True)), {"BAMONGUE", "YOUAK I", "YOUAK II"})
        # aucun doublon de préfecture / commune / canton créé à cause de l'orthographe
        self.assertEqual(A.objects.filter(type=A.PREFECTURE, parent=self.savanes).count(), 2)
        self.assertEqual(A.objects.filter(type=A.COMMUNE, parent__parent=self.savanes).count(), 2)
        self.assertEqual(A.objects.filter(type=A.CANTON, parent__parent__parent=self.savanes).count(), 2)

    def test_reimport_does_not_duplicate_and_coordinates_stay_on_the_village(self):
        rows = columns([("ZZTEST SAVANES", "OTI", "OTI 2", "LOKO", "Kerekete-2")])
        rows["Latitude"] = {0: 10.5}
        rows["Longitude"] = {0: 0.7}
        save_csv_file_datas_in_db(rows)
        save_csv_file_datas_in_db(columns([("ZZTEST SAVANES", "OTI", "OTI 2", "LOKO", "KEREKETE 2")]))
        self.assertEqual(A.objects.filter(type=A.VILLAGE, parent=self.loko_oti).count(), 1)
        self.loko_oti.refresh_from_db()
        self.assertIsNone(self.loko_oti.latitude)  # les coordonnées du village ne vont plus sur le canton

    def test_find_village_uses_the_canton_commune(self):
        A.objects.create(name="TOMONGUE", type=A.VILLAGE, parent=self.loko_oti)
        A.objects.create(name="TOMONGUE", type=A.VILLAGE, parent=self.loko_tandjouare)
        resolver = AdministrativeLevelResolver()
        # canton seul : ambigu -> jamais choisi au hasard
        self.assertEqual(resolver.find("TOMONGUE", A.VILLAGE, canton="LOKO").error, "ambiguous")
        # avec la commune (même mal orthographiée) : le bon
        self.assertEqual(resolver.find("TOMONGUE", A.VILLAGE, canton="LOKO", commune="TANDJOARE 1").level.parent_id, self.loko_tandjouare.id)
        self.assertEqual(resolver.find("TOMONGUE", A.VILLAGE, canton="LOKO", commune="OTI 2").level.parent_id, self.loko_oti.id)
        self.assertEqual(resolver.find("LOKO", A.CANTON, commune="TANDJOARE 1").level.id, self.loko_tandjouare.id)
        self.assertEqual(resolver.find("LOKO", A.CANTON).error, "ambiguous")

    def test_numbers_are_never_confused(self):
        oti_1 = A(name="OTI 1", type=A.COMMUNE)
        youak_i = A(name="YOUAK I", type=A.VILLAGE)
        self.assertEqual(match_by_name("OTI 2", [oti_1], fuzzy=True)[0], [])
        self.assertEqual(match_by_name("YOUAK II", [youak_i], fuzzy=True)[0], [])
        self.assertEqual(match_by_name("TANDJOARE 1", [self.tandjouare_1], fuzzy=True)[0], [self.tandjouare_1])
