#!/usr/bin/env bash
set -euo pipefail

: "${ERP_DB_PASSWORD:?Set ERP_DB_PASSWORD before running this script}"
: "${POS_DB_PASSWORD:?Set POS_DB_PASSWORD before running this script}"

sudo -u postgres psql \
  -v erp_password="$ERP_DB_PASSWORD" \
  -v pos_password="$POS_DB_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE hiddenoasis_erp_app LOGIN PASSWORD %L', :'erp_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hiddenoasis_erp_app')\gexec
ALTER ROLE hiddenoasis_erp_app WITH LOGIN PASSWORD :'erp_password';

SELECT format('CREATE ROLE hiddenoasis_pos_app LOGIN PASSWORD %L', :'pos_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hiddenoasis_pos_app')\gexec
ALTER ROLE hiddenoasis_pos_app WITH LOGIN PASSWORD :'pos_password';

SELECT 'CREATE DATABASE hiddenoasis_erp_live OWNER hiddenoasis_erp_app'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'hiddenoasis_erp_live')\gexec

SELECT 'CREATE DATABASE hiddenoasis_pos_live OWNER hiddenoasis_pos_app'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'hiddenoasis_pos_live')\gexec

GRANT ALL PRIVILEGES ON DATABASE hiddenoasis_erp_live TO hiddenoasis_erp_app;
GRANT ALL PRIVILEGES ON DATABASE hiddenoasis_pos_live TO hiddenoasis_pos_app;
SQL

echo "PostgreSQL databases and users are ready."
