#!/bin/bash

set -x

INSTANCE="$1"
if [ -z "${INSTANCE}" ]; then
   echo "Must provide instance parameter (e.g. grandprix or pro). Exiting...."
   exit 1
fi

VENV_NAME="env-$INSTANCE"
TINYDB_DIR=".db-$INSTANCE/tinydb"
CONFIG_FILE="conf/config-$INSTANCE.json"
WEBAPP_SETTINGS="conf/webapp.default.conf"

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
pip install -r requirements.txt

# Run webapp
export CONFIG_FILE
export WEBAPP_SETTINGS
./$VENV_NAME/bin/uwsgi -s /tmp/uwsgi-$INSTANCE.sock --manage-script-name --mount /$INSTANCE=wsgi:app --virtualenv ./env-$INSTANCE
