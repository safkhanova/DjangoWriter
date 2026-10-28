# Iscritti e newsletter

## Flusso di iscrizione (double opt-in)

1. Il visitatore compila il box «Abunə ol» (`#abune` in home): e-mail, nome opzionale, sezioni di interesse.
   Nessuna sezione selezionata = riceve tutto.
2. `POST /abune/` → `Subscriber` creato o aggiornato con `is_confirmed=False`, poi
   `services.send_confirmation()` invia subito (tramite la coda) l'e-mail con `/abune/tesdiq/<token>/`.
3. Il clic conferma (`is_confirmed=True`, `confirmed_at`).
4. Ogni e-mail contiene il link `/abune/<token>/` (cambio sezioni o disiscrizione) e gli header
   `List-Unsubscribe` + `List-Unsubscribe-Post` che puntano a `/abune/<token>/imtina/` (bottone
   «Annulla iscrizione» nativo di Gmail e Apple Mail).

Antispam: honeypot, rate limit 5 tentativi ogni 10 min per IP, risposta identica per gli indirizzi
già iscritti (nessuna enumerazione).

## Invio di un articolo

Nell'admin, pagina dell'articolo → bottone **«Abunəçilərə göndər»** → pagina di conferma con il numero
di destinatari → «Bəli, göndər».

`services.queue_article_newsletter(article, user)`:

- rifiuta se l'articolo non è pubblico (bozza, programmato o sezione nascosta);
- rifiuta se esiste già un `NewsletterIssue` per l'articolo (OneToOne: mai due invii);
- crea un `NewsletterIssue` e un `OutgoingEmail` per ogni iscritto di
  `Subscriber.objects.interested_in(article.section)` (attivi **e** che hanno scelto quella sezione
  oppure nessuna sezione).

L'invio non avviene nella richiesta web (con molti iscritti andrebbe in timeout).

## Coda

`manage.py send_queued_emails` (cron ogni minuto) invia al massimo `NEWSLETTER_BATCH_SIZE`
(default 100) e-mail `pending` per esecuzione, dalla più vecchia. Ogni errore incrementa `attempts`;
al terzo l'e-mail passa a `failed`. Il superuser può rimetterle in coda dall'admin
(«E-poçt növbəsi» → «Xətalıları yenidən növbəyə qoy»).

Con un provider con limiti orari (es. 500 al giorno) regola `NEWSLETTER_BATCH_SIZE` e la frequenza del cron.

Le e-mail transazionali (conferma iscrizione, notifica dei contatti) passano anch'esse per la coda ma
vengono tentate subito; se l'SMTP non risponde restano `pending` e il cron le ritenta.

I codici OTP del login **non** passano per la coda (li invia `emailotp` direttamente).

## Template

`templates/emails/new_article.{html,txt}`, `confirm_subscription.*`, `contact_notification.*`,
tutti basati su `emails/base.html` (HTML a tabelle, stili inline, colore accent del sito).

## Privacy

Si salvano solo e-mail, nome opzionale, sezioni e date. L'admin permette di esportare in CSV o
disiscrivere. Per la cancellazione definitiva (diritto all'oblio) si elimina la riga.
