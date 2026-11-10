"""Current stabilized facilitators of a locality (village or CVD).

A facilitator is "stabilized" in a village when the village id is in their CDD field
`stabilization_administrative_ids`. The data is read live from the CDD table, so the page
always shows the facilitators in place today."""
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from authentication.models import Facilitator

COMMUNITY = 'community_facilitator'
TECHNICAL = 'technical_facilitator'


def stabilized_facilitators(villages):
    """{'community': [...], 'technical': [...]} for the given villages.

    Each facilitator gets a `stabilized_villages` attribute: the names of the given villages
    they are stabilized in (useful for a CVD that groups several villages)."""
    villages = {v.pk: v.name for v in villages}
    result = {'community': [], 'technical': []}
    if not villages:
        return result

    in_villages = Q()
    for village_id in villages:
        in_villages |= Q(stabilization_administrative_ids__contains=[village_id])
    facilitators = (Facilitator.objects.using('cdd')
                    .filter(in_villages, active=True, develop_mode=False, training_mode=False,
                            facilitator_type__in=(COMMUNITY, TECHNICAL))
                    .order_by('name', 'username'))
    for facilitator in facilitators:
        ids = {int(v) for v in facilitator.stabilization_administrative_ids or [] if str(v).isdigit()}
        facilitator.stabilized_villages = sorted(villages[i] for i in ids & villages.keys())
        key = 'technical' if facilitator.facilitator_type == TECHNICAL else 'community'
        result[key].append(facilitator)
    return result


def stabilized_facilitator_groups(villages):
    """[(label, facilitators), ...] for the `stabilized_facilitators.html` component."""
    found = stabilized_facilitators(villages)
    return [(_("AC/FC (community facilitator)"), found['community']),
            (_("FT (technical facilitator)"), found['technical'])]
