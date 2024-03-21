from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import generic

from cosomis.mixins import AJAXRequestMixin, JSONResponseMixin
from administrativelevels.models import AdministrativeLevel
from administrativelevels.functions_adl import get_cascade_administrative_levels_by_administrative_level_id


class GetAdministrativeLevelForCVDByADLView(AJAXRequestMixin, LoginRequiredMixin, JSONResponseMixin, generic.View):
    def get(self, request, *args, **kwargs):
        adl_id = request.GET.get('administrative_level_id')

        objects = AdministrativeLevel.objects.filter(id=int(adl_id))
        d = []
        if objects:
            obj = objects.first()
            if obj.cvd:
                d = [{'id': elt.id, 'name': elt.name} for elt in obj.cvd.get_villages()]

        return self.render_to_json_response(sorted(d, key=lambda o: o['name']), safe=False)
    

class GetChoicesForNextAdministrativeLevelNoConditionView(AJAXRequestMixin, LoginRequiredMixin, JSONResponseMixin, generic.View):
    def get(self, request, *args, **kwargs):
        parent_id = request.GET.get('parent_id')

        data = AdministrativeLevel.objects.filter(parent_id=int(parent_id))

        d = [{'id': elt.id, 'name': elt.name} for elt in data]

        return self.render_to_json_response(sorted(d, key=lambda o: o['name']), safe=False)
    

class GetChoicesForNextAdministrativeLevelView(AJAXRequestMixin, LoginRequiredMixin, JSONResponseMixin, generic.View):
    def get(self, request, *args, **kwargs):
        parent_id = request.GET.get('parent_id')
        geographical_unit_id = request.GET.get('geographical_unit_id', None)

        data = AdministrativeLevel.objects.filter(parent_id=int(parent_id))

        d = [{'id': elt.id, 'name': elt.name} for elt in data if((not elt.geographical_unit) or (elt.geographical_unit and geographical_unit_id and elt.geographical_unit.id == int(geographical_unit_id)))]

        return self.render_to_json_response(sorted(d, key=lambda o: o['name']), safe=False)

class GetChoicesAdministrativeLevelByGeographicalUnitView(AJAXRequestMixin, LoginRequiredMixin, JSONResponseMixin, generic.View):
    def get(self, request, *args, **kwargs):
        geographical_unit_id = request.GET.get('geographical_unit_id')
        cvd_id = request.GET.get('cvd_id', None)

        data = AdministrativeLevel.objects.filter(geographical_unit=int(geographical_unit_id))

        d = [{'id': elt.id, 'name': elt.name} for elt in data if((not elt.cvd) or (elt.cvd and cvd_id and elt.cvd.id == int(cvd_id)))]
        
        return self.render_to_json_response(sorted(d, key=lambda o: o['name']), safe=False)
    

class GetAncestorAdministrativeLevelsView(AJAXRequestMixin, LoginRequiredMixin, JSONResponseMixin, generic.View):
    def get(self, request, *args, **kwargs):
        administrative_id = request.GET.get('administrative_id', None)
        ancestors = []
        try:
            ancestors.insert(0, str(AdministrativeLevel.objects.get(id=int(administrative_id)).parent.id))
        except Exception as exc:
            pass

        return self.render_to_json_response(ancestors, safe=False)
    


class GetChoicesForNextAdministrativeLevelAllView(AJAXRequestMixin, JSONResponseMixin, generic.View):
    def get(self, request, *args, **kwargs):
        parent_ids = request.GET.getlist('parent_id[]')
        datas = dict()
        if not parent_ids or "All" in parent_ids:
            parent_ids = [None]
        print(parent_ids)
        datas = {
            "prefectures": [],
            "communes": [],
            "cantons":  [],
            "villages": []
        }
        for parent_id in parent_ids:
            for k, v in get_cascade_administrative_levels_by_administrative_level_id(parent_id).items():
                datas[k] += v

        return self.render_to_json_response(
            datas, 
            safe=False
        )