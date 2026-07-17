from django.utils.translation import gettext_lazy as _
# from subprojects.models import SubprojectSector, SubprojectType


OBSTACLES_FOCUS_GROUP = [
    "Obstacles of the farmers and breeders group", "Barriers of the women's group",
    "Barriers for Youth", "Barriers for ethnic minority groups"
]
GOALS_FOCUS_GROUP = [
    "Vision for the focus group of Farmers and breeders", "Vision for the women's focus group",
    "Vision for the youth focus group", "Vision for the focus group of ethnic minority groups"
]

IGNORES = (' ', '  ', 'Nean', 'Neant', 'O', 'Oo', 'Ooo', 'X', 'Xx', 'Xxx', 'Non', '-', '0', '00', '000', 'Pas De Minorite', "Pas D'", 'Ras', 'Aucun', 'Pas', "Il N'Y A Pas", ' N Existe Pas', "N'Existe Pas", "Il N'Yapas De Groupe", "Il N'Y a pas De Groupe")
PEULS = ('Peulh', 'Peuhl', 'Paulh', 'Pauhl', 'Peuls', 'Peul', 'Peul...', 'Peul.', 'Pheul', 'Les Peulhs', 'Les Peulh', 'Peulhs', 'Les Peuhl', 'Les Peuhls', 'Les Pleuh')


SUB_PROJECT_STATUS_COLOR = {
    "Identifié": "#000000", #Black f-noire
    # "Non approuvé": "#c5c5c5", #Darkwhite f-blanche sombre
    "Non approuvé par le CORA": "#c5c5c5", #Darkwhite f-blanche sombre
    # "Approuvé": "#939301", #Olive f-Olive
    "Approuvé par le CORA": "#939301", #Olive f-Olive
    "DAO lancé": "#ffa500", #Orange f-orange
    # "Entreprise sélectionné": "#ff7f50", #Coral f-Corail
    # "Entreprise sélectionnée": "#ff7f50", #Coral f-Corail
    "Entreprise retenue": "#ff7f50", #Coral f-Corail
    "Contrat signé avec attributaire": "#d2691e", #Chocolate f-chocolat
    "Remise du site": "#8a2be2", #Blueviolet f-Blue violet
    "En cours": "#0000ff", #Blue f-blue
    "Remise en cours": "#0000ff", #Blue f-blue
    "Abandon": "#ff0000", #Red f-rouge
    "Interrompu": "#b40219", #Reb-black f-rouge sombre
    "Achevé": "#008b8b", #darkcyan f-cyan sombre
    "Réception technique": "#006400", #Darkgreen f-vert sombre
    "Réception provisoire": "#008200", #Green
    "Remise de l'ouvrage à la communauté": "#00ff00", #Lime f-citron vert
    "Réception définitive": "#32cd32", #LimeGreen
}

SUB_PROJECT_STATUS_COLOR_TRANSLATE = {
    _("Not start"): "#000000", #Black f-noire
    _("Identified"): "#000000", #Black f-noire
    _("Not approved"): "#c5c5c5", #Darkwhite f-blanche sombre
    _("Approved"): "#939301", #Olive f-Olive
    _("DAO launched"): "#ffa500", #Orange f-orange
    _("Company selected"): "#ff7f50", #Coral f-Corail
    _("Contract signed with contractor"): "#d2691e", #Chocolate f-chocolat
    _("Site handover"): "#8a2be2", #Blueviolet f-Blue violet
    _("In progress"): "#0000ff", #Blue f-blue
    _("Abandon"): "#ff0000", #Red f-rouge
    _("Interrupted"): "#b40219", #Reb-black f-rouge sombre
    _("Completed"): "#008b8b", #darkcyan f-cyan sombre
    _("Technical reception"): "#006400", #Darkgreen f-vert sombre
    _("Provisional reception"): "#008200", #Green
    _("Handover to the community"): "#00ff00", #Lime f-citron vert
    _("Final reception"): "#32cd32", #LimeGreen
}

# TYPES_OF_SUB_PROJECT_COLOR = dict([('', '')],[
#     (o.name_fr, o.color) for o in SubprojectType.objects.all()
# ])
# TYPES_OF_SUB_PROJECT_COLOR = {
#     'Bibliothèques scolaires': '#808080', #Gray f-Gris
#     'Blocs de latrines dans les établissements scolaires': '#808080', #Gray f-Gris
#     'Bâtiment Scolaire au CEG': '#808080', #Gray f-Gris
#     'Bâtiment Scolaire au Lycée': '#808080', #Gray f-Gris
#     'Bâtiment Scolaire au Primaire': '#808080', #Gray f-Gris
#     'Bâtiment Scolaire au Pré-scolaire': '#808080', #Gray f-Gris
#     'CMS': '#008200', #Green f-vert
#     "Cantine d'Hôpital": "#008200", #Green f-vert
#     'Centre Communautaire': "#ffa500", #Orange f-orange
#     'Clôture (Centre de santé)': "#ffa500", #Orange f-orange
#     'Clôture (Ecole)': '#808080', #Gray f-Gris
#     "Dalot d'accès à l'école": '#808080', #Gray f-Gris
#     'Electrification hors réseau avec lampadaires solaires': "#9c9c14", #DarkYellow f-jaune sombre
#     'Extension réseau électrique': "#939301", #Olive f-Olive
#     'Forage Photovoltaïque (Boisson)': '#0000ff', #Blue f-blue
#     'Forage Photovoltaïque (Centre communautaire)': '#0000ff',  #Blue f-blue
#     'Forage Photovoltaïque (Ecole)': '#0000ff',  #Blue f-blue
#     'Forage Photovoltaïque (Maison des jeunes)': '#0000ff',  #Blue f-blue
#     'Forage Photovoltaïque (Maraichage)': '#0000ff',  #Blue f-blue
#     'Forage Photovoltaïque (Salle de réunion)': '#0000ff',  #Blue f-blue
#     'Incinérateurs médicaux': "#008200", #Green f-vert
#     'Laboratoire': "#00ff00", #Lime f-citron vert
#     'Latrine Communautaire': "#191970", #MidNightBlue f-Blue sombre
#     'Magasin de Stockage': "#800080", #Purple f-Violet
#     'Maison des jeunes': "#ff0000", #Red f-rouge
#     'Paillote enseignants': '#808080', #Gray f-Gris
#     'Paillote pour centre de santé': "#008200", #Green f-vert
#     'Pharmacie': "#006400", #Darkgreen f-vert sombre
#     'Pistes': "#000000", #Black f-noire
#     'Pédiatrie': "#92d492", #DarkSeaGreen f-Vert de mer foncé
#     'Reboisement': "#deb887", #Burlywood f-Bois massif
#     "Retenue d'eau": '#601ee0', #Blueviolet f-Blue violet
#     'Réhabilitation PMH': '#1e90ff', #DodgerBlue f-Bleu cagnard
#     'Réhabilitation PMH en Forage Photovoltaïque (Ecole)': '#1e90ff', #DodgerBlue f-Bleu cagnard
#     'Salle de réunion': "#a75e06", #DarkOrange f-Orange sombre
#     'Terrain de Foot': "#7a1212", #DarkRed f-rouge sombre
#     'USP': "#3b7024", #DarkOliveGreen f-Vert olive foncé
# }

TYPES_OF_SUB_PROJECT_COLOR = {
    'Abri pour petits ruminants': '#800080', 
    'Abri pour volailles': '#800080', 
    'Abri pour volailles et petits ruminants': '#800080', 
    'Aménagement de pistes': '#000000', 
    'Bâtiment Scolaire au CEG': '#808080', 
    'Bâtiment Scolaire au Pré-scolaire': '#808080', 
    'Bâtiment Scolaire au Primaire': '#808080', 
    'Bâtiments scolaires au premier cycle du secondaire (CEG)': '#808080', 
    'Bâtiments scolaires au préscolaire': '#808080', 
    'Bâtiments scolaires au primaire': '#808080', 
    'Bâtiments scolaires au second cycle du secondaire (Lycée)': '#808080', 
    'Bibliothèques scolaires': '#808080', 
    'Bloc administratif': '#808080', 
    'Blocs de latrines dans les établissements scolaires': '#808080', 
    'Blocs de latrines dans les marchés': '#ffa500', 
    'Boucherie': '#ffa500', 
    'Boutiques': '#ffa500',
    "Cantine d'Hôpital": '#008200', 
    'Centre artisanal': '#ffa500', 
    'Centre Communautaire': '#ffa500', 
    'Centre culturel': '#ffa500', 
    'Centre Médico-Social (CMS)': '#008200', 
    'Clôture de centre communautaire': '#ffa500', 
    'Clôture de Centre de santé': '#008200', 
    'Clôture/Façade de marché': '#ffa500', 
    'Clôtures d’école': '#808080', 
    'Dépotoir': '#ff0000', 
    'Dortoir': '#ffa500', 
    'Electrification hors réseau avec des lampadaires solaires': '#9c9c14', 
    'Electrification hors réseau avec lampadaires solaires': '#9c9c14',
    "Extension du réseau d'eau (TDE)": '#9c9c14', 
    'Extension du réseau électrique': '#9c9c14', 
    'Extension réseau électrique': '#9c9c14', 
    'Forage Photovoltaïque (Boisson)': '#0000ff', 
    'Forage Photovoltaïque (Centre communautaire)': '#0000ff', 
    'Forage Photovoltaïque (Ecole)': '#0000ff', 
    'Forage Photovoltaïque (Maison des jeunes)': '#0000ff', 
    'Forage Photovoltaïque (Maraichage)': '#0000ff', 
    'Forage Photovoltaïque (Salle de réunion)': '#0000ff', 
    'Forages photovoltaïques dans les communautés pour eau de boisson': '#0000ff', 
    'Forages photovoltaïques dans les établissements scolaires': '#0000ff', 
    'Forages photovoltaïques dans les marchés pour eau de boisson': '#0000ff', 
    'Forages photovoltaïques pour les activités maraîchères': '#0000ff', 
    'Hangar de Gare routière': '#ffa500', 
    'Hangar de type cantonal': '#ffa500', 
    'Incinérateurs médicaux': '#008200', 
    'Laboratoire': '#008200', 
    'Latrine Communautaire': '#ffa500',
    "Local de stockage d'oxygène médical": '#008200', 
    'Magasin': '#ffa500', 
    'Magasin De Stockage': '#ffa500', 
    'Maison des jeunes': '#ffa500', 
    'Marché à bétail': '#ffa500', 
    'Maternité': '#008200',
    "Ouvrage d'assainissement": '#008200',
    "Ouvrage de franchissement au niveau de l'établissment scolaire": '#000000', 
    'Ouvrage de franchissement au niveau du magasin de stockage': '#000000', 
    'Paillote enseignants': '#808080', 
    'Paillote pour centre de santé': '#008200', 
    'Parking auto/moto': '#ffa500', 
    'Parking moto': '#ffa500', 
    'Pédiatrie': '#008200', 
    'Pharmacie': '#008200', 
    'Pistes': '#000000', 
    'PMH à réhabiliter/transformer en Forages photovoltaïques dans les établissements scolaires': '#0000ff', 
    'Portes de marché': '#ffa500', 
    'Reboisement': '#9c9c14', 
    'Réhabilitation du marché moderne de Mango': '#ffa500', 
    'Réhabilitation PMH': '#0000ff', 
    'Réhabilitation PMH en Forage Photovoltaïque (Ecole)': '#0000ff',
    "Retenue d'eau": '#0000ff',
    "Retenues d'eau": '#0000ff', 
    'Salle de réunion': '#ffa500', 
    'Salle informatique': '#00ff00', 
    'Terrain de Foot': '#00ff00', 
    'Unité de soins périphériques (USP)': '#008200', 
    'Vestiaires de Terrain de Foot': '#00ff00'
}

# {

#     # 'Batiment Scolaire au Pré-scolaire': "#808080", #Gray f-Gris
#     # 'Batiment Scolaire au Primaire': "#808080", #Gray f-Gris
#     # 'Batiment Scolaire au CEG': "#808080", #Gray f-Gris
#     # 'Batiment Scolaire au Lycée': "#808080", #Gray f-
    
#     'Bâtiment Scolaire au Pré-scolaire': "#808080", #Gray f-Gris
#     'Bâtiment Scolaire au Primaire': "#808080", #Gray f-Gris
#     'Bâtiment Scolaire au CEG': "#808080", #Gray f-Gris
#     'Bâtiment Scolaire au Lycée': "#808080", #Gray f-Gris
    
#     'Forage Photovoltaïque (Boisson)': "#0000ff", #Blue f-blue
#     'Forage Photovoltaïque (Centre communautaire)': "#0000ff", #Blue f-blue
#     'Forage Photovoltaïque (Ecole)': "#0000ff", #Blue f-blue
#     'Forage Photovoltaïque (Latrines)': "#0000ff", #Blue f-blue
#     'Forage Photovoltaïque (Maison des jeunes)': "#0000ff", #Blue f-blue
#     'Forage Photovoltaïque (Maraichage)': "#0000ff", #Blue f-blue
#     'Forage Photovoltaïque (Salle de réunion)': "#0000ff", #Blue f-blue
#     "Pompe à motricité humaine (PMH)": "#1e90ff", #DodgerBlue f-Bleu cagnard
#     "Retenue d'eau": "#601ee0", #Blueviolet f-Blue violet

#     'CMS': "#008200", #Green f-vert
#     'CHP': "#32cd32", #LimeGreen f-Vert de chaux
#     'USP': "#3b7024", #DarkOliveGreen f-Vert olive foncé
#     'Pharmacie': "#006400", #Darkgreen f-vert sombre
#     'Pédiatrie': "#92d492", #DarkSeaGreen f-Vert de mer foncé
#     'Laboratoire': "#00ff00", #Lime f-citron vert

    
#     'Extension réseau électrique': "#939301", #Olive f-Olive
#     'Lampadaires solaire': "#9c9c14", #DarkYellow f-jaune sombre

#     'Centre Communautaire': "#ffa500", #Orange f-orange
#     'Salle de réunion': "#a75e06", #DarkOrange f-Orange sombre

#     'Maison des jeunes': "#ff0000", #Red f-rouge
#     'Terrain de Foot': "#7a1212", #DarkRed f-rouge sombre

#     'Magasin De Stockage': "#800080", #Purple f-Violet
    
#     'Reboisement': "#deb887", #Burlywood f-Bois massif

#     'Piste/OF': "#000000", #Black f-noire

#     'Latrine Communautaire': "#191970", #MidNightBlue f-Blue sombre
# }



TYPES_OF_STRUCTURE_COLOR = {
    'Bibliothèques scolaires': '#808080', #Gray f-Gris
    'Blocs de latrines dans les établissements scolaires': '#808080', #Gray f-Gris
    'Bâtiment Scolaire au CEG': '#808080', #Gray f-Gris
    'Bâtiment Scolaire au Lycée': '#808080', #Gray f-Gris
    'Bâtiment Scolaire au Primaire': '#808080', #Gray f-Gris
    'Bâtiment Scolaire au Pré-scolaire': '#808080', #Gray f-Gris
    'CMS': '#008200', #Green f-vert
    "Cantine d'Hôpital": "#008200", #Green f-vert
    'Centre Communautaire': "#ffa500", #Orange f-orange
    'Clôture (Centre de santé)': "#ffa500", #Orange f-orange
    'Clôture (Ecole)': '#808080', #Gray f-Gris
    "Dalot d'accès à l'école": '#808080', #Gray f-Gris
    'Electrification hors réseau avec lampadaires solaires': "#9c9c14", #DarkYellow f-jaune sombre
    'Extension réseau électrique': "#939301", #Olive f-Olive
    'Forage Photovoltaïque (Boisson)': '#0000ff', #Blue f-blue
    'Forage Photovoltaïque (Centre communautaire)': '#0000ff',  #Blue f-blue
    'Forage Photovoltaïque (Ecole)': '#0000ff',  #Blue f-blue
    'Forage Photovoltaïque (Maison des jeunes)': '#0000ff',  #Blue f-blue
    'Forage Photovoltaïque (Maraichage)': '#0000ff',  #Blue f-blue
    'Forage Photovoltaïque (Salle de réunion)': '#0000ff',  #Blue f-blue
    'Incinérateurs médicaux': "#008200", #Green f-vert
    'Laboratoire': "#00ff00", #Lime f-citron vert
    'Latrine Communautaire': "#191970", #MidNightBlue f-Blue sombre
    'Magasin de Stockage': "#800080", #Purple f-Violet
    'Maison des jeunes': "#ff0000", #Red f-rouge
    'Paillote enseignants': '#808080', #Gray f-Gris
    'Paillote pour centre de santé': "#008200", #Green f-vert
    'Pharmacie': "#006400", #Darkgreen f-vert sombre
    'Pistes': "#000000", #Black f-noire
    'Pédiatrie': "#92d492", #DarkSeaGreen f-Vert de mer foncé
    'Reboisement': "#deb887", #Burlywood f-Bois massif
    "Retenue d'eau": '#601ee0', #Blueviolet f-Blue violet
    'Réhabilitation PMH': '#1e90ff', #DodgerBlue f-Bleu cagnard
    'Réhabilitation PMH en Forage Photovoltaïque (Ecole)': '#1e90ff', #DodgerBlue f-Bleu cagnard
    'Salle de réunion': "#a75e06", #DarkOrange f-Orange sombre
    'Terrain de Foot': "#7a1212", #DarkRed f-rouge sombre
    'USP': "#3b7024", #DarkOliveGreen f-Vert olive foncé
}
# {
#     'Bâtiment Scolaire': "#808080", #Gray f-Gris
    
#     'Forage Photovoltaïque': "#0000ff", #Blue f-blue
#     "Pompe à motricité humaine (PMH)": "#1e90ff", #DodgerBlue f-Bleu cagnard
#     "Retenue d'eau": "#601ee0", #Blueviolet f-Blue violet

#     'santé': "#008200", #Green f-vert
#     'Hôpital': "#008200", #Green f-vert
#     'CMS': "#008200", #Green f-vert
#     'CHP': "#32cd32", #LimeGreen f-Vert de chaux
#     'USP': "#3b7024", #DarkOliveGreen f-Vert olive foncé
#     'Pharmacie': "#006400", #Darkgreen f-vert sombre
#     'Pédiatrie': "#92d492", #DarkSeaGreen f-Vert de mer foncé
#     'Laboratoire': "#00ff00", #Lime f-citron vert
    
#     'Extension réseau électrique': "#939301", #Olive f-Olive
#     'Lampadaires solaire': "#9c9c14", #DarkYellow f-jaune sombre

#     'Centre Communautaire': "#ffa500", #Orange f-orange
#     'Salle de réunion': "#a75e06", #DarkOrange f-Orange sombre
#     'Maison des jeunes': "#ff0000", #Red f-rouge
#     'Terrain de Foot': "#7a1212", #DarkRed f-rouge sombre

#     'Magasin De Stockage': "#800080", #Purple f-Violet
#     'Reboisement': "#deb887", #Burlywood f-Bois massif

#     'Piste': "#000000", #Black f-noire
    
#     'Latrine Communautaire': "#191970", #MidNightBlue f-Blue sombre
#     'Latrine Scolaire': "#2f4f4f", #darkSlategray f-Gris sombre
    
#     'Clôture Scolaire': "#000000",
#     'Clôture Pédiatrie': "#000000",
    
# }






OTHER_STRUCUTURES = [
    'Latrine Scolaire', 'Clôture Pédiatrie', 'Clôture Scolaire'
]

# SUB_PROJECT_SECTORS_COLOR = dict([('', '')],[
#     (o.name_fr, o.color) for o in SubprojectSector.objects.all()
# ])
SUB_PROJECT_SECTORS_COLOR = {
    'Developpement–a–la–Base': "#ffa500", #Orange f-orange
    'Eau–Hydraulique': '#0000ff', #Blue f-blue
    'Pistes': '#000000', #Black f-noire
    'Education': '#808080', #Gray f-Gris
    'Agriculture': "#601ee0", #Blueviolet f-Blue violet
    'Sante': '#008200', #Green f-vert
    'Energie': '#939301', #Olive f-Olive
    'Sport–Loisir': "#7a1212", #DarkRed f-rouge sombre
    'Assainissement': "#191970", #MidNightBlue f-Blue sombre
    'Environnement': "#deb887", #Burlywood f-Bois massif
    'Commerce': "#29294d", #f-blue sombre
}

FINANCING_COLOR = {
    'Allocation': '#0000ff', #Blue f-blue
    'Residual': '#000000', #Black f-noire
    'Spent': '#008200', #Green f-vert
    'Estimate': "#ff0000", #Red f-Rouge
    
    'Allocation': '#0000ff', #Blue f-blue
    'Reliquat': '#000000', #Black f-noire
    'Dépensés': '#008200', #Green f-vert
    'Estimé': "#ff0000", #Red f-Rouge
}

CURRENCY_UNIT = 'FCFA' #currency unit global variable

IDENTIFIED_RANKING = 1
NOT_APPROVED_BY_CORA_RANKING = 2
APPROVED_BY_CORA_RANKING = 3
DAO_LAUNCHED_RANKING = 4
SELECTED_COMPANY_RANKING = 5
FIRST_CONTRACT_RANKING = 6
CONTRACT_TERMINATED_RANKING = 6.1
DAO_RELAUNCHED_RANKING = 6.2
OTHERS_CONTRACT_RANKING = 6.3
SITE_DISCOUNT_RANKING = 7
ANOTHER_SITE_HANDED_OVER_FOR_CONSTRUCTION_RANKING = 7.1
IN_PROGRESS_RANKING = 8
ABANDONED_RANKING = 9
INTERRUPTED_RANKING = 10
RESUME_IN_PROGRESS_RANKING = 10.1
COMPLETED_RANKING = 11
RECEPTION_TECHNICAL_RANKING = 12
PROVISIONAL_RECEPTION_RANKING = 13
HANDOVER_TO_COMMUNITY_RANKING = 14
FINAL_RECEPTION_RANKING = 15

IDENTIFIED_RANKING_LIST = [IDENTIFIED_RANKING]
STRUCTURE_IN_PROGRESS_RANKING_LIST = [IN_PROGRESS_RANKING, RESUME_IN_PROGRESS_RANKING]
STRUCTURE_COMPLETED_RANKING_LIST = [COMPLETED_RANKING, RECEPTION_TECHNICAL_RANKING, PROVISIONAL_RECEPTION_RANKING, HANDOVER_TO_COMMUNITY_RANKING, FINAL_RECEPTION_RANKING]
PROBLEMS_STEPS_RANKING_LIST = [NOT_APPROVED_BY_CORA_RANKING, DAO_RELAUNCHED_RANKING, CONTRACT_TERMINATED_RANKING, ABANDONED_RANKING, INTERRUPTED_RANKING]
DAO_LAUNCHED_RANKING_LIST = [DAO_LAUNCHED_RANKING, DAO_RELAUNCHED_RANKING]
CONTRACT_RANKING_LIST = [FIRST_CONTRACT_RANKING, OTHERS_CONTRACT_RANKING]

STRUCTURE_NOT_START_STATUS = ['Identifié']
NOT_APPROVED_BY_CORA_LIST = ['Non approuvé par le CORA']
STRUCTURE_IN_PROGRESS_STATUS = ['En cours', 'Remise en cours']
ABANDONED_LIST = ['Abandon']
INTERRUPTED_LIST = ['Arrêt', 'Interrompu']
CONTRACT_TERMINATED_LIST = ['Contrat résilié']
STRUCTURE_COMPLETED_STATUS = ["Achevé", "Réception technique", "Réception provisoire", "Remise de l'ouvrage à la communauté", "Réception définitive"]
STRUCTURE_COMPLETED_ONLY_STATUS = ["Achevé"]
STRUCTURE_PROVISIONAL_ACCEPTANCE_STATUS = ["Réception provisoire", "Remise de l'ouvrage à la communauté", "Réception définitive"]
STRUCTURE_FINAL_ACCEPTANCE_STATUS = ["Réception définitive"]
STRUCTURE_IN_PROGRESS_ALL_STATUS = STRUCTURE_IN_PROGRESS_STATUS+['Superstructure en cours']
STRUCTURE_COMPLETED_ALL_STATUS = STRUCTURE_COMPLETED_STATUS+['provisoire', 'réception', 'réceptionné', 'terminée', 'Superstructure construite'] #, 'superstructure'


IMAGE_EXTENSIONS = [
    # Formats courants
    ".jpg", ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".tif", ".tiff",
    ".webp",

    # Formats vectoriels
    ".svg", ".svgz",

    # Formats professionnels / impression
    ".psd",
    ".ai",
    ".eps",
    # ".pdf",

    # Formats photo / RAW (appareils photo)
    ".raw",
    ".arw",   # Sony
    ".cr2", ".cr3",  # Canon
    ".nef",  # Nikon
    ".orf",  # Olympus
    ".rw2",  # Panasonic
    ".dng",  # Adobe / universel
    ".sr2",

    # Formats anciens ou spécialisés
    ".ico",
    ".cur",
    ".pcx",
    ".tga",
    ".dds",
    ".exr",
    ".hdr",
    ".jp2", ".j2k",
    ".pbm", ".pgm", ".ppm",
    ".xbm", ".xpm",

    # Autres
    ".heic", ".heif",  # Apple / iOS
    ".avif",

    # Kobo Collect files
    '.kobotoolbox'
]
