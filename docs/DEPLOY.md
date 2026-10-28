# Deploy (server Linux, PostgreSQL)

Esempio per Ubuntu/Debian. Percorsi: codice in `/srv/example.com`, media in
`/var/www/example.com/media`, utente di sistema `site`.

## 1. Pacchetti e database

```bash
sudo apt install python3.13 python3.13-venv postgresql nginx gettext
sudo -u postgres createuser site -P
sudo -u postgres createdb site -O site
```

## 2. Codice e ambiente

```bash
cd /srv/example.com
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
# private site configuration: copy the instance folder from your machine (scp/rsync),
# or create a new one from the template:
.venv/bin/python manage.py init_instance         # instance/ with a fresh SECRET_KEY
nano instance/.env                                # DATABASE_URL, SMTP, SITE_URL, ALLOWED_HOSTS…
nano instance/seed.json                           # sections, hero, contact topics (new sites)
.venv/bin/python manage.py check --deploy
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createcachetable      # cache shared by workers (rate limits)
.venv/bin/python manage.py setup_site            # load instance/seed.json
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py createsuperuser --username you@example.com --email you@example.com
.venv/bin/python manage.py create_editor proprietaria@example.com --name "Ad Soyad"
```

`instance/` non è nel repository: tienine una copia sicura (contiene `.env` con i segreti).
Per tenerla fuori dalla cartella del codice: `INSTANCE_DIR=/etc/site/instance` nell'ambiente
del servizio (systemd `Environment=`). Più siti sullo stesso server: un servizio gunicorn per sito
(porte diverse), ciascuno con il suo `INSTANCE_DIR` e il suo blocco `server` in nginx.
Le traduzioni Unfold sono già compilate (`locale/az/LC_MESSAGES/django.mo`); dopo aver modificato
il `.po`: `manage.py compilemessages -l az` (serve `gettext`).

## 3. gunicorn (systemd)

`/etc/systemd/system/site.service`

```ini
[Unit]
Description=example.com
After=network.target postgresql.service

[Service]
User=site
Group=www-data
WorkingDirectory=/srv/example.com
ExecStart=/srv/example.com/.venv/bin/gunicorn config.wsgi:application \
    --bind 127.0.0.1:8000 --workers 3 --timeout 60 --access-logfile -
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload && sudo systemctl enable --now site
```

## 4. nginx

```nginx
# in the http {} block: max 10 login requests per minute per IP
limit_req_zone $binary_remote_addr zone=login:10m rate=10r/m;

server {
    server_name example.com www.example.com;
    client_max_body_size 32M;          # >= MAX_DOCUMENT_UPLOAD_MB
    server_tokens off;

    location /media/ {
        alias /var/www/example.com/media/;
        expires 30d;
        # Uploaded files are data, never active content: an SVG or a disguised HTML
        # file cannot run scripts on the site's origin.
        add_header X-Content-Type-Options nosniff always;
        add_header Content-Security-Policy "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; sandbox" always;
        location ~* \.(html?|js|xml|php)$ { return 403; }
    }

    # defence in depth: the admin's own password form is never used
    location = /admin/login/ { return 302 /login/; }

    location /login/ {
        limit_req zone=login burst=5 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;          # used by rate limits (do not use X-Forwarded-For)
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

HTTPS: `sudo certbot --nginx -d example.com -d www.example.com`.
Una volta verificato che tutto funziona in HTTPS, attiva HSTS: `SECURE_HSTS_SECONDS=31536000` nel `.env`.
Con un CDN o Cloudflare davanti: `EMAILOTP_IP_HEADER=HTTP_CF_CONNECTING_IP`.
Gli statici li serve WhiteNoise (da gunicorn), non serve un blocco `/static/`.

## 5. Cron

`crontab -u site -e`

```cron
* * * * *  cd /srv/example.com && .venv/bin/python manage.py send_queued_emails >> /var/log/site/mail.log 2>&1
0 4 * * *  cd /srv/example.com && .venv/bin/python manage.py emailotp_cleanup
30 3 * * * /srv/example.com/deploy/backup.sh
```

## 6. Backup

`deploy/backup.sh` (da creare sul server, `chmod +x`):

```bash
#!/bin/sh
set -e
D=/var/backups/site/$(date +%F)
mkdir -p "$D"
pg_dump -Fc site > "$D/db.dump"
tar -czf "$D/media.tgz" -C /var/www/example.com media
tar -czf "$D/instance.tgz" -C /srv/example.com --exclude=instance/media instance   # config, seed, import data
find /var/backups/site -maxdepth 1 -mtime +30 -exec rm -rf {} +
```

Copia i backup anche fuori dal server (rsync o rclone verso un altro storage), cifrati:
`instance.tgz` contiene `.env` con le password.
Ripristino: `pg_restore -c -d site db.dump` e `tar -xzf media.tgz -C /var/www/example.com`.

## 7. Aggiornamenti

```bash
cd /srv/example.com
git pull
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createcachetable
.venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart site
```

## 8. Verifica dopo il deploy

```bash
curl -sI https://example.com/ | head -1                    # 200
curl -sI https://example.com/admin/login/ | head -1    # 302
curl -sI https://example.com/sitemap.xml | head -1         # 200
```

Poi, **prima di uscire da SSH**, fai un login completo all'admin (e-mail → password → codice).
Prova anche: iscrizione alla newsletter (arriva l'e-mail di conferma) e un messaggio dal form contatti
(arriva a `notification_email`).
