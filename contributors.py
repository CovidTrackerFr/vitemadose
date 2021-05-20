import sys
import logging
from dotmap import DotMap
import json
import requests
from requests.auth import HTTPBasicAuth

EXPORT_PATH = "data/output/contributors_{team}.json"
TOKEN="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"
auth=HTTPBasicAuth('floby', TOKEN)

logger = logging.getLogger('contributors')
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler(sys.stdout))

SECTIONS = {
  "scrap": "CovidTrackerFr/vitemadose",
  "web": "CovidTrackerFr/vitemadose-front",
  "ios": "CovidTrackerFr/vitemadose-ios",
  "android": "CovidTrackerFr/vitemadose-android",
  "infra": "CovidTrackerFr/covidtracker-server"
}

def main(teams=SECTIONS, export_path=EXPORT_PATH):
  contributors_by_team = {}
  for team, path in teams.items():
    logger.info(f"getting contributors for team '{team}'")
    response = requests.get(f"https://api.github.com/repos/{path}/contributors", auth=auth)
    response.raise_for_status()
    team_contributors = response.json()
    contributors_by_team[team] = [map_github_contributor(team=team, **contributor) for contributor in team_contributors]

  all_contributors = {}
  for team, contributors in contributors_by_team.items():
    for contributor in contributors:
      if contributor.id in all_contributors:
        all_contributors[contributor.id].teams.append(team)
        contributor.teams = all_contributors[contributor.id].teams
      else:
        all_contributors[contributor.id] = contributor

  for team, contributors in contributors_by_team.items():
    outpath = export_path.format(team=team)
    logger.info(f"writing about {len(contributors)} to {outpath}")
    with open(outpath, 'w') as outfile:
      json.dump({ "contributors": contributors }, outfile, indent=2)

  outpath = export_path.format(team="all")
  with open(outpath, 'w') as outfile:
    logger.info(f"writing about {len(all_contributors)} to {outpath}")
    json.dump({ "contributors": list(all_contributors.values()) }, outfile, indent=2)




def map_github_contributor(team, login, avatar_url, html_url, **kwargs):
  logger.info(f"getting more info from github about '{login}'")
  p = get_github_profile(login)
  full_name = p.name
  site_web = p.blog
  twitter_username = p.twitter_username
  company = p.company
  github_url = html_url
  bio = p.bio
  links = {
    "github": github_url,
    "twitter": twitter_username
  }
  return DotMap({
    "id": login,
    "nom": full_name,
    "pseudo": login,
    "photo": avatar_url,
    "site_web": site_web,
    "job": bio,
    "localisation": p.location,
    "company": company,
    "teams": [ team ],
    "links": [
      {"site": site, "url": url}
      for site, url in links.items()
      if url is not None
    ]
  })

PROFILES = {}
def get_github_profile(login):
  if login in PROFILES:
    logger.debug(f"HIT! got profile '{login}' from cache")
    return PROFILES[login]

  pr = requests.get(f"https://api.github.com/users/{login}", auth=auth)
  pr.raise_for_status()
  p = DotMap(pr.json())
  PROFILES[login] = p
  return p



if __name__ == "__main__":
  main()
