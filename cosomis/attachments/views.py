import os
from django.conf import settings
import time
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import generics, parsers
from rest_framework.response import Response
from storages.backends.s3boto3 import S3Boto3Storage
from datetime import datetime
from rest_framework import status
from rest_framework.views import APIView
import re
import zipfile
from io import BytesIO
import requests
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse

from attachments.serializers import SubprojectStepFileSerializer, SubprojectStepUrlFileSerializer
from rest_framework import serializers
from subprojects.models import SubprojectFile, SubprojectStep, Level, Subproject
from subprojects.serializers import SubprojectFileSerializer
from usermanager.api.auth.login import CheckUserSerializer
from cosomis.functions import compress_image, compress_file
from cosomis.__init__ import FORM_FIELDS_TO_EXCLUDE


# class UploadIssueAttachmentAPIView(generics.GenericAPIView):
#     serializer_class = TaskFileSerializer
#     parser_classes = (parsers.FormParser, parsers.MultiPartParser)

#     @extend_schema(
#         responses={201: inline_serializer(
#             'AttachmentUpdateStatusSerializer',
#             fields={
#                 'message': serializers.CharField(),
#                 'fileUrl': serializers.CharField(),
#             }
#         )},
#         description=f"Allowed file size less than or equal to {settings.MAX_UPLOAD_SIZE / (1024 * 1024) } MB"
#     )
#     def post(self, request, *args, **kwargs):
#         serializer = self.get_serializer(data=request.data)
#         serializer.is_valid(raise_exception=True)

#         data = serializer.validated_data

#         file_directory_within_bucket = 'proof_of_work/'
#         file_path_within_bucket = os.path.join(
#             file_directory_within_bucket,
#             data['file'].name
#         )

#         media_storage = S3Boto3Storage()

#         if not media_storage.exists(file_path_within_bucket):  # avoid overwriting existing file
#             media_storage.save(file_path_within_bucket, data['file'])
#             file_url = media_storage.url(file_path_within_bucket)
#             return Response({
#                 'message': 'OK',
#                 'fileUrl': file_url,
#             }, status=201)
#         else:
#             return Response({
#                 'message': 'Error: file {filename} already exists at {file_directory} in bucket {bucket_name}'.format(
#                     filename=data['file'].name,
#                     file_directory=file_directory_within_bucket,
#                     bucket_name=media_storage.bucket_name
#                 ),
#             }, status=400)


class UploadSubprojectStepAttachmentAPIView(generics.GenericAPIView):
    serializer_class = SubprojectStepFileSerializer
    parser_classes = (parsers.FormParser, parsers.MultiPartParser)

    @extend_schema(
        responses={201: inline_serializer(
            'AttachmentUpdateStatusSerializer',
            fields={
                'message': serializers.CharField(),
                'fileUrl': serializers.CharField(),
            }
        )},
        description=f"Allowed file size less than or equal to {settings.MAX_UPLOAD_SIZE / (1024 * 1024) } MB"
    )
    
    def convert_objects(self, data):
        for k, v in data.items():
            if v:
                if str(v).replace('.','',1).replace(',','',1).isdigit():
                    data[k] = int(float(v))
                elif k == 'file_type' and v == 'undefined':
                    data[k] = 'application/pdf' if '.pdf' in data['url'] else 'image/*'
                elif v and v in ('null', 'undefined'):
                    data[k] = None
                else:
                    data[k] = v
            else:
                data[k] = v
        return data
            
        
    def post(self, request, *args, **kwargs):
        data = self.convert_objects(request.data)
        
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data
        
        file = data['file']
        
        if file.content_type and 'image' in str(file.content_type).lower():
            file = compress_image(file, 0.7 if file.size > (1 * 1024 * 1024) else (0.5 if file.size > (0.5 * 1024 * 1024) else (file.size/(1024 * 1024))))
        
        if file and (('subproject_step' in data and data['subproject_step']) or ('subproject_level' in data and data['subproject_level'])):     
            
            if 'subproject_step' in data and data['subproject_step']:
                step_object = SubprojectStep.objects.get(id=data['subproject_step'])
                images = step_object.subproject.get_all_images()
                subproject = step_object.subproject
                # subproject_file = SubprojectFile.objects.filter(
                #             subproject_step_id=step_object.id, file_type=file.content_type
                #         ).first()
            else:
                step_object = Level.objects.get(id=data['subproject_level'])
                images = step_object.subproject_step.subproject.get_all_images()
                subproject = step_object.subproject_step.subproject
                # subproject_file = SubprojectFile.objects.filter(
                #             subproject_level_id=step_object.id, file_type=file.content_type
                #         ).first()
                
            subproject_file = None
            if 'id' in data and data['id']:
                subproject_file = SubprojectFile.objects.filter(
                            id=data['id']
                        ).first()
            
            file_directory_within_bucket = 'proof_of_work/'
            file_path_within_bucket = os.path.join(
                file_directory_within_bucket,
                f'{str(time.time())}-{file.name}'
            )
            
            media_storage = S3Boto3Storage()
            
            # if not media_storage.exists(file_path_within_bucket):  # avoid overwriting existing file
            media_storage.save(file_path_within_bucket,file)
            
            file_url = media_storage.url(file_path_within_bucket)
            
            # file_url = file


            principal = False
            if len(images) == 0 and (
                ('file_type' in data and 'image' in data['file_type']) or
                ('content_type' in data and 'image' in data['content_type'])
            ):
                principal = True

            
            
            if not subproject_file:
                subproject_file = SubprojectFile()
                subproject_file.order = data['order']
                subproject_file.subproject = subproject
                subproject_file.principal = principal
                if 'subproject_step' in data and data['subproject_step']:
                    subproject_file.subproject_step = step_object
                else:
                    subproject_file.subproject_level = step_object
                
                subproject_file.file_type = file.content_type

            subproject_file.url = file_url
            subproject_file.review = False
            subproject_file.date_taken = datetime.strptime(data['date_taken'], '%Y-%m-%d').date()
            subproject_file.name = step_object.wording
            subproject_file = subproject_file.save_and_return_object(user=user)
            
            return Response(
                SubprojectFileSerializer(subproject_file).data, 
                status=status.HTTP_200_OK
            )
            # if 'subproject_step' in data and data['subproject_step']:
            #     return Response(
            #         SubprojectFileSerializer(
            #             SubprojectFile.objects.filter(subproject_step_id=step_object.id, file_type=file.content_type),
            #             many=True).data, 
            #         status=status.HTTP_200_OK
            #     )
            # else:
            #     return Response(
            #         SubprojectFileSerializer(
            #             SubprojectFile.objects.filter(subproject_level_id=step_object.id, file_type=file.content_type),
            #             many=True).data, 
            #         status=status.HTTP_200_OK
            #     )
                

        return Response({
            'error': 'Error: file {filename} already exists at {file_directory} in bucket {bucket_name}'.format(
                filename=data['file'].name,
                file_directory=file_directory_within_bucket,
                bucket_name=media_storage.bucket_name
            ),
        }, status=400)
        # return Response({
        #     'error': 'Error: file',
        # }, status=400)



class UploadSubprojectStepUrlAttachmentAPIView(generics.GenericAPIView):
    serializer_class = SubprojectStepUrlFileSerializer
    # parser_classes = (
    #     parsers.FormParser, parsers.MultiPartParser
    #     )

    # @extend_schema(
    #     responses={201: inline_serializer(
    #         'AttachmentUpdateStatusSerializer',
    #         fields={
    #             'message': serializers.CharField(),
    #             'fileUrl': serializers.CharField(),
    #         }
    #     )},
    #     description=f"Allowed file size less than or equal to {settings.MAX_UPLOAD_SIZE / (1024 * 1024) } MB"
    # )
    
    def convert_objects(self, data):
        for key in FORM_FIELDS_TO_EXCLUDE:
            data.pop(key, None)

        for k, v in data.items():
            if v:
                if str(v).isdigit():
                    data[k] = int(v)
                elif str(v).replace('.','',1).replace(',','',1).isdigit():
                    data[k] = int(float(v))
                elif k == 'file_type' and v == 'undefined':
                    data[k] = 'application/pdf' if '.pdf' in data['url'] else 'image/*'
                elif v and v in ('null', 'undefined', ''):
                    data[k] = None
                elif v and v in ('true', '1', 'yes'):
                    data[k] = True
                elif v and v in ('false', '0', 'no'):
                    data[k] = True
                else:
                    data[k] = v
            else:
                data[k] = v
        return data
            
        
    def post(self, request, *args, **kwargs):
        try:
            data = request.data #self.convert_objects(request.data.copy())
            
            if 'file' not in data:
                data['file'] = data['url']
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            user = serializer.validated_data
            
            file = data['file']
            
            if file and (
                ('subproject_step' in data and data['subproject_step']) or 
                ('subproject_level' in data and data['subproject_level']) or 
                ('subproject' in data and data['subproject'])
            ):     
                step_object = None
                if 'subproject_step' in data and data['subproject_step'] and data['subproject_step'] not in (None, 'None', 'null', 0):
                    step_object = SubprojectStep.objects.get(id=data['subproject_step'])
                    images = step_object.subproject.get_all_images()
                    subproject = step_object.subproject
                elif 'subproject_level' in data and data['subproject_level'] and data['subproject_level'] not in (None, 'None', 'null', 0):
                    step_object = Level.objects.get(id=data['subproject_level'])
                    images = step_object.subproject_step.subproject.get_all_images()
                    subproject = step_object.subproject_step.subproject
                else:
                    subproject = Subproject.objects.get(id=data['subproject'])
                    images = subproject.get_all_images()
                    
                subproject_file = None
                if 'id' in data and data['id']:
                    subproject_file = SubprojectFile.objects.filter(
                                id=data['id']
                            ).first()
                
                file_url = file

                if not subproject_file:
                    subproject_file = SubprojectFile.objects.filter(
                        url = file_url,
                        subproject = subproject
                    )
                
                principal = False
                if len(images) == 0 and ( 
                    ('file_type' in data and 'image' in data['file_type']) or
                    ('content_type' in data and 'image' in data['content_type'])
                ):
                    principal = True

                
                
                if not subproject_file:
                    subproject_file = SubprojectFile()
                    subproject_file.order = data['order']
                    subproject_file.subproject = subproject
                    subproject_file.principal = principal
                    if 'subproject_step' in data and data['subproject_step'] and data['subproject_step'] not in (None, 'None', 'null', 0):
                        subproject_file.subproject_step = step_object
                    elif 'subproject_level' in data and data['subproject_level'] and data['subproject_level'] not in (None, 'None', 'null', 0):
                        subproject_file.subproject_level = step_object
                    
                    subproject_file.file_type = data['content_type'] if 'content_type' in data else subproject_file.file_type

                subproject_file.url = file_url
                subproject_file.date_taken = datetime.strptime(data['date_taken'], '%Y-%m-%d').date()
                subproject_step_current = subproject.get_current_subproject_step
                subproject_file.description = data['description'] if 'description' in data else (subproject_step_current.step.wording if subproject_step_current else None)
                subproject_file.name = step_object.wording if step_object else (subproject_file.description if subproject_file.description else subproject.type_of_subproject)
                subproject_file.special = data['special'] if 'special' in data else False
                if 'principal' in data and (not principal and images):
                    if data['principal'] == True:
                        SubprojectFile.objects.filter(subproject=subproject).update(principal=False)
                    subproject_file.principal = data['principal']
                
                try:
                    if hasattr(user, 'no_sql_user'):
                        subproject_file.facilitator_id = user.id
                    else:
                        subproject_file.user = user
                except Exception as exc:
                    pass

                subproject_file = subproject_file.save_and_return_object(user=user)

                
                return Response(
                    SubprojectFileSerializer(subproject_file).data, 
                    status=status.HTTP_200_OK
                )
        except Exception as exc:
            return Response({
                'error': str(exc),
            }, status=400)

        return Response({
            'error': 'Error: file',
        }, status=400)




class DeleteSubprojectFileAPIView(APIView):
    throttle_classes = ()
    permission_classes = ()
    serializer_class = CheckUserSerializer
    
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data

        try:
            _ = SubprojectFile.objects.filter(url=request.data['url'], subproject=request.data['subproject']).delete()
            
            return Response(
                {'success': 'deleted'}, 
                status=status.HTTP_200_OK
            )
        except Exception as exc:
            return Response(
                {'error': exc.__str__()}, 
                status=status.HTTP_404_NOT_FOUND
            )
        



@login_required
def attachment_download(self, adm_id: int, url: str):
    response = requests.get(url)
    if response.status_code == 200:
        content_disposition = response.headers.get("content-disposition")
        filename = url.split("/")[-1]
        if content_disposition is not None:
            try:
                fname = re.findall('filename="(.+)"', content_disposition)

                if len(fname) != 0:
                    filename = fname[0]
            except:
                pass

        response = HttpResponse(
            response.content, content_type=response.headers.get("content-type")
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    else:
        return HttpResponse("Failed to download the file.")


@login_required
def attachment_download_by_id(request, pk: int):
    attachment = SubprojectFile.objects.get(pk=pk)
    url = attachment.url.split("?")[0]
    response = requests.get(url)
    if response.status_code != 200:
        return HttpResponse("Failed to download the file.", status=502)

    filename = url.split("/")[-1]
    content_disposition = response.headers.get("content-disposition")
    if content_disposition is not None:
        try:
            fname = re.findall('filename="(.+)"', content_disposition)
            if len(fname) != 0:
                filename = fname[0]
        except:
            pass

    out = HttpResponse(
        response.content, content_type=response.headers.get("content-type")
    )
    out["Content-Disposition"] = f'attachment; filename="{filename}"'
    return out


@login_required
def attachment_download_zip(self, adm_id: int):
    ids = self.GET.get("ids").split(",")

    buffer = BytesIO()
    zip_file = zipfile.ZipFile(buffer, "w")
    for id in ids:
        url = SubprojectFile.objects.get(id=int(id)).url.split("?")[0]
        response = requests.get(url)
        if response.status_code == 200:
            content_disposition = response.headers.get("content-disposition")
            filename = url.split("/")[-1]
            if content_disposition is not None:
                try:
                    fname = re.findall('filename="(.+)"', content_disposition)

                    if len(fname) != 0:
                        filename = fname[0]
                except:
                    pass
        zip_file.writestr(filename, response.content)

    zip_file.close()

    response = HttpResponse(buffer.getvalue())
    response["Content-Type"] = "application/x-zip-compressed"
    response["Content-Disposition"] = "attachment; filename=attachments.zip"

    return response


@login_required
def gloval_attachment_download_zip(request):
    ids = request.GET.get("ids").split(",")

    buffer = BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        attachments = SubprojectFile.objects.filter(id__in=ids, url__isnull=False)
        for attachment in attachments:
            try:
                url = attachment.url.split("?")[0]
                
                response = requests.get(url)

                if response.status_code == 200:
                    filename = url.split("/")[-1]

                    content_disposition = response.headers.get("content-disposition")

                    if content_disposition:
                        fname = re.findall(r'filename="(.+)"', content_disposition)

                        if fname:
                            filename = fname[0]

                    zip_file.writestr(filename, response.content)
            except Exception:
                pass

    buffer.seek(0)

    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/zip"
    )

    response["Content-Disposition"] = (
        'attachment; filename="attachments.zip"'
    )

    return response