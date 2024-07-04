from django.contrib import admin
from .models import *

# Register your models here.
admin.site.register([
    Subproject, 
    VulnerableGroup,
    VillagePriority,
    VillageMeeting,
    Component,
    VillageObstacle,
    VillageGoal,
    Financier,
    Project,
    Step,
    SubprojectSector,
    SubprojectType
])