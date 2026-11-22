from django.core.management.base import BaseCommand
from django.db import DEFAULT_DB_ALIAS, connections

from erp_framework.ledgers import (
    build_ledger_sql,
    create_ledger_views,
    drop_ledger_views,
    ledger_models,
    present_sources,
)


class Command(BaseCommand):
    help = "Drop and recreate the ledger views from the current models."

    def add_arguments(self, parser):
        parser.add_argument("--database", default=DEFAULT_DB_ALIAS)
        parser.add_argument(
            "--sql",
            action="store_true",
            help="Print the CREATE VIEW statements and change nothing.",
        )

    def handle(self, *args, database, sql, verbosity, **options):
        connection = connections[database]
        if sql:
            for ledger in ledger_models():
                present = present_sources(ledger, connection)[0]
                self.stdout.write(build_ledger_sql(ledger, connection, present) + ";\n")
            return
        drop_ledger_views(database)
        created = create_ledger_views(database, verbosity=verbosity, stdout=self.stdout)
        if verbosity >= 1:
            for name, present, _missing in created:
                self.stdout.write(
                    f"Rebuilt {name} over {len(present)} source table(s)."
                )
