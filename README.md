# Writer's site

Sito personale per scrittori e giornalisti: home con hero, sezioni configurabili (letteratura,
articoli, media archive, video…), articoli a blocchi, newsletter per sezione, form contatti,
anteprima delle bozze, login dello staff a due fattori. Tutto si gestisce da un admin Django
(Unfold) pensato per chi non è tecnico.

Interfaccia e testi sono in **azero** (vedi «Lingua» sotto).

## Pubblico e privato

| Dove | Cosa | Git |
|---|---|---|
| tutto il repository | il codice del sito, uguale per tutti | pubblico |
| `instance.example/` | modello di configurazione e di contenuti | pubblico |
| `instance/` | **un sito preciso**: `.env` con i segreti, `seed.json` (sezioni, hero, argomenti…), dati da importare, database e file caricati in sviluppo, eventuali template o CSS personalizzati | **escluso** (`.gitignore`) |

Per un nuovo sito non si tocca il codice: si modifica solo `instance/`.

### Più siti nella stessa cartella

Ogni sito è una cartella `instance<Nome>/` (es. `instanceAlice/`, `instanceBob/`), tutte escluse da
git, ciascuna con il proprio `.env`, database, media e contenuti. Si sceglie quale avviare:

```bash
echo instanceAlice > .instance                 # sito attivo per questa cartella (file ignorato da git)
INSTANCE_DIR=instanceBob .venv/bin/python manage.py runserver 8002   # oppure per un singolo comando
```

Senza `.instance` né `INSTANCE_DIR` si usa `instance/`.

## Nuovo sito in locale

```bash
git clone <repo> mysite && cd mysite
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py init_instance      # crea instance/ da instance.example/ con un SECRET_KEY
# per un nome diverso: INSTANCE_DIR=instanceAlice .venv/bin/python manage.py init_instance
```

Poi modifica `instance/.env` (per lavorare in locale: `DEBUG=True`, `SITE_URL=http://127.0.0.1:8000`,
`ALLOWED_HOSTS=localhost,127.0.0.1`) e `instance/seed.json` (nome del sito, sezioni, hero, argomenti).
Infine:

```bash
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createcachetable
.venv/bin/python manage.py setup_site                         # carica instance/seed.json
.venv/bin/python manage.py createsuperuser                    # username = indirizzo e-mail!
.venv/bin/python manage.py import_content instance/content/example.json --publish   # opzionale
.venv/bin/python manage.py runserver
```

- Sito: <http://127.0.0.1:8000/>
- Admin: <http://127.0.0.1:8000/admin/>, che reindirizza a `/login/` (e-mail → password → codice).
  In sviluppo le e-mail, codice OTP compreso, compaiono nella console di `runserver`.

## Personalizzare senza toccare il codice

- **Dall'admin:** testi, sezioni, tipi, hero (più versioni), font e colori (preset), social,
  argomenti, articoli.
- **`instance/seed.json`:** la struttura di partenza; rilanciare `setup_site` aggiunge ciò che manca
  senza sovrascrivere le modifiche fatte nell'admin (`--overwrite` per forzare).
- **`instance/content/*.json` + `texts/`:** import di articoli in blocco (`import_content`).
- **`instance/templates/…`, `instance/static/…`:** un file con lo stesso percorso di uno del progetto
  lo sostituisce (es. `instance/static/css/site.css`, `instance/templates/site/base.html`).
  Usalo con parsimonia: i file sostituiti non ricevono gli aggiornamenti del progetto.

## Documentazione

| Documento | Contenuto |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Stack, istanza, URL, visibilità/anteprima, blocchi, layout, sicurezza |
| [docs/DATA_MODEL.md](docs/DATA_MODEL.md) | Modelli, campi, vincoli, relazioni |
| [docs/AUTH.md](docs/AUTH.md) | Login a due fattori, sessioni revocabili, permessi |
| [docs/NEWSLETTER.md](docs/NEWSLETTER.md) | Iscritti, double opt-in, coda e-mail, cron |
| [docs/DEPLOY.md](docs/DEPLOY.md) | Server Linux: PostgreSQL, gunicorn, nginx, systemd, cron, backup |
| [docs/SECURITY.md](docs/SECURITY.md) | Revisione di sicurezza e raccomandazioni |
| [docs/ADMIN_GUIDE_AZ.md](docs/ADMIN_GUIDE_AZ.md) | Guida per l'autore/autrice (in azero, non tecnica) |

## Test

```bash
.venv/bin/python manage.py test tests
```

Non usano `instance/`: `tests/runner.py` carica una struttura pubblica (`tests/fixtures/seed.json`)
e un test verifica che `instance.example/` resti sempre importabile.

## Comandi

| Comando | Uso |
|---|---|
| `init_instance` | crea `instance/` da `instance.example/` |
| `setup_site [--seed file] [--overwrite]` | carica la struttura del sito dal seed |
| `import_content <file.json> [--publish] [--dry-run] [--replace-texts]` | importa articoli (e testi) |
| `create_editor <email> [--name ...]` | account staff non superuser (gruppo «Redaktor») |
| `revoke_sessions <email>... \| --all` | logout immediato da tutti i dispositivi |
| `send_queued_emails [--limit N]` | invia la coda e-mail (cron ogni minuto) |
| `emailotp_cleanup` | pulizia codici OTP e log (cron notturno) |

## Lingua

Admin, template ed e-mail sono scritti direttamente in azero, non tramite i file di traduzione:
il sito funziona bene per autori di lingua azera. Per altre lingue servirebbe un passaggio di
internazionalizzazione (`gettext` sulle stringhe e file `.po` per lingua): è il prossimo passo
naturale se il progetto deve servire autori di altri paesi.
