#!/bin/bash
set -euxo pipefail
PKG_NAME=${PKG_NAME:-${CI_REPO_NAME##*/}}

if [[ "$CI_COMMIT_BRANCH" =~ ^v[0-9]+.[0-9]?* ]]; then
    eval export ${PKG_NAME^^}_RELEASE_VERSION=\$CI_COMMIT_BRANCH
fi

SUNDIALS_ROOT=$(compgen -G "/opt-3/sundials-6.*-release")
if [ ! -e $SUNDIALS_ROOT/include/sundials/sundials_config.h ]; then
    >&2 echo "No sundials installation found at: $SUNDIALS_ROOT"
    exit 1
else
    export PYCOMPILATION_TESTING_SUNDIALS_CFLAGS="-isystem ${SUNDIALS_ROOT}/include"
    export PYCOMPILATION_TESTING_SUNDIALS_LDFLAGS="-Wl,--disable-new-dtags -Wl,-rpath,${SUNDIALS_ROOT}/lib -L${SUNDIALS_ROOT}/lib"
fi

source $(compgen -G /opt-3/cpython-v3.*-apt-deb/bin/activate)
( set +e; python3 -c "import sympy" || pip install sympy )
( set +e; python3 -c "import scipy" || pip install scipy )
python3 setup.py sdist
(cd dist/; ${PYTHON:-python3} -m pip install pytest $PKG_NAME-$(${PYTHON:-python3} ../setup.py --version).tar.gz)
(cd /; ${PYTHON:-python3} -m pytest --pyargs $PKG_NAME)
${PYTHON:-python3} -m pip install .[all]
PYTHONPATH=$(pwd) ./scripts/run_tests.sh "$@"
#./scripts/coverage_badge.py htmlcov/ htmlcov/coverage.svg
! grep "DO-NOT-MERGE!" -R . --exclude ci.sh
