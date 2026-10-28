# Testi degli articoli

Metti qui il testo integrale di ogni articolo, un file per articolo, con il nome indicato
(UTF-8, `.md` oppure `.txt`): il nome è lo slug del titolo (es. «Nümunə hekayə» → `numune-hekaye.md`). Poi:

```bash
.venv/bin/python manage.py import_content instance/content/<file>.json
```

Formato:
- riga vuota = nuovo paragrafo; un a capo semplice resta un a capo (utile per le poesie);
- `## Titolo` = sottotitolo;
- `> testo` = citazione;
- `***` = separatore.

Il testo diventa la pagina dell'articolo sul sito. Sotto compare automaticamente il riquadro
«İlk dəfə dərc olunub» / «Mənbə» con il link alla pubblicazione originale.

Un articolo che ha già un testo (importato o scritto nell'admin) non viene sovrascritto;
per sostituirlo usa `--replace-texts`. Senza file la pagina mostra il riassunto e il link alla fonte.

**Diritti:** i propri testi si possono pubblicare; per i testi scritti da altri serve il permesso
della testata, altrimenti si lascia solo riassunto + link (comportamento senza file).
