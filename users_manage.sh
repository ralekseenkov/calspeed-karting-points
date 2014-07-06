#!/bin/bash

VENV_NAME='env'
TINYDB_DIR='.db/tinydb'

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

# Run webapp
python users_manage.py $@
