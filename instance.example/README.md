# Instance (private site configuration)

`manage.py init_instance` copies this folder to `instance/`, which is ignored by git.
Everything specific to one site lives there:

| File | Purpose |
|---|---|
| `.env` | secrets and settings: `SECRET_KEY`, `SITE_URL`, `ALLOWED_HOSTS`, `DATABASE_URL`, SMTP, `TIME_ZONE`… |
| `seed.json` | initial structure: site name and design, sections with their types, hero, contact topics, social links. Load with `manage.py setup_site`. |
| `content/*.json` | articles to import (`manage.py import_content instance/content/<file>.json`) |
| `content/texts/<slug>.md` | full text of an article (see `content/texts/README.md`) |
| `db.sqlite3`, `media/` | development database and uploaded files (created automatically) |
| `templates/`, `static/` | optional overrides: same relative path as a project file replaces it |
| `notes/` | anything private you want to keep with the site |

Keep a secure backup of the whole folder: it is the only copy of your secrets and data.
