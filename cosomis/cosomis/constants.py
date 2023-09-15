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