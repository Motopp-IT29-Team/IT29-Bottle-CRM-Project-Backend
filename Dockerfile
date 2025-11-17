FROM ubuntu:20.04

# Set default APP_NAME if not provided
ARG APP_NAME=bottle-crm
ENV APP_NAME=${APP_NAME}

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

# Copy and set permissions for entrypoint
COPY --chown=ubuntu:ubuntu entrypoint.sh /home/ubuntu/entrypoint.sh
RUN chmod +x /home/ubuntu/entrypoint.sh

# setup path
ENV PATH="${PATH}:/home/ubuntu/${APP_NAME}/${APP_NAME}/scripts"

# Expose port
EXPOSE $PORT

# Run entrypoint
CMD ["/home/ubuntu/entrypoint.sh"]