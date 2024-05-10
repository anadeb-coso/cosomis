from typing import Any, Dict
# from koboextractor import KoboExtractor
import environ
from requests import get as get_request
from .config import kobotoolbox_api_base_url_v2
from kobotoolbox.form_id_kobo import FORM_ID_KOBO

env = environ.Env()
env.read_env()



def get_all(form_uid: str = FORM_ID_KOBO, KOBO_TOKEN = env('KOBO_TOKEN')) -> Dict[str, Any]:
    headers = {'Authorization': f'Token {KOBO_TOKEN}'}
    try:
        # url = f'{kobotoolbox_api_base_url}/assets/{form_uid}/submissions/?format=json'
        url = f'{kobotoolbox_api_base_url_v2}/assets/{form_uid}/data/?format=json'
        response = get_request(url, headers=headers)
        # sorted_results = sorted(response.json(),
        #                         key=lambda result: result['_submission_time'],
        #                         reverse=False)
        return response.json()
    except Exception as exc:
        return {}

def get(id, form_uid=FORM_ID_KOBO, KOBO_TOKEN = env('KOBO_TOKEN')) -> Dict[str, Any]:
    headers = {'Authorization': f'Token {KOBO_TOKEN}'}
    try:
        url = f'{kobotoolbox_api_base_url_v2}/assets/{form_uid}/data/{id}/?format=json'
        response = get_request(url, headers=headers)

        return response.json()
    except Exception as exc:
        return {}