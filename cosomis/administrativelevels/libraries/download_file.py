import os
from django.conf import settings
from django.http import FileResponse, Http404

def download(request, path, content_type="application/pdf", param_download=True):
    file_path = os.path.join(settings.MEDIA_ROOT, path)
    if os.path.exists(file_path):
        # FileResponse envoie le fichier par blocs (streaming) plutôt que de le charger
        # intégralement en mémoire avec fh.read() : évite un pic mémoire sur les gros
        # exports.
        content = 'inline; filename=' + os.path.basename(file_path)
        if param_download:
            content = "attachment; filename=" + os.path.basename(file_path)
        response = FileResponse(open(file_path, 'rb'), content_type=content_type)
        response['Content-Disposition'] = content
        return response
    raise Http404