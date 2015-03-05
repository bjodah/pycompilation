#!/bin/bash
# Usage, e.g.:
# ./scripts/run_tests.sh --ignore examples/ --maxfail 1
# see py.test --help for more examples

export PKG_NAME=pycompilation


# Check dependencies for the py.test test command below,
# note that the package itself might depend on more packages
# (see ../requirements.txt)
if ! $PYTHON_EXE -c "import pytest" > /dev/null 2>&1; then
    >&2 echo "Error, could not import pytest, please install pytest."
fi

PYTEST_ARGS=()

# py.test might use either 'python' or 'python3'
PYTHON_EXE=$(head -1 $(which py.test) | cut -f2 -d!)
echo "Python executable used: $PYTHON_EXE, output of $PYTHON_EXE --version:"
$PYTHON_EXE --version


if ! $PYTHON_EXE -c "import pytest_pep8" > /dev/null 2>&1; then
    echo "Could not import pytest_pep8, install pytest-pep8 if you want it."
else
    PYTEST_ARGS+=(--pep8)
fi

if ! $PYTHON_EXE -c "import pytest_cov" > /dev/null 2>&1; then
    echo "Could not import pytest_cov, install pytest-cov if you want it."
else
    PYTEST_ARGS+=(--cov $PKG_NAME --cov-report html)
fi

echo "About to run the full test suite. It can take several minutes..."
set -xe  # bash: echo commands, exit on failure
py.test ${PYTEST_ARGS[@]} $@
