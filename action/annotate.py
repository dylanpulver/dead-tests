"""Run deadtests and turn its findings into GitHub annotations.

Called by action.yml with settings in DT_* environment variables. Runs from the
workspace with a relative path, because several scanners skip any path with a
`tmp` or `fixtures` component and an absolute runner path can contain one."""
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

DEADTESTS = Path(__file__).resolve().parent.parent / "deadtests"
# "path:12: msg", "path:12  msg" or "path  [msg]" (a whole-file finding)
FINDING = re.compile(r"^(\S+?)(?::(\d+))?:?\s+(.+)$")


def esc(s, prop=False):
    s = s.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    return s.replace(":", "%3A").replace(",", "%2C") if prop else s


def changed_files():
    """Paths the pull request touches, or None when this is not a pull request."""
    try:
        event = json.load(open(os.environ["GITHUB_EVENT_PATH"]))
        number = event["pull_request"]["number"]
    except (KeyError, OSError, ValueError):
        return None
    api = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    files = set()
    for page in range(1, 31):  # the API stops at 3000 files
        req = urllib.request.Request(
            f"{api}/repos/{os.environ['GITHUB_REPOSITORY']}/pulls/{number}/files?per_page=100&page={page}",
            headers={"Authorization": f"Bearer {os.environ['DT_TOKEN']}", "Accept": "application/vnd.github+json"})
        batch = json.load(urllib.request.urlopen(req))
        files |= {f["filename"] for f in batch}
        if len(batch) < 100:
            break
    return files


def run(args):
    r = subprocess.run([sys.executable, "-I", str(DEADTESTS), *args], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def main():
    root = os.environ.get("DT_PATH") or "."
    checks = os.environ.get("DT_CHECKS", "").replace(",", " ").split()
    changed = changed_files() if os.environ.get("DT_CHANGED_ONLY", "true") == "true" else None
    if changed is None and os.environ.get("DT_CHANGED_ONLY", "true") == "true":
        print("::notice::not a pull request, so reporting findings in every file")

    rc, out = 0, ""
    for name in checks or [None]:
        code, text = run(["run", name, root] if name else ["scan", root])
        rc, out = max(rc, code), out + (f"\n## {name}\n" if name else "") + text
    print("::group::deadtests output\n" + out + "\n::endgroup::")
    if rc:
        print(f"::error::deadtests exited {rc}; see the output above")
        return rc

    check, found = "", []
    for line in out.splitlines():
        if line.startswith("## "):
            check = line[3:].split(":")[0]
            if "skipped" in line:
                print(f"::notice::{esc(line[3:])}")
            continue
        m = FINDING.match(line)
        if not m:
            continue
        path, lineno, msg = m.groups()
        # Most scanners print paths from the workspace, a few from the scan root.
        for candidate in (Path(path), Path(root) / path):
            if candidate.is_file():
                break
        else:
            continue
        rel = os.path.relpath(candidate).replace(os.sep, "/")
        if changed is not None and rel not in changed:
            continue
        found.append((check, rel, lineno, msg.strip()))

    for check, rel, lineno, msg in found:
        where = f"file={esc(rel, True)}" + (f",line={lineno}" if lineno else "")
        print(f"::warning {where},title={esc('dead-tests ' + check, True)}::{esc(msg)}")

    # GitHub shows only 10 warnings per step, so the full list goes in the summary.
    with open(os.environ.get("GITHUB_STEP_SUMMARY", os.devnull), "a") as s:
        s.write(f"### dead-tests: {len(found)} finding(s)\n\n")
        s.writelines(f"- `{rel}{':' + lineno if lineno else ''}` {check}: {msg}\n" for check, rel, lineno, msg in found)
    with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a") as o:
        o.write(f"findings={len(found)}\n")

    if found and os.environ.get("DT_FAIL") == "true":
        print(f"::error::{len(found)} dead-test finding(s)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
