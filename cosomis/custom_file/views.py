from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from django.views import generic
from django.views import generic
from storages.backends.s3boto3 import S3Boto3Storage
import os
import time
import json
from django.http import HttpResponse


from cosomis.mixins import AJAXRequestMixin, JSONResponseMixin, ModalFormMixin
from custom_file.forms import UploadFileForm
from custom_file.models import CustomerFile
from usermanager.permissions import AdminPermissionRequiredMixin


#Upload
class UploadFileFormView(AJAXRequestMixin, ModalFormMixin, AdminPermissionRequiredMixin, JSONResponseMixin,
                                      generic.FormView):
    form_class = UploadFileForm
    id_form = "upload_file_form"
    title = _('Upload file')
    submit_button = _('Upload')
    form_class_color = 'primary'

    def post(self, request, *args, **kwargs):
        object_id = int(request.POST.get('object_id'))
        class_name = request.POST.get('class_name')
        file = request.FILES.get('file')
        principal = bool(int(request.POST.get("principal")))
        date_taken = request.POST.get('date_taken', None)
        order = int(request.POST.get('order', 0))
        name = request.POST.get('name', None)
        
        if not object_id:
            return HttpResponse(json.dumps({"message": _("We can't find the object id").__str__()}), content_type="application/json")
        

        if object_id and file:
            file_directory_within_bucket = 'proof_of_work/'
            file_path_within_bucket = os.path.join(
                file_directory_within_bucket,
                f'{str(time.time())}-{file.name}'
            )

            media_storage = S3Boto3Storage()

            if not media_storage.exists(file_path_within_bucket):  # avoid overwriting existing file
                media_storage.save(file_path_within_bucket,file)
                file_url = media_storage.url(file_path_within_bucket)
                

                file_object = CustomerFile()
                file_object.url = file_url
                file_object.class_name = class_name
                file_object.object_id = object_id
                file_object.principal = principal
                file_object.order = order
                file_object.date_taken = date_taken
                file_object.name = name
                file_object.save()

                return HttpResponse(json.dumps({"message": _("Registered").__str__(), "ok": True}), content_type="application/json")
            else:
                return HttpResponse(json.dumps({"message": _("We can't save the image").__str__()}), content_type="application/json")
            
        else:
            return HttpResponse(json.dumps({"message": _("Please fill in all fields").__str__()}), content_type="application/json")
        
#And Upload