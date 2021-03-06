#!/bin/bash

set -x

INSTANCE=""
if [ -z "${INSTANCE}" ]; then
   echo "Must provide instance parameter (e.g. grandprix or pro). Exiting...."
   exit 1
fi

VENV_NAME="env-$INSTANCE"
TINYDB_DIR=".db-$INSTANCE/tinydb"
CONFIG_FILE="conf/config-$INSTANCE.json"

# Create virtual env if it doesn't exist
if [ ! -d "$VENV_NAME" ]; then
  virtualenv $VENV_NAME
fi

# Create database directory if it doesn't exist
if [ ! -d "$TINYDB_DIR" ]; then
  mkdir -p $TINYDB_DIR
fi

# Activate virtual env
source $VENV_NAME/bin/activate

# Install dependencies
pip -q install -r requirements.txt

# Run user management utility
export CONFIG_FILE
python users_manage.py $@
