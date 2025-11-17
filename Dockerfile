FROM ubuntu:20.04

# Set default APP_NAME
ARG APP_NAME=bottle-crm
ENV APP_NAME=${APP_NAME}

# Install system packages
RUN apt-get update -y
RUN apt-get install -y \
  python3-pip \
  python3-venv \
  build-essential \
  libpq-dev \
  libmariadbclient-dev \
  libjpeg62-dev \
  zlib1g-dev \
  libwebp-dev \
  curl  \
  vim \
  net-tools

# Setup user
RUN useradd -ms /bin/bash ubuntu
USER ubuntu

# Install app
RUN mkdir -p /home/ubuntu/"${APP_NAME}"/"${APP_NAME}"
WORKDIR /home/ubuntu/"${APP_NAME}"/"${APP_NAME}"
COPY --chown=ubuntu:ubuntu . .
RUN python3 -m venv ../venv
RUN . ../venv/bin/activate
RUN /home/ubuntu/"${APP_NAME}"/venv/bin/pip install -U pip
RUN /home/ubuntu/"${APP_NAME}"/venv/bin/pip install -r requirements.txt
RUN /home/ubuntu/"${APP_NAME}"/venv/bin/pip install gunicorn

# Copy production env
RUN cp db.env.production db.env || true

# Setup path
ENV PATH="${PATH}:/home/ubuntu/${APP_NAME}/${APP_NAME}/scripts"

# Expose port
EXPOSE 10000

# Run migrations and start gunicorn
CMD /home/ubuntu/bottle-crm/venv/bin/python /home/ubuntu/bottle-crm/bottle-crm/manage.py migrate --noinput && \
    echo "Migrations completed, starting gunicorn..." && \
    /home/ubuntu/bottle-crm/venv/bin/gunicorn crm.wsgi:application \
    --bind 0.0.0.0:$PORT \
    --workers 2 \
    --timeout 120 \
    --log-level debug \
    --access-logfile - \
    --error-logfile -