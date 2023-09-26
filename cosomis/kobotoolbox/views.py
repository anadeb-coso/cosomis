from django.shortcuts import render
from django.http import Http404
from django.contrib.auth.decorators import login_required, user_passes_test
from datetime import datetime, date

from kobotoolbox.api_call import get_all
from administrativelevels.models import AdministrativeLevel
from subprojects.models import Subproject, SubprojectImage
from kobotoolbox.form_id_kobo import FORM_ID_KOBO_GMS


@login_required
@user_passes_test(lambda u: bool(u.is_superuser) == True, login_url='/error/denied/')
def kobo(request):
    all_forms = get_all()
    print(all_forms)
    counter = 1
    for a in all_forms['results']:
        village = AdministrativeLevel.objects.filter(name=a['Village'])
        if village:
            village_object = village.first()
            coordinates = a['gps'].split(' ')
            print(counter, village_object.name, a['Village'], coordinates)
            village_object.latitude = coordinates[0]
            village_object.longitude = coordinates[1]
            village_object.save()
        counter = counter + 1
    raise Http404

@login_required
@user_passes_test(lambda u: bool(u.is_superuser) == True, login_url='/error/denied/')
def get_gms_form_reponse(request):
    all_forms = get_all(FORM_ID_KOBO_GMS)
    
    counter = 1
    for a in all_forms['results']:
        if a['type_georeferencement'] == "ouvrages_coso":
            subprojects =  Subproject.objects.filter(number=int(float(a['serial'])))
            if subprojects:
                subproject = subprojects.first()
                coordinates = a['gps'].split(' ')
                subproject.latitude = coordinates[0]
                subproject.longitude = coordinates[1]
                subproject.save()
            counter += 1
        
    print(counter-1)
    print(Subproject.objects.filter(latitude__isnull=True).count())
        
    raise Http404

@login_required
@user_passes_test(lambda u: bool(u.is_superuser) == True, login_url='/error/denied/')
def get_gms_form_reponse_save_images(request):
    all_forms = get_all(FORM_ID_KOBO_GMS)
    
    counter = 1
    for a in all_forms['results']:
        if a['type_georeferencement'] == "ouvrages_coso":
            subprojects =  Subproject.objects.filter(number=int(float(a['serial'])))
            if subprojects:
                subproject = subprojects.first()
                
                c = 0
                for attachment in sorted(a['_attachments'], key=lambda obj: obj.get('id')):
                    imgs = SubprojectImage.objects.filter(url=attachment['download_url'])
                    if imgs.exists():
                        img = imgs.first()
                    else:
                        img = SubprojectImage()
                        img.subproject = subproject
                        img.principal = True if c == 0 else False
                        img.order = subproject.get_all_images().count() + 1

                    img.name = a['description_niveau_travaux']
                    img.url = attachment['download_url']
                    try:
                        if a.get('_submission_time'):
                            _date = a['_submission_time'].split('T')[0]
                            date_split = _date.split('-')
                            img.date_taken =  date(int(date_split[0]), int(date_split[1]), int(date_split[2])) #datetime.strptime(a['_submission_time'], '%Y-%m-%d')
                    except:
                        pass
                    if not img.date_taken:
                        img.date_taken = datetime.now()
                    img.save()
                    c += 1
            counter += 1
            
        
    print(counter-1)
    print(Subproject.objects.filter(latitude__isnull=True).count())
        
    raise Http404