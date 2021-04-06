# -- Tests des statistiques --
import json
import os

from scraper.centres_stats import export_centres_stats


def test_stat_count():
    export_centres_stats('tests/fixtures/stats/info-centres.json')

    output_file = 'data/output/stats.json'
    assert os.path.exists(output_file)

    output_file = open(output_file, 'r')
    generated_content = output_file.read()
    output_file.close()
    base_file = open('tests/fixtures/stats/stat-output.json', 'r')
    base_content = base_file.read()
    base_file.close()

    stats = json.loads(generated_content)
    assert stats['tout_departement']['disponibles'] == 280
    assert stats['tout_departement']['total'] == 2291
