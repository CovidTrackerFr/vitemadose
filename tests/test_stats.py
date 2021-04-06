# -- Tests des statistiques --
import json
import os
from pathlib import Path

from stats_generation.stats_available_centers import export_centres_stats


def test_stat_count() -> None:
    export_centres_stats(Path('tests/fixtures/stats/info-centres.json'))

    output_file = Path('data/output/stats.json')
    assert output_file.exists()

    generated_content = output_file.read_text()
    base_file = Path('tests/fixtures/stats/stat-output.json')
    base_content = base_file.read_text()
    base_stats = json.loads(base_content)

    stats = json.loads(generated_content)
    assert stats['tout_departement']['disponibles'] == base_stats['tout_departement']['disponibles']
    assert stats['tout_departement']['total'] == base_stats['tout_departement']['total']
