import json

def export_centres_stats():
    centres_info = get_centres_info()
    centres_stats = {
        "tout_departement": {
            "disponibles": 0,
            "total": 0,
        }
    }

    tout_dep_obj = centres_stats["tout_departement"]

    for dep_code, dep_value in centres_info.items():
        nombre_disponibles = len(dep_value["centres_disponibles"])
        count = len(dep_value["centres_indisponibles"]) + nombre_disponibles
        centres_stats[dep_code] = {
            "disponibles": nombre_disponibles,
            "total": count,
        }

        tout_dep_obj["disponibles"] += nombre_disponibles
        tout_dep_obj["total"] += count

    with open("data/output/stats.json", "w") as stats_file:
        json.dump(centres_stats, stats_file, indent=2)


def get_centres_info():
    with open("data/output/info_centres.json", "r") as f:
        return json.load(f)


if __name__ == '__main__':
    export_centres_stats()
