#!/bin/bash

set -Eeuo pipefail

sed -i "s/host    all             all             127.0.0.1/32            md5/host    all             all             127.0.0.1/32            trust/g" /etc/postgresql/12/main/pg_hba.conf

PGPASSWORD="$POSTGRES_PASS" psql -d "$POSTGRES_DB" -U "$POSTGRES_USER" -h localhost '--set=ON_ERROR_STOP=true' <<-EOF
	CREATE EXTENSION IF NOT EXISTS postgis;
	CREATE EXTENSION IF NOT EXISTS multicorn;
	CREATE EXTENSION IF NOT EXISTS pg_cron;
	GRANT USAGE ON SCHEMA cron TO postgres;
	DROP SERVER IF EXISTS $FOREIGN_SERVER CASCADE;
EOF

cd /snowplowfdw || exit
python3 setup.py install

cd / || exit
