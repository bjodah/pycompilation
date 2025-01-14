#!/bin/bash
set -euxo pipefail
PKG_NAME=${1:-${CI_REPO##*/}}

source $(compgen -G /opt-3/cpython-v3.*-apt-deb/bin/activate)

python3 setup.py sdist
(cd dist/; ${PYTHON:-python3} -m pip install pytest $PKG_NAME-$(${PYTHON:-python3} ../setup.py --version).tar.gz)
(cd /; ${PYTHON:-python3} -m pytest --pyargs $PKG_NAME)
${PYTHON:-python3} -m pip install .[all]
PYTHONPATH=$(pwd) ./scripts/run_tests.sh --cov $PKG_NAME --cov-report html
./scripts/coverage_badge.py htmlcov/ htmlcov/coverage.svg
! grep "DO-NOT-MERGE!" -R . --exclude ci.sh
