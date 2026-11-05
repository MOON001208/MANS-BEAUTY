"""Run the latest review pipeline at most once per Windows calendar day."""
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from shared import CACHE, ROOT


def run_daily(log_dir, command):
    now = datetime.now().astimezone()
    log_dir.mkdir(parents=True, exist_ok=True)
    try:
        # Claim today's run before launching Python. The log doubles as the claim.
        log = (log_dir / f'{now:%Y-%m-%d}.log').open('x', encoding='utf-8')
    except FileExistsError:
        return 0

    with log:
        print(f'Started: {now.isoformat()}', file=log, flush=True)
        try:
            result = subprocess.run(
                command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            )
        except OSError as error:
            print(f'Could not start pipeline: {error}', file=log)
            return 1
        print(f'Finished: {datetime.now().astimezone().isoformat()} (exit {result.returncode})', file=log)
        return result.returncode


if __name__ == '__main__':
    # Task Scheduler launches pythonw to keep the task out of the desktop.
    python = Path(sys.executable).with_name('python.exe')
    raise SystemExit(run_daily(CACHE / 'windows-daily', [
        str(python), '-u', str(ROOT / 'run_pipeline.py'),
        '--latest-only', '--browser', '--write', '--delay', '8',
    ]))
