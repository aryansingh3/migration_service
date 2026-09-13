#!/usr/bin/env python3
"""Progress of the migration run. Reads logs/main.log only - no DB connection. Usage: python3 status.py"""
import os, re, subprocess, time
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(ROOT, "logs", "main.log")
PID = os.path.join(ROOT, "full_run.pid")
strip = lambda s: re.sub(r"\x1b\[[0-9;]*m", "", s)
now_utc = lambda: datetime.now(timezone.utc).replace(tzinfo=None)  # log timestamps are UTC

running, pid = False, None
if os.path.exists(PID):
    pid = open(PID).read().strip()
    running = subprocess.run(["ps", "-p", pid], capture_output=True).returncode == 0
if not running:  # started without a pid file (e.g. in tmux on the server) - find the process by its command line
    found = subprocess.run(["pgrep", "-f", "^[^ ]*python[^ ]* main.py --(run|daily)"], capture_output=True, text=True).stdout.split()
    running, pid = bool(found), (found[0] if found else None)

all_lines = [strip(l) for l in open(LOG, errors="ignore")]
# only the current/latest run: everything after the last "RUN: live" marker
marks = [i for i, l in enumerate(all_lines) if "RUN: live" in l]
lines = all_lines[marks[-1]:] if marks else all_lines
start = [l for l in lines if "RUN: live" in l]
batches = [l for l in lines if re.search(r"batch \d+/\d+", l)]
pauses = [l for l in lines if "paused" in l and "rechecking" in l]
resumes = [l for l in lines if "resumed after" in l]
working = [l for l in lines if "working:" in l]
done = [l for l in lines if "RUN done" in l]
stopped = [l for l in lines if "STOP file found" in l]

print(f"state      : {'RUNNING (pid ' + pid + ')' if running else 'NOT RUNNING'}")
if start:
    t0 = datetime.strptime(start[-1][:23], "%Y-%m-%d %H:%M:%S.%f")
    print(f"started    : {t0} UTC ({(now_utc() - t0).total_seconds() / 60:.0f} min ago)")
if batches:
    last = batches[-1]
    n, total = map(int, re.search(r"batch (\d+)/(\d+)", last).groups())
    deleted = int(re.search(r"'deleted': (\d+)\}\s*\|\s*\d+ rows/s", last).group(1)) if re.search(r"'deleted': (\d+)\}\s*\|\s*\d+ rows/s", last) else 0
    elapsed = (now_utc() - datetime.strptime(start[-1][:23], "%Y-%m-%d %H:%M:%S.%f")).total_seconds()
    eta_h = (elapsed / n * (total - n)) / 3600 if n else 0
    print(f"batches    : {n}/{total} ({100 * n / total:.1f}%)")
    print(f"rows moved : {deleted:,}")
    print(f"rate       : {deleted / max(elapsed, 1):.0f} rows/s overall")
    print(f"eta        : {eta_h:.1f} h left" if running else "eta        : -")
    print(f"last batch : {last[:19]} {last[last.find('batch'):][:120]}")
else:
    print("batches    : none finished yet (still selecting events, or paused)")
if working:
    print(f"progress   : {working[-1][:19]} {working[-1][working[-1].find('working:') + 9:].strip()}")
print(f"pauses     : {len(pauses)} health checks paused, {len(resumes)} resumes")
if pauses:
    print(f"last pause : {pauses[-1][:19]} {pauses[-1][pauses[-1].find('paused'):][:110]}")
for line in (stopped[-1:] + done[-1:]):
    print(f"final      : {line[:19]} {line[line.find(':', 30) + 1:][:140].strip()}")
