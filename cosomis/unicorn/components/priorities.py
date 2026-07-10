from django_unicorn.components import UnicornView
from subprojects.models import VillagePriority


class PrioritiesView(UnicornView):
    priorities = []
    components = []
    goals = []
    administrativelevel_village = None
    def __init__(self, administrativelevel_village: object, priorities: list, components: list, goals: list,  *args, **kwargs):
        super().__init__(**kwargs)  # calling super is required
        self.administrativelevel_village = administrativelevel_village
        self.priorities = list(priorities)
        self.components = components
        self.goals = goals

    def add(self):
        priority = VillagePriority()
        priority.component_id = self.components[0].pk
        priority.proposed_men = 0
        priority.proposed_women = 0
        priority.estimated_cost = 0.0
        priority.climate_changing_contribution = ""
        priority.administrative_level = self.administrativelevel_village
        priority.meeting_id = 1
        priority = priority.save_and_return_object()
        self.priorities.append(priority)

        # for elt in self.priorities:
        #     print(elt)

    def remove(self, pk):
        for i in range(len(self.priorities)):
            if self.priorities[i]['pk'] == pk:
                del self.priorities[i]
                VillagePriority.objects.get(id=pk).delete()
                break