#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

exec "$DIR/venv/bin/celery" -A workers.celery_app.celery_app worker --pool=solo --loglevel=info
