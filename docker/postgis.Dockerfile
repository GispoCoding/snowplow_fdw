ARG IMAGE_VERSION=12.4

FROM postgres:$IMAGE_VERSION

RUN apt-get update && apt-get -y install git build-essential postgresql-server-dev-12

RUN git clone https://github.com/citusdata/pg_cron.git
RUN cd pg_cron && make && make install

FROM kartoza/postgis:$IMAGE_VERSION
MAINTAINER gispo<info@gispo.fi>

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    git \
    python \
    python3 \
    python3-dev \
    python3-pip \
    pgxnclient \
    && apt clean

WORKDIR /

RUN pip3 install -q setuptools

# Install Multicorn for Foreign Data Wrappers
RUN pgxn install multicorn

# Install plpygis for Foreign Data Wrapper support for Postgis
RUN pip3 install plpygis

WORKDIR /

COPY dev_install.sh /scripts/dev_install.sh
RUN chmod +x /scripts/dev_install.sh