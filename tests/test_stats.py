# -- Tests des statistiques --
import json
import os

from pathlib import Path
from stats_generation.stats_available_centers import export_centres_stats


def test_stat_count():
    output_file_name = "stats_test.json"
    center_data = Path("tests", "fixtures", "stats", "info-centres.json")
    export_centres_stats(center_data, output_file_name)

    assert os.path.exists(f"data/output/{output_file_name}")

    output_file = open(f"data/output/{output_file_name}", "r")
    generated_content = output_file.read()
    output_file.close()

    stats = json.loads(generated_content)
    assert stats["tout_departement"]["disponibles"] == 280
    assert stats["tout_departement"]["total"] == 2291
    os.remove(f"data/output/{output_file_name}")
