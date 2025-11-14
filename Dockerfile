FROM ubuntu:20.04

# invalidate cache
ARG APP_NAME

# test arg
RUN test -n "$APP_NAME"

# install system packages
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

# setup user
RUN useradd -ms /bin/bash ubuntu
USER ubuntu

# install app
RUN mkdir -p /home/ubuntu/"$APP_NAME"/"$APP_NAME"
WORKDIR /home/ubuntu/"$APP_NAME"/"$APP_NAME"
COPY --chown=ubuntu:ubuntu . .
RUN python3 -m venv ../venv
RUN . ../venv/bin/activate
RUN /home/ubuntu/"$APP_NAME"/venv/bin/pip install -U pip
RUN /home/ubuntu/"$APP_NAME"/venv/bin/pip install -r requirements.txt
RUN /home/ubuntu/"$APP_NAME"/venv/bin/pip install gunicorn

# setup path
ENV PATH="${PATH}:/home/ubuntu/$APP_NAME/$APP_NAME/scripts"

# Expose port
EXPOSE 10000

# Run migrations and start gunicorn
CMD /home/ubuntu/"$APP_NAME"/venv/bin/python /home/ubuntu/"$APP_NAME"/"$APP_NAME"/manage.py migrate && \
    /home/ubuntu/"$APP_NAME"/venv/bin/gunicorn crm.wsgi:application \
    --bind 0.0.0.0:$PORT \
    --workers 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -