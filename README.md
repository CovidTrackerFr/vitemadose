<a href="https://covidtracker.fr/vitemadose"><img src="./.github/assets/logo.png" width="150" alt="Vite Ma Dose !" /></a>

[Vite Ma Dose !](https://covidtracker.fr/vitemadose) est un outil open source de [CovidTracker](https://covidtracker.fr) permettant de détecter les rendez-vous disponibles dans votre département afin de vous faire vacciner (sous réserve d'éligibilité).

[![Contributeurs][contributors-shield]][contributors-url]
[![Issues][issues-shield]][issues-url]
[![Licence][license-shield]][license-url]
![Coverage][coverage-shield]

## Signaler un Problème, une idée de modification

Ouvrez une [issue Github](https://github.com/CovidTrackerFr/vitemadose/issues/new) si vous souhaitez signaler un problème.

## Comment Contribuer

Le développement de l'application est très actif, donc envoyez un message sur [le Telegram Général de Vite Ma Dose](https://hackmd.io/YHcjKsUzQ1-cMomOUuTpXw#Cha%C3%AEnes-de-discussion) pour être sûr que personne ne travaille déjà sur ce que vous comptez faire. Si ce n'est pas le cas, quelqu'un vous aiguillera si vous avez besoin d'aide.
Pour proposer une modification ou un ajout sur l'outil de détection, ouvrez une [Pull Request](https://github.com/CovidTrackerFr/vitemadose/pulls). 

La [documentation](https://hackmd.io/YHcjKsUzQ1-cMomOUuTpXw) permet de centraliser les informations importantes relatives au développement de l'outil : comment ça marche, quelles sont les grosses tâches du moment, comment on communique ...

Pour le code en Python, merci d'utiliser un linter avant de soumettre une PR.

## Plateformes supportées

| Plateforme        | Lien           | Supporté  |
| ------------- |:-------------:| :-----:|
| <img src="https://www.ch2p.bzh/wp-content/uploads/2020/02/Logo-doctolib-bleu-tr.png" width="100" /> | https://doctolib.fr/ | <font style="color: green; font-size: 16px;">✓</font> |
| <img src="https://www.keldoc.com/keldoc-logo.nolqip.e7abaad88d1642c9c1f2.png" width="100" /> | https://keldoc.com | <font style="color: green; font-size: 16px;">✓</font> |
| <img src="https://www.rmingenierie.net/wp-content/uploads/2019/12/logo-Maiia-vert.png" width="100" /> | https://maiia.com | <font style="color: green; font-size: 16px;">✓</font> |
| <img src="https://www.ordoclic.fr/wp-content/uploads/2019/03/Logo.png" width="100" /> | https://ordoclic.fr | <font style="color: green; font-size: 16px;">✓</font> |
| <img src="https://pharmagest.com/wp-content/uploads/PandaPatient2.jpg" width="100" /> | https://pharmagest.com/en/pandalab-agenda/ | <font style="color: orange; font-size: 16px;">En cours</font> |
| <img src="https://www.mapharma.fr/media/logo/stores/2/logo_mapharma.png" width="100" /> | https://www.mapharma.fr/ | <font style="color: orange; font-size: 16px;">En Cours</font> |

## Utilisation

Installer les dépendances (À la racine de `vitemadose`) :

```bash
make install
```

Lancer le scraper :

```bash
make scrape
```

Générer des statistiques :

```bash
make stats
```

Lancer des tests unitaires :

```bash
make test
```