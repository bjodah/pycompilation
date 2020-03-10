#!/bin/bash
touch doc/_build/html/.nojekyll
cp LICENSE doc/_build/html/
mkdir -p deploy/public_html/branches/"${DRONE_BRANCH}" deploy/script_queue
cp -r dist/* htmlcov/ examples/ doc/_build/html/ deploy/public_html/branches/"${DRONE_BRANCH}"/
