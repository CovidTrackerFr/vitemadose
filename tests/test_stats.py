# -- Tests des statistiques --
import json
import os

from stats_generation.stats_available_centers import export_centres_stats


def test_stat_count():
    output_file_name = "data/output/stats_test.json"
    export_centres_stats("tests/fixtures/stats/info-centres.json", output_file_name)

    assert os.path.exists(output_file_name)

    output_file = open(output_file_name, "r")
    generated_content = output_file.read()
    output_file.close()
    base_file = open("tests/fixtures/stats/stat-output.json", "r")
    base_file.close()

    stats = json.loads(generated_content)
    assert stats["tout_departement"]["disponibles"] == 280
    assert stats["tout_departement"]["total"] == 2291
    os.remove(output_file_name)
