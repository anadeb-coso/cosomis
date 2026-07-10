from django.utils.translation import gettext_lazy as _
# from subprojects.models import SubprojectSector, SubprojectType

SUB_PROJECT_TYPE_DESIGNATION = (
    ('Subproject', _('Subproject')),
    ('Infrastructure', _('Infrastructure'))
)


# SUB_PROJECT_SECTORS = tuple([('', '')],[
#     (o.name_fr, o.name) for o in SubprojectSector.objects.all()
# ])
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
    ('Environnement', _('Environment')), 
    ('Commerce', _('Trade'))
)

# TYPES_OF_SUB_PROJECT = tuple([('', '')],[
#     (o.name_fr, o.name) for o in SubprojectType.objects.all()
# ])
TYPES_OF_SUB_PROJECT = (
    ('', ''), 
    ('Bibliothèques scolaires', _('School libraries')), 
    ('Blocs de latrines dans les établissements scolaires', _('Latrine blocks in schools')), 
    ('Bâtiment Scolaire au CEG', _('School building at CEG')), 
    ('Bâtiment Scolaire au Lycée', _('School building at Lycée')), 
    ('Bâtiment Scolaire au Primaire', _('Primary school building')), 
    ('Bâtiment Scolaire au Pré-scolaire', _('Pre-school school building')), 
    ('CMS', _('Medical-social center')), 
    ("Cantine d'Hôpital", _('Hospital canteen')), 
    ('Centre Communautaire', _('Community Center')),
    ('Clôture (Centre de santé)', _('Fence (Health center)')), 
    ('Clôture (Ecole)', _('Fence (School)')), 
    ("Dalot d'accès à l'école", _('School access dalot')), 
    ('Electrification hors réseau avec lampadaires solaires', _('Off-grid electrification with solar street lamps')), 
    ('Extension réseau électrique', _('Power grid extension')), 
    ('Forage Photovoltaïque (Boisson)', _('Photovoltaic drilling (Beverage)')), 
    ('Forage Photovoltaïque (Centre communautaire)', _('Photovoltaic drilling (Community center)')), 
    ('Forage Photovoltaïque (Ecole)', _('Photovoltaic drilling (School)')), 
    ('Forage Photovoltaïque (Maison des jeunes)', _('Photovoltaic drilling (youth center)')), 
    ('Forage Photovoltaïque (Maraichage)', _('Photovoltaic drilling (market gardening)')), 
    ('Forage Photovoltaïque (Salle de réunion)', _('Photovoltaic drilling (Meeting room)')), 
    ('Incinérateurs médicaux', _('Medical incinerators')), 
    ('Laboratoire', _('Laboratory')), 
    ('Latrine Communautaire', _('Community latrine')), 
    ('Magasin de Stockage', _('Storage Warehouse')), 
    ('Maison des jeunes', _('Youth center')), 
    ('Paillote enseignants', _('Teaching hut')), 
    ('Paillote pour centre de santé', _('Health center hut')), 
    ('Pharmacie', _('Pharmacy')), 
    ('Pistes', _('Track + OF')), 
    ('Pédiatrie', _('Pediatrics')), 
    ('Reboisement', _('Reforestation')), 
    ("Retenue d'eau", _("Water retention")), 
    ('Réhabilitation PMH', _('PMH rehabilitation')),
    ('Réhabilitation PMH en Forage Photovoltaïque (Ecole)', _('Rehabilitation of PMH into a photovoltaic borehole (School)')),
    ('Salle de réunion', _('Meeting room')), 
    ('Terrain de Foot', _('Soccer pitch')), 
    ('USP', _('USP'))
)
# (
#     ('', ''),
#     ('Centre Communautaire', _('Community Center')), 
#     ('Forage Photovoltaïque (Centre communautaire)', _('Photovoltaic drilling (Community center)')), 
#     ('Forage Photovoltaïque (Boisson)', _('Photovoltaic drilling (Beverage)')), 
#     ('Piste/OF', _('Track + OF')), 
#     # ('Batiment Scolaire au Lycée', _('School building at Lycée')), 
#     # ('Batiment Scolaire au CEG', _('School building at CEG')), 
#     # ('Batiment Scolaire au Primaire', _('Primary school building')), 
#     # ('Batiment Scolaire au Pré-scolaire', _('Pre-school school building')),
#     ('Bâtiment Scolaire au Lycée', _('School building at Lycée')), 
#     ('Bâtiment Scolaire au CEG', _('School building at CEG')), 
#     ('Bâtiment Scolaire au Primaire', _('Primary school building')), 
#     ('Bâtiment Scolaire au Pré-scolaire', _('Pre-school school building')),
#     ('Forage Photovoltaïque (Ecole)', _('Photovoltaic drilling (School)')), 
#     ('Magasin De Stockage', _('Storage Warehouse')), 
#     ('CMS', _('Medical-social center')), 
#     ('Extension réseau électrique', _('Power grid extension')), 
#     ("Retenue d'eau", _("Water retention")), 
#     ('Terrain de Foot', _('Soccer pitch')), 
#     ('CHP', _('Prefectural hospital center')), 
#     ('Latrine Communautaire', _('Community latrine')), 
#     ('Forage Photovoltaïque (Latrines)', _('Photovoltaic drilling (Latrines)')), 
#     ('Forage Photovoltaïque (Maraichage)', _('Photovoltaic drilling (market gardening)')), 
#     ('USP', _('USP')), 
#     ('Pharmacie', _('Pharmacy')), 
#     ('Lampadaires solaire', _('Solar street lamps')), 
#     ('Pédiatrie', _('Pediatrics')), 
#     ('Laboratoire', _('Laboratory')), 
#     ('Reboisement', _('Reforestation')), 
#     ('Maison des jeunes', _('Youth center')), 
#     ('Forage Photovoltaïque (Maison des jeunes)', _('Photovoltaic drilling (youth center)')), 
#     ('Salle de réunion', _('Meeting room')), 
#     ('Forage Photovoltaïque (Salle de réunion)', _('Photovoltaic drilling (Meeting room)')),
#     ('Pompe à motricité humaine (PMH)', _('Human-powered pump (H.P.P.)'))
# )


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