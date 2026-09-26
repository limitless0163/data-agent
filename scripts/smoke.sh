#!/bin/sh
set -eu

curl --fail --silent --show-error http://localhost:8080/ > /dev/null
docker compose exec -T backend python -c 'import json, urllib.request; spec = json.load(urllib.request.urlopen("http://127.0.0.1:8000/openapi.json", timeout=10)); assert "/api/query" in spec["paths"]'
status=$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' --header 'Content-Type: application/json' --data '{}' http://localhost:8080/api/query)
[ "$status" = 422 ]
echo 'Frontend and backend HTTP checks passed.'
