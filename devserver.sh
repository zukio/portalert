#!/bin/sh
source .venv/bin/activate
python -m flask --app main run -p $PORT --debug
#本番用 waitress-serve --port=$PORT main:app
