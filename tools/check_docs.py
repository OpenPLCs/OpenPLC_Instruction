"""Every check that guards this repo's documents, in one run.

    python tools/check_docs.py

Runs P7, P8, P9, P13 and P18, then a summary. P7, P9 and P13 also read the code
repos beside this one; a repo not cloned is skipped by name, not failed.

Exit 0 = all pass, 1 = any failed.
"""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from _doccheck_common import Fail, Ok, Section  # noqa: E402

# (id, what it proves, script and arguments)
STEPS = [
    ("P7", "every cited case is defined, and every defined case is cited", ["check_status_sync.py"]),
    ("P8", "no claim is written out in more than one document", ["check_doc_dupes.py"]),
    ("P9", "every path a document names actually exists", ["check_doc_paths.py"]),
    ("P13", "no renamed id is still cited anywhere", ["check_no_stale_ids.py"]),
    ("P18", "the live-id table in ID-MAP.md is up to date", ["gen_id_map.py", "--check"]),
]


def main():
    results = []
    for step, what, argv in STEPS:
        Section("%s  %s" % (step, what))
        sys.stdout.flush()
        rc = subprocess.call([sys.executable, str(HERE / argv[0])] + argv[1:], cwd=str(HERE.parent))
        results.append((step, what, rc))
        (Ok if rc == 0 else Fail)("PASS" if rc == 0 else "FAIL (exit %d)" % rc)

    Section("summary")
    for step, what, rc in results:
        print("%-5s %-62s %s" % (step, what, "PASS" if rc == 0 else "FAIL (exit %d)" % rc))
    failed = sum(1 for *_, rc in results if rc != 0)
    print("")
    if failed:
        Fail("%d failed" % failed)
        return 1
    Ok("every document check passes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
