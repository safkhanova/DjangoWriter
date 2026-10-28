"""Translation backend for the emailotp app (EMAILOTP_TRANSLATE). The site is Azerbaijani-only."""

from emailotp.emailotp_translations import EMAILOTP_TRANSLATIONS


def translate(key: str, default: str = "") -> str:
    return EMAILOTP_TRANSLATIONS.get(key, {}).get("az") or default or key
