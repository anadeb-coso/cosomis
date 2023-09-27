from django.shortcuts import render
from django.http import Http404
from django.contrib.auth.decorators import login_required, user_passes_test
from datetime import datetime, date

from kobotoolbox.api_call import get_all
from administrativelevels.models import AdministrativeLevel
from subprojects.models import Subproject, SubprojectFile
from kobotoolbox.form_id_kobo import FORM_ID_KOBO_GMS
from kobotoolbox.utils import (
    kobo_util, get_gms_form_reponse_save_images_util, get_gms_form_reponse_util
)


@login_required
@user_passes_test(lambda u: bool(u.is_superuser) == True, login_url='/error/denied/')
def kobo(request):

    kobo_util()

    raise Http404


@login_required
@user_passes_test(lambda u: bool(u.is_superuser) == True, login_url='/error/denied/')
def get_gms_form_reponse(request):
    
    get_gms_form_reponse_util()

    raise Http404


@login_required
@user_passes_test(lambda u: bool(u.is_superuser) == True, login_url='/error/denied/')
def get_gms_form_reponse_save_images(request):

    get_gms_form_reponse_save_images_util()
        
    raise Http404