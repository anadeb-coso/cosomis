from django.utils.translation import gettext_lazy as _

SUB_PROJECT_TYPE_DESIGNATION = (
    ('Subproject', _('Subproject')),
    ('Infrastructure', _('Infrastructure'))
)


SUB_PROJECT_SECTORS = (
    ('', ''),
    ('Developpement–a–la–Base', _('Grassroots-development')), 
    ('Eau–Hydraulique', _('Water-Hydraulics')), 
    ('Pistes', _('Tracks')), 
    ('Education', _('Education')), 
    ('Agriculture', _('Agriculture')), 
    ('Sante', _('Health')), 
    ('Energie', _('Energy')), 
    ('Sport–Loisir', _('Sport-Loisir')), 
    ('Assainissement', _('Sanitation')), 
    ('Environnement', _('Environment'))
)

TYPES_OF_SUB_PROJECT = (
    ('', ''),
    ('Centre Communautaire', _('Community Center')), 
    ('Forage Photovoltaïque (Centre communautaire)', _('Photovoltaic drilling (Community center)')), 
    ('Forage Photovoltaïque (Boisson)', _('Photovoltaic drilling (Beverage)')), 
    ('Piste + OF', _('Track + OF')), 
    ('Batiment Scolaire au Lycée', _('School building at Lycée')), 
    ('Batiment Scolaire au CEG', _('School building at CEG')), 
    ('Batiment Scolaire au Primaire', _('Primary school building')), 
    ('Batiment Scolaire au Pré-scolaire', _('Pre-school school building')),
    ('Forage Photovoltaïque (Ecole)', _('Photovoltaic drilling (School)')), 
    ('Magasin De Stockage', _('Storage Warehouse')), 
    ('CMS', _('Medical-social center')), 
    ('Extension réseau électrique', _('Power grid extension')), 
    ("Retenue d'eau", _("Water retention")), 
    ('Terrain de Foot', _('Soccer pitch')), 
    ('CHP', _('Prefectural hospital center')), 
    ('Latrine Communautaire', _('Community latrine')), 
    ('Forage Photovoltaïque (Latrines)', _('Photovoltaic drilling (Latrines)')), 
    ('Forage Photovoltaïque (Maraichage)', _('Photovoltaic drilling (market gardening)')), 
    ('USP', _('USP')), 
    ('Pharmacie', _('Pharmacy')), 
    ('Lampadaires solaire', _('Solar street lamps')), 
    ('Pédiatrie', _('Pediatrics')), 
    ('Laboratoire', _('Laboratory')), 
    ('Reboisement', _('Reforestation')), 
    ('Maison des jeunes', _('Youth center')), 
    ('Forage Photovoltaïque (Maison des jeunes)', _('Photovoltaic drilling (youth center)')), 
    ('Salle de réunion', _('Meeting room')), 
    ('Forage Photovoltaïque (Salle de réunion)', _('Photovoltaic drilling (Meeting room)')),
    ('Pompe à motricité humaine (PMH)', _('Human-powered pump (H.P.P.)'))
)


WORKS_TYPE_OF_SUB_PROJECT = (
    ('Construction', 'Construction'), 
    ('Construction et équipement', 'Construction et équipement'), 
    ('Construction, réhabilitation et équipement', 'Construction, réhabilitation et équipement'), 
    ('Equipement', 'Equipement'), 
    ('Réhabilitation', 'Réhabilitation'), 
    ('Réhabilitation et équipement', 'Réhabilitation et équipement')
)

LEVEL_OF_ACHIEVEMENT_DONATION_CERTIFICATE_OF_SUB_PROJECT = (
    ('', ''),
    ('Aucun', _('None')),
    ('Niveau chef village', _("Village chief level")),
    ('Niveau chef canton', _("Chef canton level")),
    ('Niveau Maire', _("Mayor's level")),
    ('Niveau Juge', _("Judge's level")),
    ('N/A (Ancien site)', _("N/A (Old site)")),
)

SUB_PROJECT_STEP_STANDART = (
    ('not_started', _('Not started')),
    ('in_progress', _('In progress')),
    ('completed', _('Completed'))
)

CURRENT_STATUS_OF_THE_SITE = (
    ("Identifié", _("Identified")),
    ("En cours", _("In progress")),
    ("Achevé", _("Completed")),
    ("Réception technique", ("Technical reception")), 
    ("Réception provisoire", _("Provisional reception")), 
    ("Réception définitive", _("Final reception")),
    ("Arrêt", _("Stop")),
    ("Abandon", _("Abandon")),
)