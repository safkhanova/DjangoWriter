"""Test runner that loads a public site structure (tests/fixtures/seed.json) into the test DB.

Site-specific data lives in the private instance folder, so tests must not depend on it.
"""

from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test.runner import DiscoverRunner

SEED = Path(__file__).parent / "fixtures" / "seed.json"


class SeededTestRunner(DiscoverRunner):
    def setup_databases(self, **kwargs):
        config = super().setup_databases(**kwargs)
        call_command("import_content", str(SEED), "--publish", stdout=StringIO())
        return config
