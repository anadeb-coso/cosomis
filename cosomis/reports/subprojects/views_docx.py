# reports/views.py (Exemple de structure)
from django.http import HttpResponse
from django.utils import timezone
from django.utils.translation import gettext as _
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from django.db.models import Prefetch
import boto3
import io
import requests
from django.conf import settings
import environ
from django.db.models import Q
from PIL import Image

from subprojects.models import Subproject, SubprojectFile # Assurez-vous d'importer vos modèles
from cosomis.constants import STRUCTURE_COMPLETED_STATUS
from subprojects.templatetags.custom_tags import separate_with_space


env = environ.Env()
env.read_env()


# Mappage des codes EXIF vers les opérations Pillow
# Source : https://github.com/python-pillow/Pillow/blob/main/src/PIL/ExifTags.py
EXIF_ORIENTATION_TAG = 274

ORIENTATION_TRANSFORMATIONS = {
    2: Image.FLIP_LEFT_RIGHT,
    3: Image.ROTATE_180,
    4: Image.FLIP_TOP_BOTTOM,
    5: Image.TRANSPOSE,
    6: Image.ROTATE_270,  # Tourne de 90° dans le sens horaire
    7: Image.TRANSVERSE,
    8: Image.ROTATE_90,   # Tourne de 90° dans le sens anti-horaire
}


PAGE_WIDTH_CONTENT = Inches(6.5) # Largeur typique de contenu pour marges d'1 pouce
MAX_IMAGES_PER_ROW = 3           # On n'essaiera jamais d'avoir plus de 3 images par ligne
TARGET_WIDTH_2_COLS = Inches(PAGE_WIDTH_CONTENT.inches / 2 - 0.1) # Largeur cible pour 2 colonnes
TARGET_WIDTH_3_COLS = Inches(PAGE_WIDTH_CONTENT.inches / 3 - 0.1) # Largeur cible pour 3 colonnes
MAX_PAGE_CONTENT_HEIGHT_INCHES = 7.0 # Exemple basé sur 1 pouce de marge totale
MAX_HEIGHT_CONSTRAINT = Inches(MAX_PAGE_CONTENT_HEIGHT_INCHES / 2) # 5.0 inches

# --- 2. Fonctions Utilitaires ---

def get_image_info(image_stream):
    """Récupère la largeur/hauteur d'une image à partir d'un flux en mémoire."""
    img = Image.open(image_stream)
    return img.width, img.height

def get_image_stream_and_reset(url, s3_client, bucket_name):
    """Télécharge l'image, corrige l'EXIF et retourne le flux, puis le prépare pour une nouvelle lecture."""
    # Cette fonction doit appeler votre fonction 'rotate_image_based_on_exif'
    # La rotation doit se faire AVANT de lire la taille pour obtenir la taille corrigée
    
    # 1. Télécharger et corriger l'EXIF (comme fait précédemment)
    corrected_stream = get_image_data(url, s3_client, bucket_name) 
    
    # Le flux est prêt à être lu pour l'insertion
    corrected_stream.seek(0)
    return corrected_stream



# Paramètres KoBo (À configurer dans settings.py ou autre endroit sécurisé)
KOBO_AUTH_TOKEN = KOBO_TOKEN=env('KOBO_TOKEN_V2')
KOBO_HEADERS = {'Authorization': f'Token {KOBO_AUTH_TOKEN}'}
KOBO_URL_PREFIX = "https://kf.kobotoolbox.org" # Assurez-vous que le préfixe correspond à votre instance



def rotate_image_based_on_exif(image_stream):
    """
    Lit le tag EXIF d'orientation d'un flux d'image (BytesIO) et fait pivoter l'image si nécessaire.
    Retourne un nouveau flux d'image corrigé.
    """
    
    # 1. Lire l'image à partir du flux
    img = Image.open(image_stream)
    
    try:
        exif = img._getexif()
        if exif:
            orientation = exif.get(EXIF_ORIENTATION_TAG)
            
            # 2. Appliquer la rotation
            if orientation in ORIENTATION_TRANSFORMATIONS:
                # Appliquer la transformation
                img = img.transpose(ORIENTATION_TRANSFORMATIONS[orientation])
                
                # 3. Supprimer le tag EXIF d'orientation
                # Cela garantit qu'il ne sera pas interprété par d'autres lecteurs
                img.info['exif'] = None
                
    except Exception:
        # Ignorer si l'image n'a pas d'EXIF ou si la lecture échoue
        pass

    # 4. Sauvegarder l'image corrigée dans un nouveau flux en mémoire
    output_stream = io.BytesIO()
    
    # Utilisez le format original de l'image si possible (souvent 'jpeg')
    # Si le format est inconnu, utilisez 'jpeg' comme fallback
    output_format = img.format if img.format in ['jpeg', 'png'] else 'jpeg'
    
    img.save(output_stream, format=output_format)
    width, height = img.width, img.height

    output_stream.seek(0)
    
    return output_stream, width, height


def get_image_data(url, s3_client, bucket_name):
    if url and "?" in url:
        url = url.split("?")[0]

    if KOBO_URL_PREFIX in url:
        # Téléchargement depuis KoBo
        try:
            response = requests.get(url, headers=KOBO_HEADERS, stream=True)
            response.raise_for_status() # Lève une exception si le statut n'est pas 200
            image_data = response.content
        except requests.RequestException as e:
            raise Exception(f"Erreur de téléchargement KoBo : {e}")
    else:
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status() # Lève une exception si le statut n'est pas 200
            image_data = response.content
        except requests.RequestException as e:
            # 1. Récupérer le contenu binaire de S3
            s3_object = s3_client.get_object(Bucket=bucket_name, Key=url)
            image_data = s3_object['Body'].read()
        except Exception as exc:
            raise Exception(f"Erreur de téléchargement S3 : {exc}")
            
            
    content_type = response.headers.get('Content-Type', '')
    if content_type.startswith('image/'):
        # Créer un buffer en mémoire
        return rotate_image_based_on_exif(io.BytesIO(image_data))

    raise Exception(f"Ce fichier n'est pas une image : {url}")



def generate_subproject_report(request):
    s3_client = boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME
    )
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME

    # 1. Configuration initiale du document
    document = Document()
    
    # Définir le style de base de la police (facultatif mais recommandé)
    style = document.styles['Normal']
    style.font.name = 'Arial'
    style.font.size = Pt(11)
    
    query = Q()
    for elt in STRUCTURE_COMPLETED_STATUS+[
        'provisoire', 'réception', 'réceptionné', 'Superstructure en cours', 'terminée', 'Superstructure construite', 'superstructure'
    ]:
        query |= Q(subproject_step__wording__icontains=elt)
        query |= Q(name__icontains=elt)

    # Récupérer les données avec pré-récupération pour optimiser
    subprojects_data = Subproject.objects.filter(
        # Ajoutez vos filtres ici (ex: réalisé et accepté)
        # id=585, # ATONTOMI (BALANKA)
        # id=680, # YIEGOU (CINKASSE)
        location_subproject_realized__parent__id=1973, # CINKASSE - CANTON
        current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS
    ).select_related(
        'component', 'location_subproject_realized__parent'
    ).prefetch_related(
        Prefetch('subprojectfile_set', queryset=SubprojectFile.objects.filter(
            Q(
                Q(file_type__icontains="image") | 
                Q(url__icontains="kobotoolbox")
            ) &
            Q(
                Q(
                    subproject_step__wording__in=STRUCTURE_COMPLETED_STATUS,
                ) | 
                Q(
                    name__in=STRUCTURE_COMPLETED_STATUS,
                ) | 
                query
            )
        ).exclude(
            Q(url__icontains=".pdf") | Q(url__icontains=".doc")
        ).order_by('order'), to_attr='photos')
    ).order_by('location_subproject_realized__parent__name', 'location_subproject_realized__name', 'component__id', 'subproject_sector', 'type_of_subproject', 'number')
    
    # Groupement des sous-projets (La logique de regroupement est cruciale)
    grouped_data = {}
    for sp in subprojects_data:
        if sp.photos:
            canton_name = sp.location_subproject_realized.parent.name if sp.location_subproject_realized else 0
            comp_name = sp.component.name if sp.component else _("Non-classé")
            
            # Le secteur est l'équivalent de la Sous-composante pour la structure du rapport
            sector = sp.subproject_sector if sp.subproject_sector else _("Sans secteur")
            
            if canton_name in grouped_data and comp_name in grouped_data[canton_name] and sector in grouped_data[canton_name][comp_name]:
                grouped_data[canton_name][comp_name][sector].append(sp)
            elif canton_name in grouped_data and comp_name in grouped_data[canton_name]:
                grouped_data[canton_name][comp_name][sector] = [sp]
            elif canton_name in grouped_data:
                grouped_data[canton_name][comp_name] = {sector: [sp]}
            else:
                grouped_data[canton_name] = {comp_name: {sector: [sp]}}
            
            # if canton_name not in grouped_data:
            #     grouped_data[canton_name] = {comp_name: {sector: [sp]}}
            # else:
            #     if comp_name not in grouped_data[canton_name]:
            #         grouped_data[canton_name][comp_name] = {sector: [sp]}
            #     else:
            #         if sector not in grouped_data[canton_name][comp_name]:
            #             grouped_data[canton_name][comp_name][sector] = [sp]
            #         else:
            #             grouped_data[canton_name][comp_name][sector].append(sp)

            # key = (canton_name, comp_name, sector)
            # if key not in grouped_data:
            #     grouped_data[key] = []
            # grouped_data[key].append(sp)
        
    # --- Section 1: Page de couverture (Simplifiée) ---
    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run('LOGO COSO').bold = True
    document.add_heading(_("Album photo des réalisations du projet COSO"), 0)
    document.add_paragraph(_("Par composante et sous-composante"))
    document.add_paragraph(f"{_('Date de génération')} : {timezone.now().strftime('%d/%m/%Y')}")
    document.add_page_break()

    # --- Section 2: Introduction/Sommaire (Placeholder) ---
    document.add_heading(_("Table des matières automatique"), 1)
    # document.add_paragraph(_("Le sommaire Word sera généré automatiquement à partir des titres de niveau 1, 2 et 3.")).style = 'List Bullet'
    document.add_page_break()
    
    document.add_heading(_("Introduction de l’album"), 1)
    document.add_paragraph(_("Ce document est une photographie globale...")).paragraph_format.first_line_indent = Inches(0.5)
    document.add_page_break()
    
    # --- Section 3: Partie principale : Album photo ---
    
    # Parcourir les groupes (Composante, Sous-composante)
    for canton_name, canton_name_v in grouped_data.items():

        # Tête de section : Composante X - [Nom complet]
        document.add_heading(f"Canton {canton_name}", 1) 

        for comp_name, comp_name_v in canton_name_v.items():

            # Sous-composante X.Y - [Nom complet] (subproject_sector)
            document.add_heading(f"{_('Sous-composante')} - {comp_name}", 2)

            for sector, subprojects in comp_name_v.items():
            
                # Secteur X.Y - (subproject_sector)
                document.add_heading(f"{_('Secteur')} - {sector}", 3)

    # for (canton_name, comp_name, sector), subprojects in sorted(grouped_data.items()):
        
        # # Tête de section : Composante X - [Nom complet]
        # document.add_heading(f"Canton {canton_name}", 1) 
        
        # # Sous-composante X.Y - [Nom complet] (subproject_sector)
        # document.add_heading(f"{_('Sous-composante')} - {comp_name}", 2)
        
        # # Secteur X.Y - (subproject_sector)
        # document.add_heading(f"{_('Secteur')} - {sector}", 3)

                for sp in subprojects:
                    # Sous-projet X.Y.Z – [Nom ou code du sous-projet]
                    # Utiliser le numéro et le titre complet
                    sp_title = f"SP{sp.joint_subproject_number or 'XXX'}.{sp.number or 'XXX'} - {sp.full_title_of_approved_subproject}"
                    document.add_heading(sp_title, 4) 
                    
                    # --- Fiche descriptive de l'ouvrage ---
                    
                    # Ouvrage 1 – Forage de Korbongou
                    document.add_heading(f"{_('Ouvrage')} {sp.number or 'N/A'} – {sp.type_of_subproject}", 5) 
                    
                    # Créer un tableau pour la fiche descriptive pour une meilleure mise en page
                    table = document.add_table(rows=9, cols=2)
                    table.style = 'Table Grid'
                    
                    # Fonction utilitaire pour insérer les données dans les cellules
                    def add_data_row(table, row_idx, label, value):
                        table.cell(row_idx, 0).text = f"{label}"
                        table.cell(row_idx, 1).text = str(value) if value is not None else _("N/A")
                        return row_idx + 1

                    # Remplissage du tableau
                    row_idx = 0
                    site = sp.location_subproject_realized
                    row_idx = add_data_row(table, row_idx, _("Date de la prise"), sp.work_completion_date.strftime('%d/%m/%Y') if sp.work_completion_date else _("Non spécifiée"))
                    if site:
                        row_idx = add_data_row(table, row_idx, _("Canton"), f"{site.parent.parent.parent.parent.name} / {site.parent.parent.parent.name} / {site.parent.parent.name} / {site.parent.name}")
                        row_idx = add_data_row(table, row_idx, _("Localité"), f"{site.name}")
                    else:
                        row_idx = add_data_row(table, row_idx, _("Canton"), _("Non spécifiée"))
                        row_idx = add_data_row(table, row_idx, _("Localité"), _("Non spécifiée"))
                    row_idx = add_data_row(table, row_idx, _("Sous-projet"), sp_title)
                    row_idx = add_data_row(table, row_idx, _("Type d’ouvrage"), sp.type_of_subproject)
                    row_idx = add_data_row(table, row_idx, _("Bénéficiaires"), f"{sp.direct_beneficiaries_men or 0} M, {sp.direct_beneficiaries_women or 0} F")
                    row_idx = add_data_row(table, row_idx, _("Statut"), sp.current_status_of_the_site)
                    # row_idx = add_data_row(table, row_idx, _("Commentaires"), sp.comments or "")
                    row_idx = add_data_row(table, row_idx, _("Coût estimé"), f"{separate_with_space(sp.estimated_cost or 0)} XOF")
                    row_idx = add_data_row(table, row_idx, _("Contrat"), f"{separate_with_space(sp.contract_amount_work_companies or 0)} XOF")

                    # --- Section Photos ---
                    document.add_paragraph("\n")


                    document.add_heading("Galerie Photo", 4)
                    photos_list = list(sp.photos)
                    i = 0
                    
                    while i < len(photos_list):
                        
                        # Phase 1: Déterminer le nombre optimal de colonnes
                        current_row_photos = photos_list[i : i + MAX_IMAGES_PER_ROW]
                        num_cols = len(current_row_photos)
                        
                        # Définir la largeur et la cible en fonction du nombre de colonnes
                        if num_cols == 3:
                            target_width = TARGET_WIDTH_3_COLS
                            column_width_in_inches = PAGE_WIDTH_CONTENT.inches / 3
                        elif num_cols == 2:
                            target_width = TARGET_WIDTH_2_COLS
                            column_width_in_inches = PAGE_WIDTH_CONTENT.inches / 2
                        elif num_cols == 1:
                            target_width = PAGE_WIDTH_CONTENT # Pleine largeur
                            column_width_in_inches = PAGE_WIDTH_CONTENT.inches # 100%
                        else:
                            # Ne devrait pas arriver si i < len(photos_list)
                            break 
                            
                        # --- Phase 2: Création du tableau et insertion ---
                        
                        table = document.add_table(rows=1, cols=num_cols)
                        table.autofit = False
                        table.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        
                        for k in range(num_cols):
                            photo_obj = photos_list[i + k]
                            cell = table.cell(0, k)
                            
                            # try:
                            # OBTENTION DU FLUX D'IMAGE CORRIGÉ DIRECTEMENT
                            # Assurez-vous que get_image_data() gère KoBo, S3, et la correction EXIF.
                            image_stream, original_width_px, original_height_px = get_image_data(photo_obj.url, s3_client, bucket_name) 

                            # Convertir la cible Word (Inches) en l'unité interne (EMU)
                            TARGET_WIDTH_EMU = target_width.emu
                            MAX_HEIGHT_EMU = MAX_HEIGHT_CONSTRAINT.emu

                            # Calculer la hauteur que l'image aurait si elle était limitée par la largeur cible
                            # (Pour connaître la hauteur résultante, si la largeur est le facteur limitant)
                            resulting_height_emu = (TARGET_WIDTH_EMU / original_width_px) * original_height_px

                            final_insert_width = target_width
                            final_insert_height = None # Par défaut, on laisse docx calculer la hauteur

                            if resulting_height_emu > MAX_HEIGHT_EMU:
                
                                # Si la hauteur résultante dépasse la contrainte maximale (moitié de la page):
                                # ON LIMITE PAR LA HAUTEUR MAXIMALE
                                
                                final_insert_height = MAX_HEIGHT_CONSTRAINT
                                
                                # On laisse python-docx calculer la largeur, mais on pourrait aussi la calculer:
                                # final_insert_width = Inches((MAX_HEIGHT_EMU / original_height_px) * original_width_px / 914400) 
                                # Cependant, il est plus simple de laisser docx gérer la conservation du ratio
                                
                                final_insert_width = None # Laissez docx calculer la largeur
                            
                            # Insérer l'image en utilisant la largeur ET la hauteur finale (si l'une est nulle, l'autre est conservée en ratio)
                            if final_insert_height is not None:
                                # Le facteur limitant est la hauteur
                                cell.paragraphs[0].add_run().add_picture(
                                    image_stream, 
                                    height=final_insert_height
                                )
                            else:
                                # Le facteur limitant est la largeur (le cas standard de la galerie)
                                cell.paragraphs[0].add_run().add_picture(
                                    image_stream, 
                                    width=final_insert_width
                                )
                            
                            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                            
                            # Ajout de la légende
                            cell.add_paragraph(f"Photo {i + k + 1} : {photo_obj.name}").alignment = WD_ALIGN_PARAGRAPH.CENTER
                            
                            # except Exception as e:
                            #     cell.add_paragraph(f"Erreur d'insertion Photo {i + k + 1}: {e}")
                            
                            # Ajuster la largeur de la colonne (CORRECTION DU TYPE ERROR)
                            table.columns[k].width = Inches(column_width_in_inches)
                        
                        # Passer à la ligne suivante
                        i += num_cols
                        document.add_paragraph("")

                    # document.add_heading("Galerie Photo", 4)
                    # photos_list = list(sp.photos)
                    # i = 0
                    
                    # while i < len(photos_list):
                        
                    #     photo_info = []
                        
                    #     # Phase 1: Déterminer le nombre optimal de colonnes pour les prochaines images
                    #     # On va tenter d'aligner 3 images si elles sont majoritairement "paysage"
                        
                    #     # On vérifie les 3 prochaines images (ou moins)
                    #     current_row_photos = photos_list[i : i + MAX_IMAGES_PER_ROW]
                        
                    #     # Simplification: on tente 3 colonnes par défaut si 3 images sont disponibles, sinon 2.
                        
                    #     if len(current_row_photos) >= 3:
                    #         num_cols = 3
                    #         target_width = TARGET_WIDTH_3_COLS
                    #     else:
                    #         num_cols = len(current_row_photos)
                    #         target_width = TARGET_WIDTH_2_COLS if num_cols == 2 else PAGE_WIDTH_CONTENT # 100% si 1 seule image
                            
                        
                    #     # --- Phase 2: Création du tableau et insertion ---
                        
                    #     table = document.add_table(rows=1, cols=num_cols)
                    #     table.autofit = False
                    #     table.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        
                    #     photos_in_row = 0
                        
                    #     for k in range(num_cols):
                    #         if i + k < len(photos_list):
                                
                    #             photo_obj = photos_list[i + k]
                    #             cell = table.cell(0, k)
                                
                    #             try:
                    #                 # 1. Obtenir le flux corrigé
                    #                 image_stream = get_image_stream_and_reset(photo_obj.url, s3_client, bucket_name)
                                    
                    #                 # 2. Insérer l'image avec la largeur cible
                    #                 # Si c'est une seule colonne, on utilise la largeur totale de la page
                    #                 width_to_use = target_width if num_cols > 1 else PAGE_WIDTH_CONTENT
                                    
                    #                 cell.paragraphs[0].add_run().add_picture(image_stream, width=width_to_use)
                    #                 cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                                    
                    #                 # 3. Ajouter la légende
                    #                 cell.add_paragraph(f"Photo {i + k + 1} : {photo_obj.name}").alignment = WD_ALIGN_PARAGRAPH.CENTER
                    #                 photos_in_row += 1
                                    
                    #             except Exception as e:
                    #                 cell.add_paragraph(f"Erreur d'insertion Photo {i + k + 1}: {e}")
                            
                    #         # Ajuster la largeur de la colonne (essentiel pour l'alignement)
                    #         table.columns[k].width = Inches(PAGE_WIDTH_CONTENT.inches / num_cols)
                        
                    #     # Passer à la ligne suivante
                    #     i += num_cols
                    #     document.add_paragraph("") # Séparateur

                    if len(photos_list) == 0:
                        document.add_paragraph(_("Aucune photo principale trouvée pour ce sous-projet."))

                    document.add_paragraph("")



                    # document.add_heading("Galerie Photo", 5)

                    # photos_list = list(sp.photos)
                    
                    # photos_added = 0

                    # # Définir la largeur maximale des photos
                    # # 3.0 inches est une bonne taille pour 2 photos côte à côte avec des marges standards
                    # TARGET_WIDTH = Inches(3.0)
                    # # Parcourir les photos par paires
                    # for i in range(0, len(photos_list), 3):
                    #     photo1 = photos_list[i]
                    #     photo2 = photos_list[i+1] if i + 1 < len(photos_list) else None
                    #     photo3 = photos_list[i+2] if i + 2 < len(photos_list) else None

                    #     # Crée un tableau avec une ligne et deux colonnes
                    #     table = document.add_table(rows=1, cols=2)
                    #     table.autofit = False # Empêche Word d'ajuster automatiquement
                        
                    #     # Style pour centrer le tableau sur la page (optionnel)
                    #     table.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        
                    #     # --- Photo 1 (Cellule 0) ---
                    #     cell1 = table.cell(0, 0)
                        
                    #     try:
                    #         # Récupérer les données binaires de l'image (via get_image_data, comme défini précédemment)
                    #         image_stream1 = get_image_data(photo1.url, s3_client, bucket_name)
                            
                    #         # 1. Insertion de la photo
                    #         # La largeur force le redimensionnement
                    #         cell1.paragraphs[0].add_run().add_picture(image_stream1, width=TARGET_WIDTH)
                    #         cell1.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                            
                    #         # 2. Ajout de la légende
                    #         cell1.add_paragraph(f"Photo {i + 1} : {photo1.name}").alignment = WD_ALIGN_PARAGRAPH.CENTER
                    #         photos_added += 1
                            
                    #     except Exception as e:
                    #         cell1.add_paragraph(f"Erreur d'insertion Photo {i+1}: {e}")

                    #     # --- Photo 2 (Cellule 1) ---
                    #     if photo2:
                    #         cell2 = table.cell(0, 1)
                    #         try:
                    #             # Récupérer les données binaires de l'image
                    #             image_stream2 = get_image_data(photo2.url, s3_client, bucket_name)
                                
                    #             # 1. Insertion de la photo
                    #             cell2.paragraphs[0].add_run().add_picture(image_stream2, width=TARGET_WIDTH)
                    #             cell2.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                                
                    #             # 2. Ajout de la légende
                    #             cell2.add_paragraph(f"Photo {i + 2} : {photo2.name}").alignment = WD_ALIGN_PARAGRAPH.CENTER
                    #             photos_added += 1
                                
                    #         except Exception as e:
                    #             cell2.add_paragraph(f"Erreur d'insertion Photo {i+2}: {e}")
                        
                    #     # Ajoutez un peu d'espace après le tableau (optionnel)
                    #     document.add_paragraph("")
                        
                    # if photos_added == 0:
                    #     document.add_paragraph(_("Aucune photo principale trouvée pour ce sous-projet."))

                    # document.add_page_break()
        
        document.add_page_break()
            
    # --- Générer la réponse HTTP ---
    filename = f"Album_COSO_{timezone.now().strftime('%Y%m%d')}.docx"
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    response['Content-Disposition'] = f'attachment; filename={filename}'
    document.save(response)
    
    return response