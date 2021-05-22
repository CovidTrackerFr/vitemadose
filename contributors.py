import sys
import random
import logging
from dotmap import DotMap
import json
import csv
import requests
import os
from requests.auth import HTTPBasicAuth

EXPORT_PATH = "data/output/contributors_{team}.json"
GITHUB_API_USER = os.environ.get('GITHUB_API_USER')
GITHUB_API_KEY = os.environ.get('GITHUB_API_KEY')

client = requests.Session()
if GITHUB_API_KEY is not None and GITHUB_API_USER is not None:
    client.auth = HTTPBasicAuth(GITHUB_API_USER, GITHUB_API_KEY)

logger = logging.getLogger("contributors")
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler(sys.stdout))



def main(export_path=EXPORT_PATH):
    csv_contributors = get_benevoles_csv_contributors()
    github_contributors = get_github_contributors()

    additional_contributors = [
      contributor for contributor in csv_contributors
      if contributor.github not in github_contributors
    ]

    all_contributors = list(github_contributors.values()) + additional_contributors
    random.shuffle(all_contributors)

    outpath = export_path.format(team="all")
    with open(outpath, "w") as outfile:
        logger.info(f"writing about {len(all_contributors)} contributors to {outpath}")
        json.dump({"contributors": all_contributors}, outfile, indent=2, default=dumper)


GITHUB_REPOS = {
    "scrap": "CovidTrackerFr/vitemadose",
    "web": "CovidTrackerFr/vitemadose-front",
    "ios": "CovidTrackerFr/vitemadose-ios",
    "android": "CovidTrackerFr/vitemadose-android",
    "infra": "CovidTrackerFr/covidtracker-server",
}
def get_github_contributors(teams=GITHUB_REPOS):
    contributors_by_team = {}
    for team, path in teams.items():
        logger.info(f"getting contributors for team '{team}'")
        response = client.get(f"https://api.github.com/repos/{path}/contributors")
        response.raise_for_status()
        team_contributors = response.json()
        contributors_by_team[team] = [
            GithubContributor(team=team, row=contributor) for contributor in team_contributors
        ]

    all_contributors = {}
    for team, contributors in contributors_by_team.items():
        for contributor in contributors:
            if contributor.github in all_contributors:
                all_contributors[contributor.github].teams.add(team)
            else:
                all_contributors[contributor.github] = contributor

    return all_contributors

DEFAULT_CSV_PATH = os.path.join(os.path.dirname(__file__), './data/input/benevoles.csv')
def get_benevoles_csv_contributors(csv_path=DEFAULT_CSV_PATH):
  contributors = []
  with open(csv_path, 'r') as infile:
    csvreader = csv.DictReader(infile, delimiter=",")
    for row in csvreader:
      contributors.append(CsvContributor(row))
  return contributors



class Contributor:
  def __init__(self, github=None):
    self.github = github
    self.links = {}
    self.teams = set()
    self.job = None
    self.localisation = None
    self.company = None
    if github is not None and github:
      self.links['github'] = f"https://github.com/{github}"

  def toJSON(self):
    return {
      "nom": self.nom,
      "pseudo": self.pseudo,
      "photo": self.photo,
      "site_web": self.site_web,
      "job": self.job,
      "localisation": self.localisation,
      "company": self.company,
      "teams": list(self.teams),
      "links": [{"site": site, "url": url}
                for site, url in self.links.items()
                if url is not None and url]
    }

class GithubContributor(Contributor):
  def __init__(self, team, row):
    login = row["login"]
    super().__init__(login)
    logger.info(f"getting more info from github about '{login}'")
    p = get_github_profile(self.github)
    self.teams.add(team)
    self.nom = p.name
    self.pseudo = login
    self.photo = p.avatar_url
    self.site_web = p.blog
    self.job = p.bio
    self.localisation = p.location
    self.company = p.company
    self.links['twitter'] = f"https://twitter.com/{p.twitter_username}"

class CsvContributor(Contributor):
  def __init__(self, row):
    login = row['pseudo_github']
    super().__init__(login)
    self.row = row
    self.nom = f"{row['Prénom']} {row['Nom']}"
    self.photo = None
    self.site_web = row['site_web']
    self.localisation = row['Localisation']
    if row['pseudo_twitter']:
      self.links['twitter'] = f"https://twitter.com/{row['pseudo_twitter']}"
    if row['lien_linkedin']:
      self.links['linkedin'] = row['lien_linkedin']

  @property
  def pseudo(self):
    if self.row['pseudo_mattermost']:
      return self.row['pseudo_mattermost']
    if self.row['pseudo_twitter']:
      return self.row['pseudo_twitter']
    return self.row['pseudo_github']

class MergedContributor(Contributor):
  def __init__(self, first, second):
    github = first.github if first.github else second.github
    super().__init__(github)

def dumper (obj):
  try:
    return obj.toJSON()
  except AttributeError as e:
    return obj.__dict__

PROFILES = {}
def get_github_profile(login):
    if login in PROFILES:
        logger.debug(f"HIT! got profile '{login}' from cache")
        return PROFILES[login]

    pr = client.get(f"https://api.github.com/users/{login}")
    pr.raise_for_status()
    p = DotMap(pr.json())
    PROFILES[login] = p
    return p

if __name__ == "__main__":
    main()
