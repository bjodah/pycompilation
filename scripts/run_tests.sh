#!/bin/bash -e
# Usage
#   $ ./scripts/run_tests.sh
# or
#   $ ./scripts/run_tests.sh --cov pycompilation --cov-report html
${PYTHON:-python3} -m pytest --doctest-modules --pep8 --flakes $@
python3 -m doctest README.rst
