<a href="https://covidtracker.fr/vitemadose"><img src="./.github/assets/logo.png" width="150" alt="Vite Ma Dose !" /></a>

[Vite Ma Dose !](https://covidtracker.fr/vitemadose) est un outil open source de [CovidTracker](https://covidtracker.fr) permettant de détecter les rendez-vous disponibles dans votre département afin de vous faire vacciner (sous réserve d'éligibilité).

[![Contributeurs][contributors-shield]][contributors-url]
[![Issues][issues-shield]][issues-url]
[![Licence][license-shield]][license-url]
[![codecov](https://codecov.io/gh/CovidTrackerFr/vitemadose/branch/main/graph/badge.svg?token=UQEI3UXY67)](https://codecov.io/gh/CovidTrackerFr/vitemadose)

## Signaler un Problème, une idée de modification


Ouvrez une [issue Github](https://github.com/CovidTrackerFr/vitemadose/issues/new) si vous souhaitez signaler un problème.

## Comment Contribuer

Le développement de l'application étant tres actif nous recommendons de joindre [le Mattermost Général de Vite Ma Dose](https://mattermost.covidtracker.fr/covidtracker/channels/town-square) pour être sûr que personne ne travaille déjà sur ce que vous comptez faire. Si ce n'est pas le cas, quelqu'un vous aiguillera si vous avez besoin d'aide.
Pour proposer une modification, un ajout, ou decrire un bug sur l'outil de détection, vous pouvez ouvrir une [issue](https://github.com/CovidTrackerFr/vitemadose/issues/new) ou une [Pull Request](https://github.com/CovidTrackerFr/vitemadose/pulls) avec vos modifications. 

La [documentation](https://hackmd.io/YHcjKsUzQ1-cMomOUuTpXw) permet de centraliser les informations importantes relatives au développement de l'outil : comment ça marche, quelles sont les grosses tâches du moment, comment on communique ...

Pour le code en Python, veillez à respecter le standard PEP8 avant de soumettre une Pull-Request.
La plupart des IDEs et éditeurs de code moderne proposent des outils permettant de mettre en page votre code en suivant ce standard automatiquement.

## Plateformes supportées

| Plateforme        | Lien           | Supporté  |
| ------------- |:-------------:| :-----:|
| <img src="https://vitemadose.covidtracker.fr/assets/images/png/logo_doctolib.png" width="100" /> | https://doctolib.fr/ | <font style="color: green; font-size: 16px;">✓</font> |
| <img src="https://vitemadose.covidtracker.fr/assets/images/png/logo_keldoc.png" width="100" /> | https://keldoc.com | <font style="color: green; font-size: 16px;">✓</font> |
| <img src="https://vitemadose.covidtracker.fr/assets/images/png/logo_maiia.png" width="100" /> | https://maiia.com | <font style="color: green; font-size: 16px;">✓</font> |
| <img src="https://vitemadose.covidtracker.fr/assets/images/png/logo_ordoclic.png" width="100" /> | https://ordoclic.fr | <font style="color: green; font-size: 16px;">✓</font> |
| <img src="https://vitemadose.covidtracker.fr/assets/images/png/logo_mapharma.png" width="100" /> | https://www.mapharma.net/ | <font style="color: green; font-size: 16px;">✓</font> |
| <img src="https://vitemadose.covidtracker.fr/assets/images/png/logo_avecmondoc.png" width="100" /> | https://www.avecmondoc.com/ | <font style="color: green; font-size: 16px;">✓</font> |
| <img src="https://vitemadose.covidtracker.fr/assets/images/png/logo_pandalab.png" width="100" /> | https://pharmagest.com/en/pandalab-agenda/ | <font style="color: orange; font-size: 16px;">En cours</font> |

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

<!-- shield cards !-->
[contributors-shield]: https://img.shields.io/github/contributors/CovidTrackerFr/vitemadose.svg?style=for-the-badge
[contributors-url]: https://github.com/CovidTrackerFr/vitemadose/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/CovidTrackerFr/vitemadose.svg?style=for-the-badge
[forks-url]: https://github.com/CovidTrackerFr/vitemadose/network/members
[issues-shield]: https://img.shields.io/github/issues/CovidTrackerFr/vitemadose.svg?style=for-the-badge
[issues-url]: https://github.com/CovidTrackerFr/vitemadose/issues
[license-shield]: https://img.shields.io/github/license/CovidTrackerFr/vitemadose.svg?style=for-the-badge
[license-url]: https://github.com/CovidTrackerFr/vitemadose/blob/master/LICENSE
