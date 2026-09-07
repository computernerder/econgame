"""Reproducible small-portfolio benchmark; not a target-scale employee claim."""
import copy
import json
import os
import platform
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from economic_simulation.application import Game
from economic_simulation.domain import Engine


def main():
    with tempfile.TemporaryDirectory(prefix="empire-benchmark-") as folder:
        game = Game(Path(folder) / "benchmark.sqlite3")
        for index in (0, 3, 5):
            pid = game.world.properties[index].id
            game.execute("buy", {"property_id": pid}, game.world.revision, f"benchmark-buy-{pid}")
            game.execute("rent", {"property_id": pid}, game.world.revision, f"benchmark-rent-{pid}")
        started = time.perf_counter()
        for _ in range(365):
            engine = Engine(copy.deepcopy(game.world))
            engine.advance_day()
            game.store.commit(engine, game.world.revision)
            game.world = engine.world
        duration = time.perf_counter() - started
        game.store.audit(game.world)
        samples = []
        for _ in range(20):
            start = time.perf_counter()
            game.view()
            samples.append((time.perf_counter() - start) * 1000)
        samples.sort()
        print(json.dumps({"python": sys.version.split()[0], "os": platform.platform(), "processor": os.environ.get("PROCESSOR_IDENTIFIER", platform.machine()), "logical_cpus": os.cpu_count(), "fixture": "seed 42; 3 owned properties with tenant searches; 0 employees; 365 daily SQLite commits; benchmark continues through decision events", "seconds_per_year": round(duration, 3), "read_model_p50_ms": round(samples[10], 3), "read_model_p95_ms": round(samples[18], 3), "save_bytes": game.store.path.stat().st_size, "ledger_audit": "passed"}, indent=2))
        game.close()


if __name__ == "__main__":
    main()
