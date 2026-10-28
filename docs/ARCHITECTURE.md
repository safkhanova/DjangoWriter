# Architettura

## 1. Stack

| Livello | Scelta | Motivo |
|---|---|---|
| Framework | Django 5.2 LTS, Python 3.13 | LTS fino ad aprile 2028 |
| Admin | django-unfold 0.110 | UI moderna, drag & drop degli inline (`ordering_field`), azioni di riga/dettaglio, editor WYSIWYG (Trix), sidebar configurabile |
| Storico versioni | django-reversion (+ `unfold.contrib.reversion`) | «Tarix» su ogni oggetto: ripristino di versioni precedenti e **recupero degli oggetti eliminati** (funziona da cestino) |
| Login | app `emailotp` (inclusa nel progetto) | staff: password + codice e-mail a 6 cifre |
| DB | PostgreSQL in produzione, SQLite in sviluppo | `DATABASE_URL` via django-environ |
| Immagini | Pillow | conversione in WebP, correzione EXIF e ridimensionamento al salvataggio |
| HTML sicuro | nh3 | whitelist dei tag nel rich text |
| Statici | WhiteNoise | `CompressedManifestStaticFilesStorage` in produzione |
| App server | gunicorn dietro nginx | |

Nessun build step front-end: CSS e JS vanilla in `static/`.

## 2. Struttura del progetto

Il repository contiene solo il codice generico. Tutto ciò che riguarda un sito preciso sta nella
cartella **istanza**, esclusa da git:

```
instance/                 PRIVATA (.gitignore) — un sito
  .env                    segreti e impostazioni (SECRET_KEY, SMTP, SITE_URL, DATABASE_URL…)
  seed.json               struttura iniziale: sezioni e tipi, hero, argomenti, social, impostazioni
  content/*.json, texts/  dati da importare (articoli e loro testi)
  db.sqlite3, media/      database di sviluppo e file caricati (default)
  templates/, static/     opzionali: sovrascrivono template/statici del progetto con lo stesso percorso
  notes/                  appunti privati
instance.example/         PUBBLICA — modello di partenza per un nuovo sito
```

Una stessa cartella di codice può contenere più istanze (`instance<Nome>/`, tutte ignorate da git):
quella attiva si sceglie con la variabile d'ambiente `INSTANCE_DIR` (assoluta o relativa al
progetto) oppure con il file `.instance`, che contiene il nome della cartella; in mancanza di
entrambi si usa `instance/`. `manage.py init_instance`
crea `instance/` dal modello (con un `SECRET_KEY` nuovo), `manage.py setup_site` carica il seed.
I test non usano l'istanza: `tests/runner.py` carica `tests/fixtures/seed.json`.

```
config/            settings, urls, wsgi
core/              impostazioni sito (singleton), Hero, social, contatti, utils condivisi
  design.py        preset di font e colori (scelte curate per l'admin)
  utils.py         az_slugify, ottimizzazione immagini, sanitize_html, is_preview_user
  permissions.py   definizione del gruppo «Redaktor»
  dashboard.py     home dell'admin e badge della sidebar
  translation.py   backend delle traduzioni per emailotp (az)
content/           Section, Category («Növ»), Tag, Article, ArticleBlock, ArticleImage
newsletter/        Subscriber, NewsletterIssue, OutgoingEmail (coda), servizi e comando di invio
emailotp/          login con OTP via e-mail (app inclusa, non modificata)
templates/
  site/            base, home, sezione, articolo, partial, layout delle sezioni (sections/<layout>.html)
  content/blocks/  un template per ogni tipo di blocco (<type>.html)
  emails/          e-mail HTML + testo
  admin/           dashboard, guida blocchi, conferma invio newsletter
  emailotp/        override del login (senza link «Registrati»)
static/css/site.css, static/js/site.js        sito pubblico
static/admin/site_admin.css, block_fields.js   personalizzazioni admin
locale/az/         traduzioni azere delle stringhe di Unfold (che non ha un catalogo az)
tests/             suite di test (+ runner.py e fixtures/seed.json)
instance.example/  modello pubblico di un'istanza (vedi sopra)
```

## 3. Mappa URL

| URL | View | Note |
|---|---|---|
| `/` | `core.views.home` | `?hero=<id>` anteprima di un hero (solo staff); `?movzu=<id>` preseleziona l'argomento nel form contatti |
| `/elaqe/` | `core.views.contact` | solo POST |
| `/abune/` | `newsletter.views.subscribe` | solo POST |
| `/abune/tesdiq/<uuid>/` | conferma iscrizione (double opt-in) | |
| `/abune/<uuid>/` | gestione preferenze / disiscrizione | link presente in ogni e-mail |
| `/abune/<uuid>/imtina/` | one-click unsubscribe RFC 8058 | POST, csrf_exempt |
| `/login/…` | emailotp | `/register/*` → redirect a `/login/` |
| `/<ADMIN_URL>` | Django admin | default `admin/`; `admin/login/` passa per emailotp |
| `/sitemap.xml`, `/robots.txt` | | |
| `/<section>/` | `content.views.section_detail` | `?nov=<category-slug>`, `?page=` |
| `/<section>/<article>/` | `content.views.article_detail` | |

Gli URL delle sezioni sono «catch-all» e vengono **per ultimi** in `config/urls.py`.
`content.models.RESERVED_SLUGS` impedisce che una sezione prenda uno slug di sistema
(`elaqe`, `abune`, `admin`, …).

## 4. Visibilità e anteprima

Regola unica: **lo staff loggato vede tutto, i visitatori solo ciò che è pubblico**
(`core.utils.is_preview_user`).

| Oggetto | Pubblico se | Implementazione |
|---|---|---|
| Section | `is_visible` | `content.models.visible_sections(user)` |
| Article | `status=published` **e** `publish_at <= now` **e** `section.is_visible` | `ArticleQuerySet.public()` / `.visible_for(user)` |
| ArticleBlock | `is_visible` | `Prefetch("blocks", …)` in `article_detail` |
| Hero | `is_active` | `core.views.current_hero` (+ `?hero=` per lo staff) |

In anteprima il template aggiunge `.is-hidden-preview` (bordo tratteggiato giallo, opacità) e i badge
«Qaralama», «Planlaşdırılıb», «Gizli blok», più una barra fissa in alto con «Redaktə et»,
«İdarəetmə paneli», «Çıxış». La barra emette anche `<meta name="robots" content="noindex">`.

La pubblicazione programmata non richiede job: un articolo con `publish_at` futuro è escluso dalla
query fino a quel momento.

## 5. Contenuto a blocchi

Un `Article` ha N `ArticleBlock` ordinati da `order` (drag & drop nell'admin). Una sola tabella con
un discriminatore `type` e campi opzionali, invece del polimorfismo: query semplici, un unico
inline ordinabile e nessuna dipendenza esterna.

`ArticleBlock.FIELDS_BY_TYPE` è la **fonte unica** di quali campi usa ogni tipo:

- viene serializzato nella pagina admin (`json_script`, template `admin/content/blocks_help.html`);
- `static/admin/block_fields.js` mostra solo i campi del tipo scelto (anche per i blocchi aggiunti
  dopo, tramite l'evento `formset:added`);
- `ArticleBlock.clean()` valida i campi obbligatori per tipo.

| type | Campi | Rendering |
|---|---|---|
| `text` | text (rich) | `.prose` |
| `heading` | heading | `h2` |
| `text_image` | heading, text, image, image_alt, caption, image_position (left/right), image_width (20–70%), text_wrap | `text_wrap=True` → `float` con testo che scorre intorno; `False` → griglia a 2 colonne. Larghezza via la variabile CSS `--img-w` |
| `image` | image, alt, caption, position (left/right/center/full), width (20–100%) | float a sinistra/destra, centrata o a tutta larghezza |
| `gallery` | heading | mostra `article.gallery` (inline «Qalereya») |
| `quote` | text, quote_author | |
| `youtube` | youtube_url, caption | embed «lite»: miniatura e iframe `youtube-nocookie.com` caricato solo al clic |
| `audio` | heading, file (mp3/m4a/ogg/wav), caption | `<audio controls>` |
| `pdf` | heading, file (pdf), button_label | box di download |
| `button` | button_label, button_url | URL limitato a `http(s)://`, `mailto:`, `tel:`, `/`, `#` |
| `divider` | — | `hr` |

Sotto i 720px ogni immagine dentro il testo diventa a tutta larghezza (niente float su mobile).

Aggiungere un tipo di blocco: aggiungerlo a `ArticleBlock.Type`, poi a `FIELDS_BY_TYPE` (con
eventuali campi nuovi e la loro migrazione), creare `templates/content/blocks/<type>.html` ed
estendere `clean()` se servono campi obbligatori.

## 6. Layout delle sezioni

`Section.layout` sceglie il template `templates/site/sections/<layout>.html`:

| layout | Aspetto | Usato da |
|---|---|---|
| `featured_list` | card grande (primo articolo) + lista a destra | Ədəbiyyat |
| `card_grid` | griglia di card | PR |
| `table_archive` | tabella Anno / Media / Titolo / Tipo, con filtri per tipo lato client | Media arxivi |
| `dark_media` | video YouTube (se `video_url`) + card testuali, fondo scuro | Koçluq |

**Autorialità.** `Article.authorship` è indipendente da sezione e categoria: un'intervista può stare nel
Media arxivi ma anche in PR o Koçluq. Sul sito i testi suoi non hanno etichetta (caso normale); gli
altri hanno un badge «Müsahibə», «Haqqımda» o «Adım çəkilir» (bordo tratteggiato) (`site/partials/authorship_badge.html`) e la firma
`original_author`. La pagina della sezione offre il filtro `?kim=own|interview|about|mention` solo se la
sezione contiene più di un tipo.

Una sezione nuova si crea solo dall'admin: titolo, layout, sfondo (`theme`), ordine. Nessun codice.
Ordine in home: `homepage_order()` = in evidenza (`is_featured`), poi fissati (`is_pinned`), poi più recenti.
Ordine nella pagina sezione: `listing_order()` = fissati, poi più recenti.

## 7. Design system

- `core/design.py` definisce `FONT_PRESETS` (4 coppie sans + serif di Google Fonts) e `COLOR_PRESETS`
  (5 palette: `accent`, `accent_soft`, `accent_bright`). Il DB salva solo la chiave.
- `site/base.html` scrive le variabili CSS `--font-sans`, `--font-serif`, `--accent*` in `:root`.
- Un Hero può sovrascrivere i font solo per sé (`Hero.font_preset`).
- Volutamente nessun colore o font libero: qualsiasi combinazione resta coerente con il design.

## 8. Immagini e file

`OptimizedImagesMixin.save()` → `optimize_image_field()` per ogni campo in `optimized_image_fields`:
solo per i **nuovi upload** (`_committed=False`): `exif_transpose`, `thumbnail(2400)`, WebP q85.
SVG e GIF restano invariati. Limiti: immagini 15 MB, documenti 30 MB (`MAX_*_UPLOAD_MB`).

## 9. Sicurezza

- Login staff a 2 fattori; `admin.site.login` reindirizza a `emailotp` ([AUTH.md](AUTH.md)).
- Percorso dell'admin configurabile (`ADMIN_URL`, default `admin/`).
- Rich text sanitizzato con nh3 al salvataggio (niente script, stili, iframe; link solo
  http/https/mailto/tel con `rel="noopener noreferrer"`).
- Form pubblici: CSRF, honeypot `website`, rate limit per IP (`core.forms.rate_limited`, 5 ogni 10 min),
  stessa risposta per successo e spam (nessun segnale ai bot).
- Newsletter: double opt-in, token UUID per conferma e gestione, nessuna enumerazione (stesso messaggio
  per chi è già iscritto).
- IP del client letto **solo** da `X-Real-IP` (vedi la guida di emailotp: `X-Forwarded-For` è falsificabile).
- In produzione: `SECURE_SSL_REDIRECT`, cookie sicuri, HSTS configurabile.
- `ATOMIC_REQUESTS=True`.
