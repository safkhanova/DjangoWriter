"""
emailotp/templatetags/emailotp_tags.py

Provides {% t "key" default="English text" %} inside the package's templates,
routed through the project's translation backend (EMAILOTP_TRANSLATE).

Deliberately a separate library from the project's own i18n_db: the package
must not depend on a tag library defined in another app.
"""
from django import template

from ..translation import tr

register = template.Library()


@register.simple_tag(name='t')
def t(key, default=''):
    return tr(key, default)
