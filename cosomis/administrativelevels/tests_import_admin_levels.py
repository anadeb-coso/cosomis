from django.test import TestCase

from administrativelevels.functions_import_admin_levels import (
    link_levels_to_project, process_rows, project_link_counts, rows_from_columns,
)
from administrativelevels.models import AdministrativeLevel as A
from subprojects.models import Project


def columns(rows):
    names = ["Région", "Préfecture", "Commune", "Canton", "Village/localité"]
    return {name: {i: row[j] for i, row in enumerate(rows)} for j, name in enumerate(names)}


class AdministrativeLevelImportPreviewTestCase(TestCase):

    def setUp(self):
        self.region = A.objects.create(name="ZZTEST SAVANES", type=A.REGION)
        self.prefecture = A.objects.create(name="OTI", type=A.PREFECTURE, parent=self.region)
        self.commune = A.objects.create(name="OTI 2", type=A.COMMUNE, parent=self.prefecture)
        self.canton = A.objects.create(name="LOKO", type=A.CANTON, parent=self.commune)
        self.project = Project.objects.create(name="ZZTEST PROJECT")
        self.project.administrative_levels.add(self.region)
        self.rows = rows_from_columns(columns([
            ("ZZTEST SAVANES", "OTI", "OTI 2", "LOKO", "KEREKETE 2"),
            ("ZZTEST SAVANES", "OTI", "OTI 2", "LOKO", "TOMONGUE"),
            ("ZZTEST SAVANES", "OTI", "OTI 2", "NEW CANTON", "NEW VILLAGE"),
        ]))

    def test_preview_saves_nothing_and_matches_the_import(self):
        before = A.objects.count()
        preview = process_rows(self.rows)
        self.assertEqual(A.objects.count(), before)
        self.assertEqual(preview['counts']['new'], 4)  # KEREKETE 2, TOMONGUE, NEW CANTON, NEW VILLAGE
        self.assertEqual(preview['counts']['existing'], 4)
        by_type = {row['type']: row for row in preview['by_type']}
        self.assertEqual(by_type[A.CANTON]['new'], 1)
        self.assertEqual(by_type[A.VILLAGE]['new'], 3)
        self.assertEqual(project_link_counts(preview, self.project), {'already_linked': 1, 'to_link': 7})

        done = process_rows(self.rows, apply=True)
        self.assertEqual(A.objects.count(), before + 4)
        self.assertEqual(done['counts'], {**preview['counts']})
        self.assertTrue(A.objects.filter(name="NEW VILLAGE", parent__name="NEW CANTON", parent__parent=self.commune).exists())

        linked = link_levels_to_project(self.project, done['created_ids'] | done['existing_ids'])
        self.assertEqual(linked, 7)
        self.assertEqual(self.project.administrative_levels.count(), 8)
