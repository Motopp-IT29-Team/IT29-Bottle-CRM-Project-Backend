#!/bin/bash
set -e

# Load environment variables
if [ -f db.env ]; then
    export $(cat db.env | grep -v '^#' | xargs)
fi

# Run migrations
/home/ubuntu/${APP_NAME}/venv/bin/python /home/ubuntu/${APP_NAME}/${APP_NAME}/manage.py migrate

# Start gunicorn
exec /home/ubuntu/${APP_NAME}/venv/bin/gunicorn crm.wsgi:application \
    --bind 0.0.0.0:${PORT:-8000} \
    --workers 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -