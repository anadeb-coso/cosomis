from django.utils.translation import gettext_lazy as _


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
    "Non approuvé": "#c5c5c5", #Darkwhite f-blanche sombre
    "Approuvé": "#ffff00", #Yellow f-jaune
    "DAO lancé": "#ffa500", #Orange f-orange
    "Entreprise sélectionné": "#ff7f50", #Coral f-Corail
    "Contrat signé avec attributaire": "#d2691e", #Chocolate f-chocolat
    "Remise du site": "#8a2be2", #Blueviolet f-Blue violet
    "En cours": "#0000ff", #Blue f-blue
    "Abandon": "#ff0000", #Red f-rouge
    "Interrompu": "#b40219", #Reb-black f-rouge sombre
    "Achevé": "#008b8b", #darkcyan f-cyan sombre
    "Réception technique": "#006400", #Darkgreen f-vert sombre
    "Réception provisoire": "#008200", #Green
    "Remise de l'ouvrage à la communauté": "#00ff00", #Lime f-citron vert
    "Réception définitive": "#32cd32", #LimeGreen
}

SUB_PROJECT_STATUS_COLOR_TRANSLATE = {
    _("Identified"): "#000000", #Black f-noire
    _("Not approved"): "#c5c5c5", #Darkwhite f-blanche sombre
    _("Approved"): "#ffff00", #Yellow f-jaune
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

TYPES_OF_SUB_PROJECT_COLOR = {

    # 'Batiment Scolaire au Pré-scolaire': "#808080", #Gray f-Gris
    # 'Batiment Scolaire au Primaire': "#808080", #Gray f-Gris
    # 'Batiment Scolaire au CEG': "#808080", #Gray f-Gris
    # 'Batiment Scolaire au Lycée': "#808080", #Gray f-
    
    'Bâtiment Scolaire au Pré-scolaire': "#808080", #Gray f-Gris
    'Bâtiment Scolaire au Primaire': "#808080", #Gray f-Gris
    'Bâtiment Scolaire au CEG': "#808080", #Gray f-Gris
    'Bâtiment Scolaire au Lycée': "#808080", #Gray f-Gris
    
    'Forage Photovoltaïque (Boisson)': "#0000ff", #Blue f-blue
    'Forage Photovoltaïque (Centre communautaire)': "#0000ff", #Blue f-blue
    'Forage Photovoltaïque (Ecole)': "#0000ff", #Blue f-blue
    'Forage Photovoltaïque (Latrines)': "#0000ff", #Blue f-blue
    'Forage Photovoltaïque (Maison des jeunes)': "#0000ff", #Blue f-blue
    'Forage Photovoltaïque (Maraichage)': "#0000ff", #Blue f-blue
    'Forage Photovoltaïque (Salle de réunion)': "#0000ff", #Blue f-blue
    "Pompe à motricité humaine (PMH)": "#1e90ff", #DodgerBlue f-Bleu cagnard
    "Retenue d'eau": "#601ee0", #Blueviolet f-Blue violet

    'CMS': "#008200", #Green f-vert
    'CHP': "#32cd32", #LimeGreen f-Vert de chaux
    'USP': "#3b7024", #DarkOliveGreen f-Vert olive foncé
    'Pharmacie': "#006400", #Darkgreen f-vert sombre
    'Pédiatrie': "#92d492", #DarkSeaGreen f-Vert de mer foncé
    'Laboratoire': "#00ff00", #Lime f-citron vert

    
    'Extension réseau électrique': "#ffff00", #Yellow f-jaune
    'Lampadaires solaire': "#9c9c14", #DarkYellow f-jaune sombre

    'Centre Communautaire': "#ffa500", #Orange f-orange
    'Salle de réunion': "#a75e06", #DarkOrange f-Orange sombre

    'Maison des jeunes': "#ff0000", #Red f-rouge
    'Terrain de Foot': "#7a1212", #DarkRed f-rouge sombre

    'Magasin De Stockage': "#800080", #Purple f-Violet
    
    'Reboisement': "#faf0e6", #Linen f-Lin

    'Piste/OF': "#000000", #Black f-noire

    'Latrine Communautaire': "#191970", #MidNightBlue f-Blue sombre
}


TYPES_OF_STRUCTURE_COLOR = {
    'Bâtiment Scolaire': "#808080", #Gray f-Gris
    
    'Forage Photovoltaïque': "#0000ff", #Blue f-blue
    "Pompe à motricité humaine (PMH)": "#1e90ff", #DodgerBlue f-Bleu cagnard
    "Retenue d'eau": "#601ee0", #Blueviolet f-Blue violet
    
    'CMS': "#008200", #Green f-vert
    'CHP': "#32cd32", #LimeGreen f-Vert de chaux
    'USP': "#3b7024", #DarkOliveGreen f-Vert olive foncé
    'Pharmacie': "#006400", #Darkgreen f-vert sombre
    'Pédiatrie': "#92d492", #DarkSeaGreen f-Vert de mer foncé
    'Laboratoire': "#00ff00", #Lime f-citron vert
    
    'Extension réseau électrique': "#ffff00", #Yellow f-jaune
    'Lampadaires solaire': "#9c9c14", #DarkYellow f-jaune sombre

    'Centre Communautaire': "#ffa500", #Orange f-orange
    'Salle de réunion': "#a75e06", #DarkOrange f-Orange sombre
    'Maison des jeunes': "#ff0000", #Red f-rouge
    'Terrain de Foot': "#7a1212", #DarkRed f-rouge sombre

    'Magasin De Stockage': "#800080", #Purple f-Violet
    'Reboisement': "#faf0e6", #Linen f-Lin

    'Piste/OF': "#000000", #Black f-noire
    
    'Latrine Communautaire': "#191970", #MidNightBlue f-Blue sombre
    'Latrine Scolaire': "#2f4f4f", #darkSlategray f-Gris sombre
    
    'Clôture Scolaire': "#000000",
    'Clôture Pédiatrie': "#000000",
    
}

CURRENCY_UNIT = 'FCFA' #currency unit global variable