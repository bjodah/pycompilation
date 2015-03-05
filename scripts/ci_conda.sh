#!/bin/bash
# this script assumes conda is in $PATH

export PYTHON_VERSION=$1
export CONDA_PY=$2
export ENV_NAME=$3
export RUN_TESTS=${4:-0}

export CONDA_PATH=$(conda info --system | grep sys.prefix | cut -d: -f2 | sed -e 's/^ *//')
# Incompatible version of libm.so in conda distribution:
conda create --quiet -n $ENV_NAME python=${PYTHON_VERSION} pip sphinx numpy cython
source activate $ENV_NAME
pip install --quiet argh appdirs future joblib pytest-pep8 pytest-cov python-coveralls sphinx_rtd_theme
conda info
find $CONDA_PATH -iname "libm*.so*" -exec rm {} \;
if [[ "$RUN_TESTS" == "1" ]]; then
    PYTHONPATH=$(pwd):$PYTHONPATH \
        LIBRARY_PATH=$CONDA_PATH/envs/$ENV_NAME/lib:$LIBRARY_PATH \
        ./scripts/run_tests.sh
fi
