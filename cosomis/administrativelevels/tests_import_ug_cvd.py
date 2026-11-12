"""Import des Unités géographiques et CVD (functions_import_ug_cvd / views_import_ug_cvd)."""
import io
from unittest import mock

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from openpyxl import Workbook

from administrativelevels.functions_import_ug_cvd import (
    ImportFileError, apply_import_plan, build_import_plan, read_import_file,
)
from administrativelevels.models import CVD, AdministrativeLevel as A, GeographicalUnit as GU

HEADERS = ('Région', 'Préfecture', 'Commune', 'Canton', 'Village/Quartier', 'CVD', 'Siège CVD', 'Unité géographique')


def make_rows(*lines, first_line=2):
    """(canton, village, cvd, siège, ug) -> lignes comme les rend read_import_file (région/préfecture/commune du jeu de test)."""
    rows = []
    for offset, line in enumerate(lines):
        canton, village, cvd, hq, unit = line
        commune = 'ZZ COMMUNE B' if canton == 'BETA' else 'ZZ COMMUNE A'
        rows.append({'line': first_line + offset, 'region': 'ZZ REGION', 'prefecture': 'ZZ PREFECTURE', 'commune': commune,
                     'canton': canton, 'village': village, 'cvd': cvd, 'headquarters': hq, 'unit': str(unit) if unit is not None else ''})
    return rows


def import_rows(*lines):
    plan = build_import_plan(make_rows(*lines))
    apply_import_plan(plan)
    return plan


def xlsx_file(headers, lines, name='ug_cvd.xlsx', sheet='Liste'):
    workbook = Workbook()
    workbook.active.title = 'Autre'
    workbook.active.append(('Rien',))
    sheet_ = workbook.create_sheet(sheet)
    sheet_.append(headers)
    for line in lines:
        sheet_.append(line)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


class ImportTestBase(TestCase):
    def setUp(self):
        region = A.objects.create(name='ZZ REGION', type=A.REGION)
        prefecture = A.objects.create(name='ZZ PREFECTURE', type=A.PREFECTURE, parent=region)
        commune_a = A.objects.create(name='ZZ COMMUNE A', type=A.COMMUNE, parent=prefecture)
        commune_b = A.objects.create(name='ZZ COMMUNE B', type=A.COMMUNE, parent=prefecture)
        self.alpha = A.objects.create(name='ALPHA', type=A.CANTON, parent=commune_a)
        self.beta = A.objects.create(name='BETA', type=A.CANTON, parent=commune_b)
        self.v = {}
        for name in ('ADJENGRE', 'AKONTA', 'ATCHIDE', 'KANKAMPIENI', 'OBOGOU', 'TOMONE', 'SOGOU'):
            self.v[name] = A.objects.create(name=name, type=A.VILLAGE, parent=self.alpha)
        for name in ('BARKOISSI', 'NABAB 1', 'SOGOU'):
            self.v['B ' + name] = A.objects.create(name=name, type=A.VILLAGE, parent=self.beta)

    def village(self, key):
        return A.objects.get(pk=self.v[key].pk)


class GroupingRulesTests(ImportTestBase):
    def test_villages_with_same_cvd_name_in_a_canton_form_one_cvd(self):
        import_rows(
            ('ALPHA', 'AKONTA', 'TAMPINLOGO/LOUME', 'NON', 7),
            ('ALPHA', 'ATCHIDE', 'TAMPINLOGO/LOUME', 'OUI', 7),
        )
        cvd = CVD.objects.get(name='TAMPINLOGO/LOUME')
        self.assertEqual(set(cvd.get_villages().values_list('name', flat=True)), {'AKONTA', 'ATCHIDE'})
        self.assertEqual(cvd.headquarters_village_id, self.v['ATCHIDE'].id)
        self.assertEqual(cvd.geographical_unit.canton_id, self.alpha.id)
        self.assertEqual(cvd.geographical_unit.attributed_number_in_canton, 7)
        self.assertEqual(self.village('AKONTA').geographical_unit_id, cvd.geographical_unit_id)

    def test_cvds_with_same_unit_number_in_a_canton_form_one_unit(self):
        import_rows(
            ('ALPHA', 'ADJENGRE', 'ASSERE', 'OUI', 1),
            ('ALPHA', 'AKONTA', 'TAMPINLOGO', 'OUI', 1),
            ('ALPHA', 'TOMONE', 'TOMONE', 'TOMONE', 2),
        )
        unit_1 = GU.objects.get(canton=self.alpha, attributed_number_in_canton=1)
        self.assertEqual(set(unit_1.get_cvds().values_list('name', flat=True)), {'ASSERE', 'TAMPINLOGO'})
        self.assertEqual(set(unit_1.get_villages().values_list('name', flat=True)), {'ADJENGRE', 'AKONTA'})
        self.assertEqual(GU.objects.filter(canton=self.alpha).count(), 2)

    def test_unit_number_and_cvd_name_are_only_unique_within_a_canton(self):
        import_rows(
            ('ALPHA', 'SOGOU', 'SOGOU', 'OUI', 1),
            ('BETA', 'SOGOU', 'SOGOU', 'OUI', 1),
            ('BETA', 'BARKOISSI', 'BARKOISSI', 'OUI', 2),
        )
        self.assertEqual(GU.objects.filter(attributed_number_in_canton=1).count(), 2)
        self.assertEqual(CVD.objects.filter(name='SOGOU').count(), 2)
        self.assertEqual(self.village('SOGOU').geographical_unit.canton_id, self.alpha.id)
        self.assertEqual(self.village('B SOGOU').geographical_unit.canton_id, self.beta.id)
        self.assertNotEqual(self.village('SOGOU').cvd_id, self.village('B SOGOU').cvd_id)

    def test_headquarters_given_by_name_with_spacing_differences(self):
        # cas réel du fichier : « KANKAMPIENI » avec un espace final, siège donné par son nom sur chaque ligne
        import_rows(
            ('ALPHA', 'KANKAMPIENI ', 'KANKAMPIENI ', 'KANKAMPIENI ', 23),
            ('ALPHA', 'OBOGOU', 'KANKAMPIENI ', 'KANKAMPIENI ', 23),
        )
        cvd = CVD.objects.get()
        self.assertEqual(cvd.headquarters_village_id, self.v['KANKAMPIENI'].id)
        self.assertEqual(cvd.get_villages().count(), 2)

    def test_headquarters_defaults_to_the_village_named_like_the_cvd(self):
        plan = import_rows(
            ('ALPHA', 'AKONTA', 'TOMONE', '', 3),
            ('ALPHA', 'TOMONE', 'TOMONE', '', 3),
        )
        self.assertEqual(CVD.objects.get().headquarters_village_id, self.v['TOMONE'].id)
        self.assertEqual(plan.warnings, [])

    def test_headquarters_not_given_is_reported(self):
        plan = import_rows(
            ('ALPHA', 'AKONTA', 'LOUME', '', 3),
            ('ALPHA', 'ATCHIDE', 'LOUME', 'NON', 3),
        )
        self.assertEqual(CVD.objects.get().headquarters_village_id, self.v['AKONTA'].id)
        self.assertTrue(any('LOUME' in w for w in plan.warnings))

    def test_lines_without_cvd_nor_unit_are_ignored(self):
        plan = import_rows(
            ('ALPHA', 'AKONTA', '', '', None),
            ('ALPHA', 'ATCHIDE', 'ATCHIDE', 'OUI', 1),
        )
        self.assertEqual(plan.ignored_rows, [2])
        self.assertIsNone(self.village('AKONTA').cvd_id)
        self.assertEqual(CVD.objects.count(), 1)

    def test_incomplete_lines_are_reported(self):
        plan = build_import_plan(make_rows(
            ('ALPHA', 'AKONTA', 'AKONTA', 'OUI', None),
            ('ALPHA', 'ATCHIDE', '', '', 4),
            ('ALPHA', 'TOMONE', 'TOMONE', 'OUI', 'UG A'),
        ))
        self.assertEqual([e['line'] for e in plan.row_errors], [2, 3, 4])
        self.assertFalse(plan.can_be_applied)

    def test_unit_number_formats(self):
        import_rows(('ALPHA', 'AKONTA', 'AKONTA', 'OUI', '7.0'), ('ALPHA', 'TOMONE', 'TOMONE', 'OUI', 'UG 08'))
        self.assertEqual(set(GU.objects.values_list('attributed_number_in_canton', flat=True)), {7, 8})
        plan = build_import_plan(make_rows(('ALPHA', 'SOGOU', 'SOGOU', 'OUI', '7.5')))
        self.assertEqual(len(plan.row_errors), 1)  # « 7.5 » n'est pas un numéro d'UG


class MissingVillagesTests(ImportTestBase):
    def test_missing_villages_are_reported_and_never_created(self):
        plan = import_rows(
            ('ALPHA', 'AKONTA', 'TAMPINLOGO', 'OUI', 1),
            ('ALPHA', 'AKONTAA', 'TAMPINLOGO', 'NON', 1),  # faute de frappe : signalé, pas rapproché
            ('ALPHA', 'INCONNU', 'INCONNU', 'OUI', 2),
            ('GAMMA', 'ADJENGRE', 'ADJENGRE', 'OUI', 3),  # canton inexistant
            ('BETA', 'ADJENGRE', 'ADJENGRE', 'OUI', 4),  # le village existe, mais dans un autre canton
        )
        missing = {(m['line'], m['village']) for m in plan.missing_villages}
        self.assertEqual(missing, {(3, 'AKONTAA'), (4, 'INCONNU'), (5, 'ADJENGRE'), (6, 'ADJENGRE')})
        suggestion = next(m for m in plan.missing_villages if m['village'] == 'AKONTAA')['suggestions']
        self.assertIn('AKONTA', suggestion)
        self.assertFalse(A.objects.filter(name__in=['AKONTAA', 'INCONNU']).exists())
        self.assertFalse(A.objects.filter(name='ADJENGRE', parent=self.beta).exists())
        self.assertIsNone(self.village('ADJENGRE').cvd_id)
        # le reste du fichier est bien importé ; une UG sans aucun village trouvé n'est pas créée
        self.assertEqual(self.village('AKONTA').cvd.name, 'TAMPINLOGO')
        self.assertEqual(GU.objects.count(), 1)
        self.assertEqual(CVD.objects.count(), 1)

    def test_parent_misspellings_are_tolerated(self):
        rows = make_rows(('ALPHA', 'AKONTA', 'AKONTA', 'OUI', 1))
        rows[0]['commune'] = 'ZZ COMUNE A'  # faute dans la commune : le canton est quand même trouvé
        plan = build_import_plan(rows)
        self.assertEqual(plan.missing_villages, [])
        self.assertEqual(plan.counts()['villages'], 1)


class InconsistencyTests(ImportTestBase):
    def assert_nothing_saved(self, plan):
        self.assertEqual(GU.objects.count(), 0)
        self.assertEqual(CVD.objects.count(), 0)
        self.assertFalse(A.objects.filter(type=A.VILLAGE).exclude(cvd=None).exists())

    def test_cvd_given_two_unit_numbers_excludes_both_units(self):
        plan = import_rows(
            ('ALPHA', 'AKONTA', 'TAMPINLOGO', 'OUI', 1),
            ('ALPHA', 'ATCHIDE', 'TAMPINLOGO', 'NON', 2),
            ('ALPHA', 'TOMONE', 'TOMONE', 'OUI', 2),
        )
        self.assertEqual({u.number for u in plan.invalid_units}, {1, 2})
        self.assertTrue(all('TAMPINLOGO' in u.errors[0] for u in plan.invalid_units))
        self.assert_nothing_saved(plan)

    def test_village_in_two_cvds_is_excluded(self):
        plan = import_rows(
            ('ALPHA', 'AKONTA', 'TAMPINLOGO', 'OUI', 1),
            ('ALPHA', 'AKONTA', 'TOMONE', 'NON', 2),
            ('ALPHA', 'TOMONE', 'TOMONE', 'OUI', 2),
            ('ALPHA', 'SOGOU', 'SOGOU', 'OUI', 3),
        )
        self.assertEqual({u.number for u in plan.invalid_units}, {1, 2})
        self.assertEqual([u.number for u in plan.valid_units], [3])
        self.assertIsNone(self.village('AKONTA').cvd_id)
        self.assertIsNone(self.village('TOMONE').cvd_id)
        self.assertEqual(self.village('SOGOU').cvd.name, 'SOGOU')

    def test_repeated_identical_line_is_only_a_warning(self):
        plan = import_rows(
            ('ALPHA', 'AKONTA', 'AKONTA', 'OUI', 1),
            ('ALPHA', 'AKONTA', 'AKONTA', 'OUI', 1),
        )
        self.assertEqual(plan.invalid_units, [])
        self.assertEqual(len(plan.warnings), 1)
        self.assertEqual(CVD.objects.get().get_villages().count(), 1)

    def test_two_different_headquarters_exclude_the_unit(self):
        plan = import_rows(
            ('ALPHA', 'AKONTA', 'TAMPINLOGO', 'OUI', 1),
            ('ALPHA', 'ATCHIDE', 'TAMPINLOGO', 'OUI', 1),
        )
        self.assertEqual(len(plan.invalid_units), 1)
        self.assert_nothing_saved(plan)

    def test_headquarters_name_outside_the_cvd_is_reported(self):
        plan = import_rows(
            ('ALPHA', 'AKONTA', 'TAMPINLOGO', 'SOGOU', 1),
            ('ALPHA', 'ATCHIDE', 'TAMPINLOGO', 'SOGOU', 1),
        )
        self.assertTrue(any('SOGOU' in w for w in plan.warnings))
        self.assertEqual(plan.invalid_units, [])
        self.assertIn(CVD.objects.get().headquarters_village_id, {self.v['AKONTA'].id, self.v['ATCHIDE'].id})


class ExistingDataTests(ImportTestBase):
    def test_preview_writes_nothing(self):
        plan = build_import_plan(make_rows(('ALPHA', 'AKONTA', 'AKONTA', 'OUI', 1)))
        self.assertEqual(plan.counts()['units_to_create'], 1)
        self.assertEqual(GU.objects.count(), 0)
        self.assertEqual(CVD.objects.count(), 0)

    def test_reimport_does_not_duplicate(self):
        lines = (
            ('ALPHA', 'AKONTA', 'TAMPINLOGO', 'NON', 7),
            ('ALPHA', 'ATCHIDE', 'TAMPINLOGO', 'OUI', 7),
        )
        import_rows(*lines)
        plan = build_import_plan(make_rows(*lines))
        counts = plan.counts()
        self.assertEqual((counts['units_to_create'], counts['cvds_to_create']), (0, 0))
        self.assertTrue(all(e['status'] == 'unchanged' for u in plan.valid_units for c in u.cvds.values() for e in c.entries))
        apply_import_plan(plan)
        self.assertEqual((GU.objects.count(), CVD.objects.count()), (1, 1))

    def test_existing_unit_and_cvd_are_reused_and_villages_moved(self):
        # état « auto-généré » : une UG et un CVD par village
        old_units = {}
        for number, key in enumerate(('AKONTA', 'ATCHIDE'), start=1):
            unit = GU.objects.create(canton=self.alpha, attributed_number_in_canton=number, unique_code=f'OLD{number}')
            cvd = CVD.objects.create(name=key, geographical_unit=unit, unique_code=f'OLD{number}', headquarters_village=self.v[key])
            A.objects.filter(pk=self.v[key].pk).update(cvd=cvd, geographical_unit=unit)
            old_units[key] = unit
        akonta_cvd = self.village('AKONTA').cvd

        plan = build_import_plan(make_rows(
            ('ALPHA', 'AKONTA', 'AKONTA', 'OUI', 1),
            ('ALPHA', 'ATCHIDE', 'AKONTA', 'NON', 1),
        ))
        unit_plan = plan.valid_units[0]
        self.assertEqual(unit_plan.existing.pk, old_units['AKONTA'].pk)
        cvd_plan = next(iter(unit_plan.cvds.values()))
        self.assertEqual(cvd_plan.existing.pk, akonta_cvd.pk)
        self.assertEqual({e['village'].name: e['status'] for e in cvd_plan.entries}, {'AKONTA': 'unchanged', 'ATCHIDE': 'moved'})
        # le CVD et l'UG d'ATCHIDE se vident : signalés, pas supprimés
        self.assertEqual([c.name for c in plan.emptied_cvds], ['ATCHIDE'])
        self.assertEqual([u.pk for u in plan.emptied_units], [old_units['ATCHIDE'].pk])

        apply_import_plan(plan)
        self.assertEqual(self.village('ATCHIDE').cvd_id, akonta_cvd.pk)
        self.assertEqual(self.village('ATCHIDE').geographical_unit_id, old_units['AKONTA'].pk)
        self.assertEqual(CVD.objects.count(), 2)
        self.assertEqual(GU.objects.count(), 2)

    def test_villages_of_an_existing_unit_absent_from_the_file_are_reported(self):
        unit = GU.objects.create(canton=self.alpha, attributed_number_in_canton=1, unique_code='OLD1')
        A.objects.filter(pk=self.v['SOGOU'].pk).update(geographical_unit=unit)
        plan = build_import_plan(make_rows(('ALPHA', 'AKONTA', 'AKONTA', 'OUI', 1)))
        self.assertEqual([v.name for v in plan.valid_units[0].remaining_villages], ['SOGOU'])

    def test_new_codes_are_unique(self):
        GU.objects.create(canton=self.beta, attributed_number_in_canton=9, unique_code=str(GU.objects.count() + 2).zfill(9))
        import_rows(('ALPHA', 'AKONTA', 'AKONTA', 'OUI', 1), ('ALPHA', 'TOMONE', 'TOMONE', 'OUI', 2))
        codes = list(GU.objects.values_list('unique_code', flat=True))
        self.assertEqual(len(codes), len(set(codes)))
        self.assertTrue(all(len(c) == 9 for c in CVD.objects.values_list('unique_code', flat=True)))


class ReadFileTests(TestCase):
    def test_reads_the_chosen_sheet_and_the_template_columns(self):
        upload = xlsx_file(HEADERS + ('Nom de FC',), [
            ('CENTRALE', 'SOTOUBOUA', 'SOTOUBOUA 2', 'ADJENGRE', 'ATCHIDE', 'TAMPINLOGO/LOUME', 'OUI', 7, 'X'),
            (None,) * 9,
            ('CENTRALE', 'SOTOUBOUA', 'SOTOUBOUA 2', 'ADJENGRE', 'AKONTA ', ' TAMPINLOGO/LOUME', 'NON', 7.0, None),
        ])
        rows = read_import_file(upload, 'Liste')
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], {'line': 2, 'region': 'CENTRALE', 'prefecture': 'SOTOUBOUA', 'commune': 'SOTOUBOUA 2', 'canton': 'ADJENGRE',
                                   'village': 'ATCHIDE', 'cvd': 'TAMPINLOGO/LOUME', 'headquarters': 'OUI', 'unit': '7'})
        self.assertEqual((rows[1]['line'], rows[1]['village'], rows[1]['cvd'], rows[1]['unit']), (4, 'AKONTA', 'TAMPINLOGO/LOUME', '7'))

    def test_village_localite_header_and_csv(self):
        content = 'Région;Préfecture;Commune;Canton;Village/localité;CVD;Siège CVD;Unité géographique\nR;P;C;K;V1;CVD1;OUI;3\n'
        rows = read_import_file(SimpleUploadedFile('f.csv', content.encode('utf-8')))
        self.assertEqual((rows[0]['village'], rows[0]['unit']), ('V1', '3'))

    def test_missing_column_is_refused(self):
        with self.assertRaises(ImportFileError):
            read_import_file(xlsx_file(('Canton', 'Village', 'CVD'), [('K', 'V', 'C')]), 'Liste')


class ImportViewTests(ImportTestBase):
    def setUp(self):
        super().setUp()
        # Le menu (context processor) lit les projets de l'utilisateur en SQL brut dans les tables de CDD,
        # absentes de la base de test.
        for target in ('cosomis.services.get_user_projects', 'cosomis.project_scope.get_user_projects'):
            patcher = mock.patch(target, return_value=[])
            patcher.start()
            self.addCleanup(patcher.stop)
        self.url = reverse('administrativelevels:geographical_unit_cvd_import')
        self.admin = User.objects.create_superuser('zz_admin', 'zz@example.com', 'pwd')
        self.client.force_login(self.admin)
        self.select_project()

    def select_project(self):
        session = self.client.session
        session['project_id'] = 1
        session['tree_structure_projects_ids'] = [1]
        session.save()

    def upload(self):
        return self.client.post(self.url, {'sheet_name': 'Liste', 'file': xlsx_file(HEADERS, [
            ('ZZ REGION', 'ZZ PREFECTURE', 'ZZ COMMUNE A', 'ALPHA', 'AKONTA', 'TAMPINLOGO', 'NON', 7),
            ('ZZ REGION', 'ZZ PREFECTURE', 'ZZ COMMUNE A', 'ALPHA', 'ATCHIDE', 'TAMPINLOGO', 'OUI', 7),
            ('ZZ REGION', 'ZZ PREFECTURE', 'ZZ COMMUNE A', 'ALPHA', 'VILLAGE FANTOME', 'FANTOME', 'OUI', 8),
        ])})

    def test_upload_shows_a_preview_and_saves_nothing(self):
        response = self.upload()
        self.assertRedirects(response, self.url + '?action=preview', fetch_redirect_response=False)
        response = self.client.get(self.url + '?action=preview')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'VILLAGE FANTOME')
        self.assertContains(response, 'TAMPINLOGO')
        self.assertEqual(response.context['counts']['villages'], 2)
        self.assertEqual(response.context['counts']['missing_villages'], 1)
        self.assertEqual(CVD.objects.count(), 0)
        missing = self.client.get(self.url + '?action=missing_villages')
        self.assertIn('VILLAGE FANTOME', missing.content.decode('utf-8'))

    def test_confirm_saves(self):
        self.upload()
        response = self.client.post(self.url, {'action': 'confirm'})
        self.assertRedirects(response, reverse('administrativelevels:geographical_units_list'), fetch_redirect_response=False)
        self.assertEqual(CVD.objects.get().get_villages().count(), 2)
        self.assertNotIn('geographical_unit_cvd_import', self.client.session)

    def test_cancel_saves_nothing(self):
        self.upload()
        self.client.post(self.url, {'action': 'cancel'})
        self.assertNotIn('geographical_unit_cvd_import', self.client.session)
        self.client.post(self.url, {'action': 'confirm'})
        self.assertEqual(CVD.objects.count(), 0)

    def test_upload_page_and_template(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)
        template = self.client.get(self.url + '?action=template')
        self.assertEqual(template.status_code, 200)
        self.assertTrue(template.content.startswith(b'PK'))

    def test_reserved_to_admins(self):
        self.client.force_login(User.objects.create_user('zz_user', password='pwd'))
        self.select_project()
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.upload()
        self.assertEqual(CVD.objects.count(), 0)
        self.assertNotIn('geographical_unit_cvd_import', self.client.session)
