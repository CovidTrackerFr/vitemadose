#!/bin/bash

set -o errexit
set -o pipefail
set -o nounset
set -o errtrace

GITLAB_HOST="gitlab.com"
RUNNER_NAME="Chez ${RUNNER_LOCATION:-inconnu}"
GITLAB_RUNNER_TOKEN=${GITLAB_RUNNER_TOKEN}
TAG_LIST="local,privileged"
if test -z "${GITLAB_RUNNER_TOKEN}"; then
  echo vous devez définir GITLAB_RUNNER_TOKEN en variable d\'environnement >&2
  exit 1
fi

function main () {
  cartouche "Intsalling Docker"
  install_docker

  cartouche "Installing Gitlab Runner"
  install_gitlab_runner

  cartouche "Register Gitlab Runner"
  register_gitlab_runner

  cartouche "Programmer le nettoyage"
  schedule_cleanup

  update-ca-certificates
}


function install_gitlab_runner () {
  curl -s -L https://packages.gitlab.com/install/repositories/runner/gitlab-runner/script.deb.sh | bash
  apt-get install -y gitlab-runner
  gitlab-runner start
  adduser gitlab-runner docker
}

function register_gitlab_runner () {
  LOCATION_TAG=$(slugify ${RUNNER_LOCATION})
  timedatectl set-timezone Europe/Paris
  gitlab-runner unregister --all-runners
  gitlab-runner register -n \
     --url https://${GITLAB_HOST}/ \
     --run-untagged=true \
     --tag-list "${TAG_LIST},${LOCATION_TAG}" \
     --registration-token ${GITLAB_RUNNER_TOKEN} \
     --docker-image docker:19.03.12 \
     --executor docker \
     --description "${RUNNER_NAME}" \
     --docker-privileged \
     --docker-volumes "/certs/client" \
     --env "DOCKER_DRIVER=overlay2"

  sed -ri 's/concurrent = .+/concurrent = 2/' /etc/gitlab-runner/config.toml
  service gitlab-runner restart
}

function schedule_cleanup () {
  set +o pipefail
  crontab -l \
   | grep -v '@gitlab-runner-prune' \
   | { cat; echo "0 13,20 * * * docker system prune -f # @gitlab-runner-prune"; } \
   | crontab -
  set -o pipefail
}

function install_docker () {
  apt-get -y install \
       apt-transport-https \
       ca-certificates \
       software-properties-common \
       htop \
       curl

  curl -fsSL https://download.docker.com/linux/debian/gpg | apt-key add -

  add-apt-repository \
     "deb [arch=amd64] https://download.docker.com/linux/debian \
     $(lsb_release -cs) \
     stable"

  apt-get update
  apt-get install docker-ce -y

  cat > /etc/docker/daemon.json <<EOF
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "60m",
    "max-file": "1"
  }
}
EOF

  service docker restart
}

function cartouche () {
  text="$*"
  length=${#text}
  box_length=$((${length} + 2))
  echo -n '╭' && printf '─%.0s' $(seq ${box_length}) && echo '╮'
  echo "│ ${text} │"
  echo -n '╰' && printf '─%.0s' $(seq ${box_length}) && echo '╯'
}

slugify () {
  echo "$1" | iconv -t ascii//TRANSLIT | sed -r s/[^a-zA-Z0-9]+/-/g | sed -r s/^-+\|-+$//g | tr A-Z a-z
}

main "$@"
