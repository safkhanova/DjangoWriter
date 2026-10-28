# Autenticazione e permessi

## Login a due fattori (app `emailotp`)

L'app è inclusa **senza modifiche** nella cartella `emailotp/` (la sua guida è in
`emailotp/email_otp_guide.md`). Questo progetto la configura così:

```
/login/            e-mail
   └─ staff → /login/password/   password (via authenticate())
                 └─ codice a 6 cifre inviato per e-mail → /login/verify/  → admin
```

| Impostazione | Valore | Perché |
|---|---|---|
| `EMAILOTP_STAFF_REQUIRE_PASSWORD` | `True` | password **e** codice = 2 fattori |
| `EMAILOTP_LOOKUP_FIELD` | `username` (default) | **lo username deve essere l'indirizzo e-mail** |
| `EMAILOTP_ACTIVATE_EXISTING_INACTIVE` | `False` | un utente disattivato non può riattivarsi da solo |
| `EMAILOTP_REGISTER_COLLECT_PASSWORD` | `False` | |
| `EMAILOTP_REMEMBER_AGE` | 30 giorni | casella «yadda saxla»; senza casella valgono 12 ore |
| `SESSION_COOKIE_AGE` | 12 ore | |
| `EMAILOTP_TRANSLATE` | `core.translation.translate` | testi azeri da `emailotp_translations.py` |
| `EMAILOTP_BASE_TEMPLATE` | `site/auth_base.html` | pagine di login con la grafica del sito |
| `EMAILOTP_IP_HEADER` | `HTTP_X_REAL_IP` | in nginx: `proxy_set_header X-Real-IP $remote_addr;` |
| `LOGIN_REDIRECT_URL` | `admin:index` | |

Integrazione in `config/urls.py`:

- `admin.site.login = staff_member_required(admin.site.login, login_url="emailotp:login")`: il form
  password di Django admin (che salterebbe il codice) non è raggiungibile.
- `/register/`, `/register/verify/`, `/register/resend/` → redirect a `/login/`: il sito non ha
  account pubblici. Override di `templates/emailotp/login.html` senza il link «Registrati».

> ⚠ **Prima di chiudere la sessione SSH dopo il deploy** fai un login completo. Se l'SMTP non
> funziona il codice non arriva e l'admin resta inaccessibile. Rimedio: `manage.py shell` →
> correggi la configurazione e-mail; la coda `OutgoingEmail` non c'entra (i codici OTP partono
> direttamente con `send_mail`).

## Sessioni e revoca (logout immediato)

Le sessioni sono **nel database** (`SESSION_ENGINE = ...backends.db`, obbligatorio). Ogni login crea
una riga `core.UserSession` (utente, chiave di sessione, IP, browser, ora di login e ultima attività),
tramite il segnale `user_logged_in`. `SessionActivityMiddleware` aggiorna `last_seen_at` al massimo ogni
5 minuti e traccia anche le sessioni nate prima di questa funzione.

**Revocare** = cancellare la riga `django_session`: il cookie rubato non punta più a niente e la
richiesta successiva è anonima, quindi il logout è immediato.

| Chi | Dove | Effetto |
|---|---|---|
| Qualsiasi staff | Admin → «Aktiv sessiyalar» | vede **solo le proprie** sessioni (dispositivo, IP, ultima attività; «Bu cihaz» = quella corrente) |
| | bottone «Digər bütün cihazlardan çıx» | revoca tutte le proprie sessioni **tranne quella corrente** |
| | azione «Seçilmiş sessiyaları ləğv et» | revoca le sessioni selezionate |
| Superuser | Utenti → utente → «Bütün cihazlardan çıxış et» (anche come azione sulla lista) | revoca tutte le sessioni di quell'utente |
| Da SSH | `manage.py revoke_sessions <email> [...]` | come sopra, senza bisogno dell'admin |
| | `manage.py revoke_sessions --all` | logout di **tutti** gli utenti |

`revoke_user_sessions()` trova anche le sessioni non tracciate decodificando le sessioni attive.

### Procedura in caso di account compromesso

1. Revoca tutte le sessioni dell'utente (admin oppure `revoke_sessions <email>`).
2. Cambia la password: Django invalida anche così le altre sessioni (session auth hash), e senza
   password l'attaccante non supera il primo fattore.
3. Se la casella e-mail è compromessa, cambia anche quella password: l'e-mail è il secondo fattore.
4. In alternativa temporanea: disattiva l'utente (`is_active=False`), che blocca ogni accesso.
5. Controlla «Tarix» (django-reversion) per vedere cosa è stato modificato e ripristina.

## Account

| Account | Come si crea | Accesso |
|---|---|---|
| Superuser (sviluppatore) | `createsuperuser --username <email> --email <email>` | tutto, compresi utenti, gruppi, coda e-mail, codice analytics, log OTP |
| Redattrice (proprietaria del sito) | `manage.py create_editor <email> --name "…"` | gruppo «Redaktor» |


Creando utenti dall'admin, `UserAdmin` mette in minuscolo lo username e, se contiene `@`, copia il
valore anche in `email`. Il campo username mostra l'avviso che deve essere un'e-mail.

## Gruppo «Redaktor»

Definito in `core/permissions.py` (`EDITOR_PERMISSIONS`), creato dalla migrazione di seed.
Dopo una modifica: `manage.py shell -c "from core.permissions import sync_editor_group; sync_editor_group()"`.

| Area | Permessi |
|---|---|
| Section | view, add, change (niente delete, per sicurezza: si nasconde con `is_visible`) |
| Category, Tag, Article, ArticleBlock, ArticleImage | tutti |
| SiteSettings | view, change (senza il fieldset «Texniki») |
| Hero, HeroTag, SocialLink, ContactTopic | tutti |
| ContactMessage | view, change, delete |
| Subscriber | view, change, delete |
| NewsletterIssue | view, add (`add` = può usare «Abunəçilərə göndər») |

Nessun accesso a: User, Group, OutgoingEmail, EmailOTP, AuthEvent.
«Aktiv sessiyalar» è aperta a tutto lo staff (permessi nel `UserSessionAdmin`, queryset limitato alle proprie righe).
La sidebar di Unfold mostra le voci in base a `has_perm`; la sezione «Texniki» solo al superuser.
