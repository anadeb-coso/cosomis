import re
import zipfile
import requests
from io import BytesIO
import json
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.response import Response
from rest_framework import permissions
from rest_framework.views import APIView
from django.db.models import Q, Case, When, Value, IntegerField,  QuerySet, Sum, Count, Subquery, F, Prefetch
from django.urls import reverse
from django.shortcuts import redirect
from urllib.parse import urlencode
from django.core.paginator import Paginator

from cosomis.mixins import PageMixin
from subprojects.models import SubprojectFile, FileComment, Subproject
from subprojects.serializers import SubprojectFileSerializer, FileCommentsSerializer
from cosomis.constants import IMAGE_EXTENSIONS


class FilesListView(PageMixin, LoginRequiredMixin, ListView):
    template_name = "attachments/attachments.html"
    context_object_name = "attachments"
    title = _("Gallery")
    active_level1 = 'infrastructures'
    model = SubprojectFile

    def get_context_data(self, **kwargs):
        context = super(FilesListView, self).get_context_data(**kwargs)
        context['hide_content_header'] = True
        query_params: dict = self.request.GET

        query_strings_raw = query_params.copy()
        if 'type' not in query_strings_raw:
            query_strings_raw['type'] = 'Photo'
        context["query_strings_raw"] = query_strings_raw
        context["query_strings_raw"].pop("page", None)
        # validated = (
        #     True if context["query_strings_raw"]['validated_status'] == 'Validated' else (
        #         False if context["query_strings_raw"]['validated_status'] == 'Invalidated' else None
        #     )
        # ) if 'validated_status' in context["query_strings_raw"] else ''
        # babylong_query_params_list = [key + '=' + value for key, value in context["query_strings_raw"].items()]
        # if babylong_query_params_list:
        #     context["babylong_query_params"] = '&' + '&'.join(babylong_query_params_list)

        context['subproject'] = Subproject.objects.get(id=self.kwargs['subproject_id'])

        context['file_ids'] = ",".join(
            map(str, self.get_queryset().values_list('id', flat=True))
        )

        return context
    
    def get_template_names(self, *args, **kwargs):
        if self.request.htmx:
            return "attachments/_grid.html"
        else:
            return self.template_name
        
    def get_queryset(self):
        queryset = super().get_queryset().filter(subproject_id=self.kwargs['subproject_id'])

        query_params: dict = self.request.GET

        query_strings_raw = query_params.copy()
        query_strings_raw.pop("page", None)
        validated = (
            True if query_strings_raw['validated_status'] == 'Validated' else (
                False if query_strings_raw['validated_status'] == 'Invalidated' else None
            )
        ) if 'validated_status' in query_strings_raw else ''

        if validated != '':
            queryset = queryset.filter(validated=validated)

        if 'type' in query_strings_raw and query_strings_raw['type']:
            query = Q()
            for ext in IMAGE_EXTENSIONS:
                query |= Q(url__icontains=ext)
            if query_strings_raw['type'] == 'Photo':
                queryset = queryset.filter(query)
            else:
                queryset = queryset.exclude(query)
        return queryset.annotate(
            validated_order=Case(
                When(validated=True, then=Value(1)),
                When(validated=None, then=Value(2)),
                When(validated=False, then=Value(3)),
                default=Value(4),
                output_field=IntegerField(),
            )
        ).order_by("validated_order", "-updated_date")
    

class AttachmentListView(PageMixin, LoginRequiredMixin, ListView):
    template_name = "attachments/attachments.html"
    context_object_name = "attachments"
    title = _("Gallery")
    paginate_by = 10
    model = SubprojectFile

    # filter_hierarchy = [
    #                        'task',
    #                        'activity',
    #                        'phase'
    #                    ] + [adm_type[0].lower() for adm_type in AdministrativeLevel.TYPE]

    def post(self, request, *args, **kwargs):
        url = reverse("administrativelevels:attachments")
        final_querystring = request.GET.copy()

        for key, value in request.GET.items():
            if (
                    key in request.POST
                    and value != request.POST[key]
                    and request.POST[key] != ""
            ):
                final_querystring.pop(key)

        post_dict = request.POST.copy()
        post_dict.update(final_querystring)
        post_dict.pop("csrfmiddlewaretoken")
        if "reset-hidden" in post_dict and post_dict["reset-hidden"] == "true":
            return redirect(url)

        for key, value in request.POST.items():
            if value == "":
                post_dict.pop(key)
        final_querystring.update(post_dict)
        if final_querystring:
            url = "{}?{}".format(url, urlencode(final_querystring))
        return redirect(url)

    def get_context_data(self, **kwargs):
        context = super(AttachmentListView, self).get_context_data(**kwargs)
        context['hide_content_header'] = True
        query_params: dict = self.request.GET

        context["query_strings_raw"] = query_params.copy()
        context["query_strings_raw"].pop("page", None)

        context['subproject'] = Subproject.objects.get(id=self.kwargs['subproject_id'])

        context['file_ids'] = ",".join(
            map(str, self.get_queryset().values_list('id', flat=True))
        )



        query_params: dict = self.request.GET

        context["filter_hierarchy_query_strings"] = self.build_filter_hierarchy()
        context["query_strings_raw"] = query_params.copy()
        context["query_strings_raw"].pop("page", None)
        babylong_query_params_list = [key + '=' + value for key, value in context["query_strings_raw"].items()]
        if babylong_query_params_list:
            context["babylong_query_params"] = '&' + '&'.join(babylong_query_params_list)

        # context["type_links"] = self._build_type_links(query_params)


        paginator = self.__build_db_filter()

        context["no_results"] = paginator.count == 0
        page_number = int(query_params.get("page", 1))
        context["attachments"] = paginator.get_page(page_number) if page_number <= paginator.num_pages else []
        
        return context

    def get_template_names(self, *args, **kwargs):
        if self.request.htmx:
            return "attachments/_grid.html"
        else:
            return self.template_name

    def __build_db_filter(self) -> Paginator:
        query: QuerySet = self.get_queryset()

        paginator = Paginator(query, 36)

        return paginator
    

    def build_filter_hierarchy(self):
        resp = {}

        return json.dumps(resp)


    def get_queryset(self):
        queryset = super().get_queryset().filter(subproject_id=self.kwargs['subproject_id'])

        query_params: dict = self.request.GET

        query_strings_raw = query_params.copy()
        query_strings_raw.pop("page", None)
        validated = (
            True if query_strings_raw['validated_status'] == 'Validated' else (
                False if query_strings_raw['validated_status'] == 'Invalidated' else None
            )
        ) if 'validated_status' in query_strings_raw else ''

        if validated != '':
            queryset = queryset.filter(validated=validated)

        if 'type' in query_strings_raw and query_strings_raw['type']:
            query = Q()
            for ext in IMAGE_EXTENSIONS:
                query |= Q(url__icontains=ext)
            if query_strings_raw['type'] == 'Photo':
                queryset = queryset.filter(query)
            else:
                queryset = queryset.exclude(query)
        return queryset.annotate(
            validated_order=Case(
                When(validated=True, then=Value(1)),
                When(validated=None, then=Value(2)),
                When(validated=False, then=Value(3)),
                default=Value(4),
                output_field=IntegerField(),
            )
        ).order_by("validated_order", "-updated_date")
    


class ToggleValidationFileView(APIView):

    permission_classes = (permissions.IsAuthenticated,)
    def post(self, request, *args, **kwargs):
        try:
            file_id = request.GET.get('file_id', None)
            action = request.GET.get('action', None)
            print(action)
            invalidation_comment = request.POST.get('invalidation_comment', None)
            no_comment = request.POST.get('no_comment')
            if file_id:
                file = SubprojectFile.objects.get(id=file_id)
                if action == None:
                    file.validated = not file.validated
                elif action == 'validated':
                    file.validated = True
                else:
                    file.validated = False
                file.review = True
                SubprojectFile.objects.bulk_update([file], fields=['validated', 'review'])
                # file.save(
                #     user=request.user
                # )
                file_comment = FileComment()
                file_comment.file = file
                file_comment.user = request.user

                if file.validated:
                    file_comment.type = "comment_validated"
                else:
                    file_comment.type = "comment_invalidated"

                if no_comment:
                    file_comment.comment = _("No comment")
                else:
                    file_comment.comment = invalidation_comment
                file_comment.save()

                return Response(SubprojectFileSerializer(file, many=False).data, status.HTTP_200_OK)
            
            return Response({
                    'error': _('Review your request')
                }, status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({
                'error': exc.__str__()
            }, status.HTTP_400_BAD_REQUEST)


class FileCommentsListView(APIView):
    
    permission_classes = (permissions.IsAuthenticated,)
    def post(self, request, *args, **kwargs):
        try:
            file_id = request.GET.get('file_id', None)
            if file_id:
                return Response(FileCommentsSerializer(
                    FileComment.objects.filter(file_id=file_id), many=True).data, status.HTTP_200_OK
                )
            return Response({
                    'error': _('Review your request')
                }, status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({
                'error': exc.__str__()
            }, status.HTTP_400_BAD_REQUEST)
        

class TogglePrincipalFileView(APIView):

    permission_classes = (permissions.IsAuthenticated,)
    def post(self, request, *args, **kwargs):
        try:
            print(self.request.POST.get('principal', None))
            file_id = request.GET.get('file_id', None)
            principal = request.POST.get('principal', None) in ('true', True)
            if file_id:
                file = SubprojectFile.objects.get(id=file_id)
                file.subproject.get_files().update(principal=False) #Put all file no principal
                if file.validated != False and principal is not None:
                    file.principal = principal
                    
                    SubprojectFile.objects.bulk_update([file], fields=['principal'])
               
                    return Response(SubprojectFileSerializer(file, many=False).data, status.HTTP_200_OK)
                
                return Response({
                    'error': _("You can't put this file invalidated principal")
                }, status.HTTP_400_BAD_REQUEST)
            
            return Response({
                    'error': _('Review your request')
                }, status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({
                'error': exc.__str__()
            }, status.HTTP_400_BAD_REQUEST)


class ToggleSpecialFileView(APIView):
    
    permission_classes = (permissions.IsAuthenticated,)
    def post(self, request, *args, **kwargs):
        try:
            file_id = request.GET.get('file_id', None)
            special = request.POST.get('special', None) in ('true', True)
            if file_id:
                file = SubprojectFile.objects.get(id=file_id)
                if special is not None:
                    file.special = special
                    
                    SubprojectFile.objects.bulk_update([file], fields=['special'])
               
                return Response(SubprojectFileSerializer(file, many=False).data, status.HTTP_200_OK)
            
            return Response({
                    'error': 'Review your request'
                }, status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({
                'error': exc.__str__()
            }, status.HTTP_400_BAD_REQUEST)
        

@login_required
def file_download(self, url: str):
    url = url.split('?')[0]
    response = requests.get(url)
    if response.status_code == 200:
        content_disposition = response.headers.get("content-disposition")
        filename = url.split("/")[-1]
        if not filename:
            filename = url.split("/")[-2]

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
        filename = f'{filename}.png' if '.' not in filename else filename
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    else:
        return HttpResponse("Failed to download the file.")


@login_required
def files_download_zip(self):
    ids = self.GET.get("ids").split(",")
    urls = SubprojectFile.objects.filter(id__in=[_id for _id in ids if _id]).values_list('url', flat=True)
    buffer = BytesIO()
    zip_file = zipfile.ZipFile(buffer, "w")
    for url in urls:
        url = url.split("?")[0]
        response = requests.get(url)
        if response.status_code == 200:
            content_disposition = response.headers.get("content-disposition")
            filename = url.split("/")[-1]
            if not filename:
                filename = url.split("/")[-2]
            if content_disposition is not None:
                try:
                    fname = re.findall('filename="(.+)"', content_disposition)

                    if len(fname) != 0:
                        filename = fname[0]
                except:
                    pass
        zip_file.writestr(f'{filename}.png' if '.' not in filename else filename, response.content)

    zip_file.close()

    response = HttpResponse(buffer.getvalue())
    response["Content-Type"] = "application/x-zip-compressed"
    response["Content-Disposition"] = "attachment; filename=attachments.zip"

    return response
