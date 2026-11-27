from django.core.management.base import BaseCommand
from django.db import DEFAULT_DB_ALIAS, connections

from erp_framework.movements import (
    build_movements_sql,
    create_movement_views,
    drop_movement_views,
    movements_models,
    present_sources,
)


class Command(BaseCommand):
    help = "Drop and recreate the movements_model views from the current models."

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
            for movements_model in movements_models():
                present = present_sources(movements_model, connection)[0]
                self.stdout.write(build_movements_sql(movements_model, connection, present) + ";\n")
            return
        drop_movement_views(database)
        created = create_movement_views(database, verbosity=verbosity, stdout=self.stdout)
        if verbosity >= 1:
            for name, present, _missing in created:
                self.stdout.write(
                    f"Rebuilt {name} over {len(present)} source table(s)."
                )
