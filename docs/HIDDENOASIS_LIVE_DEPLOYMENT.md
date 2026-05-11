# Hidden Oasis Live Deployment Guide

This deploys both online copies on one Ubuntu 22.04 server:

```text
/opt/accounting-program-online
/opt/pos-cloud-online
```

Live routing:

```text
https://hiddenoasis.app          -> Accounting frontend
https://hiddenoasis.app/api      -> Accounting backend
https://pos.hiddenoasis.app      -> POS frontend
https://pos.hiddenoasis.app/api  -> POS backend
```

Live PostgreSQL databases:

```text
hiddenoasis_erp_live
hiddenoasis_pos_live
```

POS structure:

```text
POS has its own FastAPI backend, Next.js frontend, PostgreSQL database, and sync worker.
POS is not frontend-only.
POS consumes Accounting APIs at https://hiddenoasis.app/api for catalog/accounting integration.
```

## 1. DNS

Create:

```text
A  hiddenoasis.app      SERVER_PUBLIC_IPV4
A  www.hiddenoasis.app  SERVER_PUBLIC_IPV4
A  pos.hiddenoasis.app  SERVER_PUBLIC_IPV4
```

Add matching `AAAA` records only if the server has IPv6.

## 2. Install Server Packages

```bash
apt update
apt install -y ca-certificates curl gnupg ufw postgresql postgresql-contrib nginx certbot python3-certbot-nginx python3-venv python3-pip build-essential
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable
```

## 3. Create Server User And Persistent Paths

```bash
adduser --system --group --home /opt/hiddenoasis hiddenoasis
mkdir -p /opt/accounting-program-online /opt/pos-cloud-online /etc/hiddenoasis
mkdir -p /var/lib/hiddenoasis/accounting/uploads /var/backups/hiddenoasis/postgres
chown -R hiddenoasis:hiddenoasis /opt/accounting-program-online /opt/pos-cloud-online /var/lib/hiddenoasis
chmod 750 /etc/hiddenoasis
chmod 700 /var/backups/hiddenoasis/postgres
```

Accounting uploads persist at:

```text
/var/lib/hiddenoasis/accounting/uploads
```

## 4. Upload Code

From the workstation:

```bash
rsync -az --delete --exclude '.env' --exclude '.env.*' --exclude 'node_modules' --exclude '.next' --exclude '.venv' --exclude '__pycache__' --exclude '*.db' --exclude '*.tar.gz' /Users/carylmoraleda/accounting-program-online/ root@SERVER_IP:/opt/accounting-program-online/
rsync -az --delete --exclude '.env' --exclude '.env.*' --exclude 'node_modules' --exclude '.next' --exclude '.venv' --exclude '__pycache__' --exclude '*.db' --exclude '*.tar.gz' /Users/carylmoraleda/pos-cloud-online/ root@SERVER_IP:/opt/pos-cloud-online/
```

On the server:

```bash
chown -R hiddenoasis:hiddenoasis /opt/accounting-program-online /opt/pos-cloud-online
```

## 5. PostgreSQL Databases

```bash
ERP_DB_PASSWORD="$(openssl rand -base64 32)"
POS_DB_PASSWORD="$(openssl rand -base64 32)"
cd /opt/accounting-program-online
chmod +x scripts/init-hiddenoasis-databases.sh
ERP_DB_PASSWORD="$ERP_DB_PASSWORD" POS_DB_PASSWORD="$POS_DB_PASSWORD" ./scripts/init-hiddenoasis-databases.sh
```

Expected users:

```text
hiddenoasis_erp_app
hiddenoasis_pos_app
```

Expected databases:

```text
hiddenoasis_erp_live
hiddenoasis_pos_live
```

## 6. Env Files

Create four server env files. Keep them out of code uploads.

Accounting backend:

```bash
cp /opt/accounting-program-online/.env.production.example /etc/hiddenoasis/accounting-backend.env
```

Required values:

```text
ENVIRONMENT=production
DATABASE_URL=postgresql+psycopg://hiddenoasis_erp_app:REAL_ERP_DB_PASSWORD@127.0.0.1:5432/hiddenoasis_erp_live
SECRET_KEY=REAL_ACCOUNTING_SECRET_KEY
ALLOW_DEFAULT_ADMIN_BOOTSTRAP=false
ALLOW_DEMO_SEED=false
INTEGRATION_ENABLED=true
INTEGRATION_SECRET=REAL_SHARED_POS_ACCOUNTING_SECRET
CORS_ORIGINS=https://hiddenoasis.app,https://pos.hiddenoasis.app
UPLOADS_DIR=/var/lib/hiddenoasis/accounting/uploads
TRUST_PROXY_HEADERS=true
```

Accounting frontend:

```bash
cp /opt/accounting-program-online/frontend/.env.production.example /etc/hiddenoasis/accounting-frontend.env
```

```text
NODE_ENV=production
PORT=3100
NEXT_PUBLIC_API_BASE=/api
```

POS backend:

```bash
cp /opt/pos-cloud-online/.env.production.example /etc/hiddenoasis/pos-backend.env
```

Required values:

```text
ENVIRONMENT=production
DATABASE_URL=postgresql+psycopg://hiddenoasis_pos_app:REAL_POS_DB_PASSWORD@127.0.0.1:5432/hiddenoasis_pos_live
SECRET_KEY=REAL_POS_SECRET_KEY
ALLOW_DEFAULT_ADMIN_BOOTSTRAP=false
CORS_ORIGINS=https://pos.hiddenoasis.app
ACCOUNTING_API_BASE=https://hiddenoasis.app/api
ACCOUNTING_INTEGRATION_SECRET=REAL_SHARED_POS_ACCOUNTING_SECRET
ACCOUNTING_INTEGRATION_TOKEN_PATH=/auth/integration/token
RATE_LIMIT_BACKEND=memory
STARTUP_REQUIRE_MIGRATIONS=true
TRUST_PROXY_HEADERS=true
```

POS frontend:

```bash
cp /opt/pos-cloud-online/frontend/.env.production.example /etc/hiddenoasis/pos-frontend.env
```

```text
NODE_ENV=production
PORT=3200
NEXT_PUBLIC_API_BASE=/api
```

Lock env files:

```bash
chown -R root:hiddenoasis /etc/hiddenoasis
chmod 640 /etc/hiddenoasis/*.env
```

Generate app secrets with:

```bash
openssl rand -hex 32
```

The POS `ACCOUNTING_INTEGRATION_SECRET` must exactly match Accounting `INTEGRATION_SECRET`.

## 7. Install Backends

```bash
cd /opt/accounting-program-online/backend
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
chown -R hiddenoasis:hiddenoasis .venv

cd /opt/pos-cloud-online/backend
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
chown -R hiddenoasis:hiddenoasis .venv
```

## 8. Install And Build Frontends

```bash
cd /opt/accounting-program-online/frontend
set -a; . /etc/hiddenoasis/accounting-frontend.env; set +a
npm ci
npm run build
chown -R hiddenoasis:hiddenoasis node_modules .next

cd /opt/pos-cloud-online/frontend
set -a; . /etc/hiddenoasis/pos-frontend.env; set +a
npm ci
npm run build
chown -R hiddenoasis:hiddenoasis node_modules .next
```

## 9. Initialize Schemas

Accounting:

```bash
cd /opt/accounting-program-online/backend
set -a; . /etc/hiddenoasis/accounting-backend.env; set +a
. .venv/bin/activate
python -c "import app.models; from app.db.database import Base, engine; Base.metadata.create_all(bind=engine)"
```

POS:

```bash
cd /opt/pos-cloud-online/backend
set -a; . /etc/hiddenoasis/pos-backend.env; set +a
. .venv/bin/activate
alembic upgrade head
```

## 10. Create Admin Users

Default bootstrap stays disabled in production. Create real admins:

```bash
cd /opt/accounting-program-online/backend
set -a; . /etc/hiddenoasis/accounting-backend.env; set +a
. .venv/bin/activate
python scripts/create_admin.py --username admin --full-name "Hidden Oasis Admin"

cd /opt/pos-cloud-online/backend
set -a; . /etc/hiddenoasis/pos-backend.env; set +a
. .venv/bin/activate
python scripts/create_admin.py --username admin --full-name "Hidden Oasis POS Admin"
```

## 11. Systemd

```bash
cp /opt/accounting-program-online/deploy/systemd/hiddenoasis-accounting-backend.service /etc/systemd/system/
cp /opt/accounting-program-online/deploy/systemd/hiddenoasis-accounting-frontend.service /etc/systemd/system/
cp /opt/pos-cloud-online/deploy/systemd/hiddenoasis-pos-backend.service /etc/systemd/system/
cp /opt/pos-cloud-online/deploy/systemd/hiddenoasis-pos-frontend.service /etc/systemd/system/
cp /opt/pos-cloud-online/deploy/systemd/hiddenoasis-pos-sync-worker.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now hiddenoasis-accounting-backend hiddenoasis-accounting-frontend hiddenoasis-pos-backend hiddenoasis-pos-frontend hiddenoasis-pos-sync-worker
```

Expected services:

```text
postgresql
nginx
hiddenoasis-accounting-backend
hiddenoasis-accounting-frontend
hiddenoasis-pos-backend
hiddenoasis-pos-frontend
hiddenoasis-pos-sync-worker
```

## 12. HTTPS And Nginx

Issue certificates before enabling the final HTTPS config:

```bash
systemctl stop nginx || true
certbot certonly --standalone -d hiddenoasis.app -d www.hiddenoasis.app
certbot certonly --standalone -d pos.hiddenoasis.app
systemctl start nginx
```

Install routing:

```bash
cp /opt/accounting-program-online/deploy/nginx/hiddenoasis.conf /etc/nginx/sites-available/hiddenoasis.conf
ln -sf /etc/nginx/sites-available/hiddenoasis.conf /etc/nginx/sites-enabled/hiddenoasis.conf
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx
```

Expected routing:

```text
hiddenoasis.app/             -> 127.0.0.1:3100
hiddenoasis.app/api/         -> 127.0.0.1:8100
hiddenoasis.app/uploads/     -> /var/lib/hiddenoasis/accounting/uploads
hiddenoasis.app/healthz      -> 127.0.0.1:8100
pos.hiddenoasis.app/         -> 127.0.0.1:3200
pos.hiddenoasis.app/api/     -> 127.0.0.1:8200
pos.hiddenoasis.app/healthz  -> 127.0.0.1:8200
```

## 13. Backups

```bash
cp /opt/accounting-program-online/scripts/backup-hiddenoasis-live.sh /usr/local/sbin/backup-hiddenoasis-live.sh
chmod 750 /usr/local/sbin/backup-hiddenoasis-live.sh
/usr/local/sbin/backup-hiddenoasis-live.sh
```

Daily cron:

```bash
cat >/etc/cron.d/hiddenoasis-postgres-backup <<'CRON'
20 2 * * * root /usr/local/sbin/backup-hiddenoasis-live.sh >> /var/log/hiddenoasis-postgres-backup.log 2>&1
CRON
```

The backup script writes separate dump files for:

```text
hiddenoasis_erp_live
hiddenoasis_pos_live
```

## 14. Smoke Tests

```bash
curl -fsS https://hiddenoasis.app/healthz
curl -fsS https://hiddenoasis.app/healthz/details
curl -fsS https://pos.hiddenoasis.app/healthz
curl -fsS https://pos.hiddenoasis.app/healthz/details
curl -I https://hiddenoasis.app
curl -I https://pos.hiddenoasis.app
```

Accounting UI checks:

1. Log in at `https://hiddenoasis.app`.
2. Confirm dashboard/main page loads.
3. Open **Guests** and confirm the page loads.
4. Open **Bookings** and confirm the page loads.
5. Open **Room Folios** and confirm the page loads.
6. Open **Channel Payouts** and confirm the page loads.
7. Open the Beds24 integration page.
8. Run one Beds24 booking sync for a known booking.
9. Run the same Beds24 booking sync again and confirm it updates/reuses the same local booking instead of duplicating it.
10. Confirm uploads work if attachments are used.

POS checks:

1. Log in at `https://pos.hiddenoasis.app`.
2. Open the POS main screen / terminal.
3. Confirm POS Settings use `https://hiddenoasis.app/api`.
4. Test Accounting connection.
5. Sync catalog.
6. Open a register/session and place a test order.
7. Confirm the POS sync worker pushes to Accounting.

Logs:

```bash
journalctl -u hiddenoasis-accounting-backend -n 100 --no-pager
journalctl -u hiddenoasis-pos-backend -n 100 --no-pager
journalctl -u hiddenoasis-pos-sync-worker -n 100 --no-pager
```

## 15. Future Updates

1. Change and test in local/dev folders.
2. Copy tested changes into the two online folders.
3. Upload online folders to `/opt/...` with `rsync`.
4. Never overwrite `/etc/hiddenoasis/*.env`.
5. Reinstall dependencies if requirements or lockfiles changed.
6. Rebuild frontends with production env loaded.
7. Run POS Alembic migrations.
8. Restart services.

Update commands after upload:

```bash
chown -R hiddenoasis:hiddenoasis /opt/accounting-program-online /opt/pos-cloud-online

cd /opt/accounting-program-online/backend
. .venv/bin/activate
pip install -r requirements.txt

cd /opt/pos-cloud-online/backend
. .venv/bin/activate
pip install -r requirements.txt
set -a; . /etc/hiddenoasis/pos-backend.env; set +a
alembic upgrade head

cd /opt/accounting-program-online/frontend
set -a; . /etc/hiddenoasis/accounting-frontend.env; set +a
npm ci
npm run build

cd /opt/pos-cloud-online/frontend
set -a; . /etc/hiddenoasis/pos-frontend.env; set +a
npm ci
npm run build

systemctl restart hiddenoasis-accounting-backend hiddenoasis-accounting-frontend hiddenoasis-pos-backend hiddenoasis-pos-frontend hiddenoasis-pos-sync-worker
nginx -t && systemctl reload nginx
```

## 16. Production Safety

- Production uses PostgreSQL, not SQLite.
- Accounting and POS use separate live databases.
- Default bootstrap is disabled.
- Accounting demo seed is disabled.
- Accounting is the source of truth for catalog, categories, variants, accounts, receivables, and reports.
- POS connects to Accounting through `https://hiddenoasis.app/api`.
- Keep `/etc/hiddenoasis/*.env` private.
