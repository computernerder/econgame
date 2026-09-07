"""Read-only source-save migration and one-year release smoke check."""
import copy
import json
import sqlite3
import sys
import tempfile
import time
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from economic_simulation.application import Game
from economic_simulation.domain import Engine


def main():
    source = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory(prefix='empire-release-') as folder:
        target = Path(folder) / 'migration.sqlite3'
        with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as old, closing(sqlite3.connect(target)) as new:
            old.backup(new)
        with closing(sqlite3.connect(target)) as db:
            before = json.loads(db.execute('SELECT data FROM world').fetchone()[0])
            journal = db.execute('SELECT * FROM journal').fetchall()
        game = Game(target)
        try:
            assert all(game.world.accounts[k] == v for k, v in before['accounts'].items())
            assert game.world.date == before['date']
            assert json.loads(json.dumps(game.world.rng_state)) == before['rng_state']
            with closing(sqlite3.connect(target)) as db:
                assert db.execute('SELECT * FROM journal').fetchall() == journal
            started = time.perf_counter()
            for _ in range(365):
                engine = Engine(copy.deepcopy(game.world))
                engine.advance_day()
                game.store.commit(engine, game.world.revision)
                game.world = engine.world
            game.store.audit(game.world)
            print(json.dumps(dict(migration='passed', original_date=before['date'], final_date=game.world.date, days=365, seconds=round(time.perf_counter()-started, 2), migration_backups=len(list(Path(folder).glob('*before-v3*'))), ledger='balanced'), indent=2))
        finally:
            game.close()


if __name__ == '__main__':
    main()
