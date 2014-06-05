#!/bin/bash
source env/bin/activate
pip -q install -r requirements.txt
export WEBAPP_SETTINGS=conf/webapp.default.conf
python webapp.py

