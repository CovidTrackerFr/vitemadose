
def sort_center(center: dict) -> str:
    return center.get("prochain_rdv", "-") if center else "-"