# vitemadose

Doc : https://hackmd.io/YHcjKsUzQ1-cMomOUuTpXw

## Démarrage rapide

Installation du module (À la racine de `vitemadose`) :

```bash
scripts/install
```

On peut ensuite importer les fonctions définies dans `scraper/__init__.py`
telles que `main` (définie dans `scraper/scraper.py`) :

```python
>>> from scraper import main
>>> main()
```

Où exécuter directement depuis le script de scraper (il tourne périodiquement,
cf `.github/workflows/scrape.yml`):

```bash
scripts/scrape
```

Exécuter les tests :

```bash
scripts/test
```
