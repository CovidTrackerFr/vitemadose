# vitemadose

Doc : https://hackmd.io/YHcjKsUzQ1-cMomOUuTpXw

## Démarrage rapide

Installation du modules (À la racine de `vitemadose`) :

```bash
pip install -e .
```

On peut ensuite importer les fonctions définies dans `scraper/__init__.py` telles que `main` 
(définie dans `scraper/prototype.py`) :

```python
>>> from scraper import main
>>> main()
```

Où exécuter directement depuis le script de scraper (il tourne périodiquement, cf `.github/workflows/scrape.yml`):

```bash
scripts/scrape
```

Exécuter les tests :

```bash
scripts/test
```
