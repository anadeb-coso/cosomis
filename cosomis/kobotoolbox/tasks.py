from cosomis.celery import app
from kobotoolbox.api_call import get_all
from kobotoolbox.utils import save_kobo_villages_coordinates

@app.task
def kobo_request():
    all_forms = get_all()
    # print(all_forms)
    # coordonnées écrites seulement sur un village identifié sans ambiguïté
    save_kobo_villages_coordinates(all_forms.get('results'))

    return all_forms
    


@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    # Calls kobo_request() every 60 seconds.
    # print("Passe")
    sender.add_periodic_task(60, kobo_request.s(), name='check issues every sixty seconds')
