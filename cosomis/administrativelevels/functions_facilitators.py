"""Current stabilized facilitators of a locality (village, CVD, geographical unit or any level above).

A facilitator is "stabilized" in a village when the village id is in their CDD field
`stabilization_administrative_ids`. The data is read live from the CDD table, so the page
always shows the facilitators in place today."""
from django.utils.translation import gettext_lazy as _

from authentication.models import Facilitator

COMMUNITY = 'community_facilitator'
TECHNICAL = 'technical_facilitator'


def _stabilized_ids(facilitator):
    return {int(v) for v in facilitator.stabilization_administrative_ids or [] if str(v).isdigit()}


def active_facilitators():
    """Active field facilitators (AC/FC and FT), test and training accounts left out."""
    return list(Facilitator.objects.using('cdd')
                .filter(active=True, develop_mode=False, training_mode=False,
                        facilitator_type__in=(COMMUNITY, TECHNICAL))
                .order_by('name', 'username'))


def stabilized_facilitators(villages, facilitators=None):
    """{'community': [...], 'technical': [...]} for the given villages.

    `villages` is a list of villages or a {village id: name} dict. Each facilitator gets a
    `stabilized_villages` attribute: the names of the given villages they are stabilized in.
    The active facilitators are read in one query (about 200 rows), then matched here."""
    if not isinstance(villages, dict):
        villages = {v.pk: v.name for v in villages}
    result = {'community': [], 'technical': []}
    if not villages:
        return result
    for facilitator in (facilitators if facilitators is not None else active_facilitators()):
        ids = _stabilized_ids(facilitator) & villages.keys()
        if not ids:
            continue
        facilitator.stabilized_village_ids = ids
        facilitator.stabilized_villages = sorted(villages[i] for i in ids)
        key = 'technical' if facilitator.facilitator_type == TECHNICAL else 'community'
        result[key].append(facilitator)
    return result


def stabilized_facilitator_groups(villages, facilitators=None):
    """[(label, facilitators), ...] for the `stabilized_facilitators.html` component."""
    found = stabilized_facilitators(villages, facilitators)
    return [(_("AC/FC (community facilitator)"), found['community']),
            (_("FT (technical facilitator)"), found['technical'])]
