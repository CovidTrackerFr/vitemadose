from collections import Counter

from utils.vmd_utils import departementUtils


def deduplicates_names(departement_centers):
    """
    Removes unique names by appending city name
    in par_departement

    see https://github.com/CovidTrackerFr/vitemadose/issues/173
    """
    deduplicated_centers = []
    departement_center_names_count = Counter([center["nom"] for center in departement_centers])
    names_to_remove = {
        departement for departement in departement_center_names_count if departement_center_names_count[departement] > 1
    }

    for center in departement_centers:
        if center["nom"] in names_to_remove:
            center["nom"] = f"{center['nom']} - {departementUtils.get_city(center['metadata']['address'])}"
        deduplicated_centers.append(center)
    return deduplicated_centers
