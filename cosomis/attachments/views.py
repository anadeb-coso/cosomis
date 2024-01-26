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

from attachments.serializers import SubprojectStepFileSerializer
from rest_framework import serializers
from subprojects.models import SubprojectFile, SubprojectStep, Level
from subprojects.serializers import SubprojectFileSerializer
from usermanager.api.auth.login import CheckUserSerializer


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
                if str(v).isdigit():
                    data[k] = int(v)
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
        print(data)
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.validated_data
        
        file = data['file']
        
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
            if not media_storage.exists(file_path_within_bucket):  # avoid overwriting existing file
                media_storage.save(file_path_within_bucket,file)
                file_url = media_storage.url(file_path_within_bucket)
                
                principal = False
                if len(images) == 0:
                    principal = True

                
                
                if not subproject_file:
                    subproject_file = SubprojectFile()
                    subproject_file.order = data['order']
                    subproject_file.subproject = subproject
                    subproject_file.principal = principal
                    if data['subproject_step']:
                        subproject_file.subproject_step = step_object
                    else:
                        subproject_file.subproject_level = step_object
                    
                    subproject_file.file_type = file.content_type

                subproject_file.url = file_url
                subproject_file.date_taken = datetime.strptime(data['date_taken'], '%Y-%m-%d').date()
                subproject_file.name = step_object.wording
                subproject_file = subproject_file.save_and_return_object()
                
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





class DeleteSubprojectFileAPIView(APIView):
    throttle_classes = ()
    permission_classes = ()
    serializer_class = CheckUserSerializer
    
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data

        try:
            _ = SubprojectFile.objects.get(url=request.data['url']).delete()
            print(_)
            return Response(
                {'success': 'deleted'}, 
                status=status.HTTP_200_OK
            )
        except Exception as exc:
            return Response(
                {'error': exc.__str__()}, 
                status=status.HTTP_404_NOT_FOUND
            )