"""Many towers share desk_brain_journal.json. Saves at the same time must not crash or lose rows."""
import json
import multiprocessing
import os
import tempfile
import threading

import desk_brain


def _write_many(root, bot, n):
    for i in range(n):
        desk_brain.record_decision(root, bot=bot, action="skip", reasons=[f"r{i}"], note="t")


def test_threads_record_without_crash_or_loss():
    with tempfile.TemporaryDirectory() as root:
        errors = []

        def run(bot):
            try:
                _write_many(root, bot, 25)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=run, args=(f"bot{i}",)) for i in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
        data = json.load(open(desk_brain.journal_path(root)))
        assert len(data["decisions"]) == 150
        assert not [f for f in os.listdir(root) if f.endswith(".tmp")]


def test_processes_record_without_crash_or_loss():
    with tempfile.TemporaryDirectory() as root:
        ctx = multiprocessing.get_context("fork")
        procs = [ctx.Process(target=_write_many, args=(root, f"p{i}", 20)) for i in range(4)]
        for p in procs:
            p.start()
        for p in procs:
            p.join(60)
        assert all(p.exitcode == 0 for p in procs)
        data = json.load(open(desk_brain.journal_path(root)))
        assert len(data["decisions"]) == 80


def test_plain_saves_at_once_never_lose_the_temp_file():
    with tempfile.TemporaryDirectory() as root:
        errors = []

        def run():
            try:
                for _ in range(40):
                    desk_brain.save_journal(desk_brain.load_journal(root), root)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=run) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
