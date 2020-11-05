#!/bin/bash

set -Eeuo pipefail


PGPASSWORD="$POSTGRES_PASS" psql -d "$POSTGRES_DB" -U "$POSTGRES_USER" -h localhost '--set=ON_ERROR_STOP=true' <<-EOF
	CREATE EXTENSION IF NOT EXISTS postgis;
	CREATE EXTENSION IF NOT EXISTS multicorn;
	DROP SERVER IF EXISTS $FOREIGN_SERVER CASCADE;
EOF

cd /snowplowfdw || exit
python3 setup.py install

cd / || exit
