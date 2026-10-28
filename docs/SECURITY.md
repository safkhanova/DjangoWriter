# Revisione di sicurezza (28.10.2026)

Ambito: codice del progetto (config, core, content, newsletter), integrazione di `emailotp`,
template, upload, e-mail, configurazione di deploy, dipendenze.
Metodo: lettura del codice, `check --deploy` in configurazione di produzione, `pip-audit`, test
di verifica scritti per riprodurre ogni problema prima di correggerlo. Tutte le correzioni sono
coperte da test in `tests/test_security.py` (68 test in totale, tutti passano).

## Risultato in breve

| # | Gravità | Problema | Stato |
|---|---|---|---|
| 1 | **Alta** | Azioni admin che cambiano stato eseguibili con un semplice GET (CSRF): attivare un hero, revocare le sessioni | Corretto |
| 2 | **Alta** | Passaggio password del login staff senza limite di tentativi (brute force illimitato) | Corretto |
| 3 | **Alta** | Logo e favicon accettavano qualsiasi file (HTML o SVG con script serviti dallo stesso dominio → XSS persistente) | Corretto |
| 4 | Media | `SECRET_KEY` con valore di riserva noto anche in produzione | Corretto |
| 5 | Media | Nessuna Content-Security-Policy sul sito pubblico | Corretto |
| 6 | Media | Form contatti: messaggio senza limite di lunghezza, corpo della richiesta fino a 30 MB | Corretto |
| 7 | Media | Rate limit in memoria del singolo processo (moltiplicato per il numero di worker gunicorn) | Corretto |
| 8 | Bassa | Export CSV degli iscritti vulnerabile a «CSV injection» (nomi dal form pubblico) | Corretto |
| 9 | Bassa | Nome del mittente con a capo nell'oggetto dell'e-mail di notifica | Corretto |
| 10 | Bassa | Link dei bottoni accettavano `//dominio` (link esterno travestito da relativo) | Corretto |
| 11 | Bassa | Articoli con molti blocchi: limite di 1000 campi per richiesta | Corretto |

Dipendenze: `pip-audit` → nessuna vulnerabilità nota (Django 5.2.18, Unfold 0.110, Pillow 13.0, …).

## Dettaglio delle correzioni

**1. CSRF sulle azioni admin.** Le azioni «dettaglio» e «riga» di Unfold sono link (GET). Un
sito esterno poteva farle eseguire nel browser di un admin loggato (anche il cookie SameSite=Lax
viene inviato nella navigazione GET). Ora `core/admin_confirm.py::confirm_then` mostra una
pagina di conferma con GET ed esegue solo con un POST verificato dal token CSRF. Si applica ad
«Aktiv et» (hero), «Bütün cihazlardan çıxış et» (utente) e «Digər bütün cihazlardan çıx»
(sessioni). «Abunəçilərə göndər» funzionava già così. Le azioni di sola lettura («Önizlə»,
«Saytda bax») restano link.

**2. Brute force sulla password.** `emailotp` limita i tentativi sul codice ma non sul form
password. Senza modificare l'app, `core/auth_guard.py` intercetta `/login/password/`: dopo
10 errori in un'ora per account, o 30 per IP, rifiuta anche la password giusta per il resto
dell'ora (evento `THROTTLED` nell'audit). Compromesso consapevole: un attaccante può bloccare
l'account per un'ora, ma non indovinare la password. In più c'è `limit_req` di nginx su `/login/`
(vedi DEPLOY).

**3. Upload.** Logo: png/jpg/jpeg/webp/svg; favicon: ico/png/svg; gli SVG con `<script>`,
`on…=`, `javascript:`, `<foreignObject>`, `<iframe>`, `<embed>`, `<object>` vengono rifiutati.
Seconda difesa in nginx: i file in `/media/` hanno `Content-Security-Policy: … sandbox` e
`nosniff`, e `.html/.js/.xml/.php` danno 403. Le immagini sono già ricodificate in WebP e i
file dei blocchi hanno una whitelist di estensioni.

**4. SECRET_KEY.** Con `DEBUG=False` l'avvio fallisce se manca nel `.env`.

**5. CSP e header** (`core/security.py`, solo pagine pubbliche: l'admin di Unfold usa script inline):
`default-src 'self'`, script solo dal proprio dominio (+ `CSP_EXTRA_SCRIPT_SRC` per gli analytics),
Google Fonts, miniature e iframe YouTube (`youtube-nocookie`), `object-src 'none'`,
`frame-ancestors 'none'`, `form-action 'self'`, `base-uri 'self'`. Inoltre `Permissions-Policy`,
in produzione `Cross-Origin-Opener-Policy: same-origin` e cookie CSRF `HttpOnly`.
Lo snippet analytics deve caricare uno script esterno: quelli inline vengono bloccati.

**6–7.** Messaggio limitato a 5000 caratteri; `DATA_UPLOAD_MAX_MEMORY_SIZE` = 5 MB (i file sono
esclusi); cache su database condivisa dai worker (`createcachetable`).

**8–11.** `csv_safe()` antepone `'` alle celle che iniziano con `= + - @`; il nome nell'oggetto
viene ridotto a una riga; `is_safe_link()` esclude `//`; `DATA_UPLOAD_MAX_NUMBER_FIELDS` = 10000.

## Verificato e già corretto

- **Autenticazione:** staff = password + codice e-mail (2FA); il form password di Django admin è
  disattivato; registrazione pubblica disattivata; codici OTP salvati come hash, 5 tentativi per
  codice, limiti per e-mail e per IP; nessun `next=` (niente open redirect).
- **Sessioni:** su database, revocabili (logout immediato), 12 h o 30 giorni con «ricordami»;
  cookie `Secure`, `HttpOnly`, `SameSite=Lax`; la sessione viene rigenerata al login.
- **Permessi:** il gruppo «Redaktor» non ha accesso a utenti, gruppi, coda e-mail, log OTP né al
  campo analytics (verificato con test); le sessioni sono visibili solo al proprietario.
- **XSS:** autoescape dei template; rich text sanitizzato con nh3 al salvataggio (script,
  attributi `on…` e `javascript:` rimossi, verificato con test); gli unici `|safe` riguardano HTML
  sanitizzato, preset fissi di font e lo snippet analytics (solo superuser); i dati JSON passano
  da `json_script`; il JS non usa `innerHTML`.
- **Iniezioni:** solo ORM, nessun SQL raw; i parametri `?kim`, `?nov`, `?hero`, `?movzu`
  vengono validati.
- **Contenuti non pubblici:** bozze, articoli programmati e sezioni nascoste danno 404 e sono
  esclusi da home, liste e sitemap (verificato con test).
- **Newsletter:** double opt-in, token UUID4, nessuna enumerazione degli iscritti, one-click
  unsubscribe (unico `csrf_exempt`, agisce solo tramite token).
- **Host header:** `ALLOWED_HOSTS`; i link nelle e-mail usano `SITE_URL`, non l'header Host.
- **Proxy:** IP letto solo da `X-Real-IP` (impostato da nginx); gunicorn ascolta solo su 127.0.0.1.
- **Segreti:** tutto ciò che è privato sta in `instance/` (`.env` con permessi 600), esclusa da git;
  nessun segreto nel codice.

## Azioni consigliate (non nel codice)

1. **Password:** non scrivere mai le password dello staff in chat, ticket o file del repository;
   se è successo, cambiarle (admin → Utenti → «Şifrəni dəyiş»).
2. **E-mail del sito:** meglio una casella dedicata (es. `noreply@example.com`) o un provider
   transazionale invece della casella personale: se il server viene compromesso, l'attaccante
   ottiene le credenziali SMTP.
3. **Casella e-mail dello staff:** tenere attiva la verifica in 2 passaggi, perché l'e-mail è il
   secondo fattore dell'admin.
4. **HSTS:** `SECURE_HSTS_SECONDS=31536000` dopo aver verificato HTTPS.
5. **Server:** aggiornamenti automatici (`unattended-upgrades`), firewall (solo 22/80/443),
   SSH solo con chiave, fail2ban sull'SSH; backup cifrati e copiati fuori dal server.
6. **Aggiornamenti:** `pip-audit -r requirements.txt` a ogni deploy; aggiornare Django alle patch 5.2.x.
7. **Monitoraggio:** controllare periodicamente «Aktiv sessiyalar» e il log `AuthEvent`
   (tentativi `throttled` / `verify_fail`).

## Rischi residui accettati

- Il primo passo del login rivela se un indirizzo è staff (limite noto di `emailotp`).
- Il blocco per account (punto 2) permette a un attaccante di bloccare il login per un'ora.
- Lo staff vede tutte le bozze: è voluto (anteprima).
- La CSP pubblica permette `style-src 'unsafe-inline'` (necessario per i token di design e la
  larghezza delle immagini); gli script inline restano bloccati.
