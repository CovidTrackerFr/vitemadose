#!/bin/sh

set -e

cd $1

find -type f -name '*.json' \
  | cut -c3- \
  | sort \
  | xargs du -h \
  | awk 'BEGIN { print "<p>Ressources disponibles</p>\n<ul>"}
               { print "  <li><a href=\"" $2 "\">"$2" ("$1")</a></li>" }
         END   { print "</ul>" }' \
  > index.html
