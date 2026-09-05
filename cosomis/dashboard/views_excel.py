from django.views.generic import View
from cosomis.mixins import AJAXRequestMixin, JSONResponseMixin
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.translation import gettext_lazy
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from django.http import Http404
import json
import os
from datetime import datetime
import pandas as pd

from administrativelevels.libraries import download_file




class DownloadExcelFile(AJAXRequestMixin, LoginRequiredMixin, JSONResponseMixin, View):
    template_name = 'statistics/subprojects_tracking.html'
    context_object_name = 'Download'
    title = gettext_lazy("Download")

    def post(self, request, *args, **kwargs):
        input_json = json.loads(request.body)
        datas = input_json.get('datas')
        type_datas = input_json.get('type_datas')

        try:
            # Écrit sous MEDIA_ROOT (et non `static/`) : les fichiers `static/` d'une app
            # ne sont resservables dynamiquement qu'en DEBUG. En production (collectstatic
            # + WhiteNoise/S3), un fichier déposé ici à la volée n'est jamais atteignable
            # via l'URL {% static %} renvoyée au client -> le window.open() du navigateur
            # échoue systématiquement (404). MEDIA_ROOT est servi dynamiquement.
            export_dir = os.path.join(settings.MEDIA_ROOT, "excel", "subprojects")
            os.makedirs(export_dir, exist_ok=True)

            file_name = type_datas if type_datas else "summary_subprojects_excel"
            file_path = os.path.join(
                "excel", "subprojects",
                file_name + str(datetime.today().replace(microsecond=0)).replace("-", "").replace(":", "").replace(" ", "_") + ".xlsx"
            )
            pd.DataFrame(datas).to_excel(os.path.join(settings.MEDIA_ROOT, file_path))

            if not file_path:
                return redirect('dashboard:dashboard')
            # Le fichier vient d'être écrit par ce même process : on le renvoie directement
            # dans cette réponse (une seule requête HTTP) au lieu de faire suivre son chemin
            # au client pour une seconde requête vers une URL statique qui n'existe pas en
            # production.
            return download_file.download(
                request,
                file_path,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        except Exception as exc:
            return self.render_to_json_response({"error": str(gettext_lazy("An error has occurred..."))}, safe=False)

        