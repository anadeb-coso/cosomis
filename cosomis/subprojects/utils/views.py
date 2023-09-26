from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import generic
from storages.backends.s3boto3 import S3Boto3Storage
import os
from django.utils.translation import gettext_lazy as _
import time

import json
from django.http import HttpResponse

from subprojects.models import Subproject, SubprojectFile, SubprojectStep, Level


class UploadSuprojectImageView(LoginRequiredMixin, generic.View):
    def post(self, request, *args, **kwargs):
        object_id = int(request.POST.get('object_id'))
        file = request.FILES.get('file')
        principal = bool(int(request.POST.get("principal")))
        date_taken = request.POST.get('date_taken')
        order = int(request.POST.get('order'))
        name = request.POST.get('name')
        subproject = None
        _ok = True
        if not object_id:
            return HttpResponse(json.dumps({"message": _("We can't find the sub-projects").__str__()}), content_type="application/json")
        
        subproject = Subproject.objects.get(id=object_id)
        images = subproject.get_all_images()
        for img in images:
            if img.order == order:
                _ok = False
                break
        
        if not _ok:
            return HttpResponse(json.dumps({"message": _("There is already an image that has this order").__str__()}), content_type="application/json")
            
        if object_id and file and date_taken and order and name:
            file_directory_within_bucket = 'proof_of_work/'
            file_path_within_bucket = os.path.join(
                file_directory_within_bucket,
                f'{str(time.time())}-{file.name}'
            )

            media_storage = S3Boto3Storage()

            if not media_storage.exists(file_path_within_bucket):  # avoid overwriting existing file
                media_storage.save(file_path_within_bucket,file)
                file_url = media_storage.url(file_path_within_bucket)
                
                if principal:
                    for img in images:
                        if img.principal:
                            img.principal = False
                            img.save()
                else:
                    if len(images) == 0:
                        principal = True

                image = SubprojectFile()
                image.url = file_url
                image.subproject = subproject
                image.principal = principal
                image.order = order
                image.date_taken = date_taken
                image.name = name
                image.file_type = file.content_type

                image.save()

                return HttpResponse(json.dumps({"message": _("Registered").__str__(), "ok": True}), content_type="application/json")
            else:
                return HttpResponse(json.dumps({"message": _("We can't save the image").__str__()}), content_type="application/json")
            
        else:
            return HttpResponse(json.dumps({"message": _("Please fill in all fields").__str__()}), content_type="application/json")
        



class UpdateSuprojectImageView(LoginRequiredMixin, generic.View):
    def post(self, request, *args, **kwargs):
        object_id = int(request.POST.get('object_id'))
        image_id = int(request.POST.get('image_id'))
        principal = bool(int(request.POST.get("principal")))
        date_taken = request.POST.get('date_taken')
        order = int(request.POST.get('order'))
        name = request.POST.get('name')
        subproject = None
        _ok = True

        image = SubprojectFile.objects.get(id=image_id)
        
        subproject = Subproject.objects.get(id=object_id)
        images = subproject.get_all_images()

        if image.order != order:
            for img in images:
                if img.order == order:
                    _ok = False
                    break
        
        if not _ok:
            return HttpResponse(json.dumps({"message": _("There is already an image that has this order").__str__()}), content_type="application/json")
        
        if order and name:
            if principal:
                for img in images:
                    if img.principal:
                        img.principal = False
                        img.save()
            else:
                if len(images) == 1:
                    principal = True

            image.subproject = subproject

            image.principal = principal
            image.order = order
            if date_taken:
                image.date_taken = date_taken
            image.name = name
            image.save()

            return HttpResponse(json.dumps({"message": _("Registered").__str__(), "ok": True}), content_type="application/json")
           
        else:
            return HttpResponse(json.dumps({"message": _("Please fill in all fields").__str__()}), content_type="application/json")
        
        