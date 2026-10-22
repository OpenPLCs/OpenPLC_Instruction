"""One fact, one file: fail if the same claim is written out in two documents.

Case P8. Every document is split into sentences, markdown emphasis is stripped
so a bolded copy matches a plain one, and any sentence long enough to be a claim
that appears in two or more files is a failure. A pointer ("see X") is short and
generic, so pointing is never flagged -- the fix for a duplicate is a pointer.

What it reads: this repo's README.md, GLOSSARY.md and docs/, and the bootloader
repo's RELEASE-NOTES.md and docs/ when it is cloned beside this one.

Fenced code blocks are reported separately and do NOT fail the run: captured
serial output, log lines and shell commands quote the firmware, not each other.

    python tools/check_doc_dupes.py            report; exit 1 on prose duplicates
    python tools/check_doc_dupes.py --min 40   only longer claims
    python tools/check_doc_dupes.py --code     also list the code-block ones

Exit 0 = no prose claim appears twice, 1 = at least one does, 2 = setup problem.
"""

import argparse
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from _doccheck_common import Fail, Ok, Section, Warn, cfg  # noqa: E402


# Markdown noise: two copies of one claim rarely agree on bolding or punctuation.
NOISE = re.compile(r"[*`>#\[\]()|~—\-\s。，、：；！？…“”\"'‘’]+")
SPLIT = re.compile(r"[。！？\n]")
FENCE = re.compile(r"^\s*```")

# Deliberate exceptions. Each needs a reason, because "it is special" is how real
# drift hides. Keyed on a distinctive fragment of the normalised sentence.
#
# Empty since 2026-08-24. The one entry it held had never matched anything: its
# key was written with the hyphens and the dot removed, but NOISE strips '-'
# without stripping '/' or '.', so the normalised sentence still carried both and
# the key was not a substring of it. Emptying the dict changed neither the output
# nor the exit code, which is how we know.
#
# The lesson is about the shape of a key, not about that one document: a key here
# has to be a fragment of the sentence AFTER NOISE runs, so build it by normalising
# a real sentence rather than by hand. An exception that looks like protection and
# is not is worse than none, because the next person to touch that document will
# trust it.
ALLOWED = {
    # The four module documents share one skeleton, so the two rules about how
    # to read them are stated once in M1 and pointed at from the other three.
    # Each pointer is short, but three copies of the same short line still read
    # as a repeated claim -- which is correct, and is why they are listed here
    # rather than reworded until the check stops seeing them.
    "状态一列的规矩见M1§5M1firmwareupgrade.md":
        "module skeleton pointer: the status column rule lives in M1 §5",
    "引用规矩见M1§6M1firmwareupgrade.md":
        "module skeleton pointer: the cross-reference rule lives in M1 §6",
    # A case lives in one file; the module test table says how to run it and
    # ID-MAP says which group owns it. Both have to name the same script.
    "$TEST/udp_discovery.go":
        "the script path, named by both the test table and the id registry",
}


SKIP_WALK = {".git", "artifacts", "__pycache__", "node_modules"}


def _walk_md(root, out):
    """Every .md under root. artifacts/ holds rendered snapshots of docs -- they
    are copies by definition and say so in their own index."""
    if root is None or not root.is_dir():
        return
    for dp, dirs, fs in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP_WALK]
        out.extend(Path(dp) / f for f in fs if f.endswith(".md"))


def docs():
    """Every prose document this repo guards. A named file that is gone is a
    failure, not a skip: a check that scans nothing must not report PASS."""
    out = []
    prod = Path(cfg.DOCS_REPO)
    named = [prod / "README.md", prod / "GLOSSARY.md"]
    boot = Path(cfg.BOOT_REPO) if cfg.BOOT_REPO else None
    if boot:
        named.append(boot / "RELEASE-NOTES.md")
    else:
        Warn("  SKIP BOOT_REPO: not cloned beside OpenPLC_Instruction")
    missing = [p for p in named if not p.is_file()]
    out += [p for p in named if p.is_file()]
    if boot:
        _walk_md(boot / "docs", out)
    _walk_md(prod / "docs", out)
    return sorted(set(out)), missing


def scan(path, min_len):
    """Yield (normalised, raw, lineno, in_code) for each claim-sized sentence."""
    in_code = False
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            if FENCE.match(line):
                in_code = not in_code
                continue
            if line.lstrip().startswith("|") and line.count("|") > 3:
                parts = re.split(r"\|", line)
            else:
                parts = SPLIT.split(line)
            for raw in parts:
                n = NOISE.sub("", raw)
                if len(n) >= min_len:
                    yield n, raw.strip(), lineno, in_code


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--min", type=int, default=28,
                    help="minimum normalised length to count as a claim")
    ap.add_argument("--code", action="store_true",
                    help="also list duplicates inside fenced code blocks")
    args = ap.parse_args()

    Section("one fact, one file")
    files, missing = docs()
    if missing:
        for p in missing:
            Fail("named document is gone: %s" % p)
        print("  fix the path or drop the entry -- do not let it be skipped")
        return 2
    if not files:
        Fail("no documents found")
        return 2
    print("  %d document(s), claim length >= %d" % (len(files), args.min))

    prose, code = defaultdict(list), defaultdict(list)
    for p in files:
        for n, raw, lineno, in_code in scan(p, args.min):
            (code if in_code else prose)[n].append((p, lineno, raw))

    def dups(table):
        out = []
        for n, hits in table.items():
            if len({h[0] for h in hits}) > 1:
                if any(k in n for k in ALLOWED):
                    continue
                out.append((n, hits))
        return sorted(out, key=lambda t: -len({h[0] for h in t[1]}))

    bad = dups(prose)
    meh = dups(code)

    if meh:
        Section("in code blocks -- quoted output and commands, not failures")
        if args.code:
            for n, hits in meh:
                print("  %s" % hits[0][2][:96])
                for p, lineno, _ in hits:
                    print("      %s:%d" % (p, lineno))
        else:
            print("  %d block(s); --code to list them" % len(meh))
        print("  a release note and an acceptance record may both quote the same")
        print("  firmware string -- they quote the .c file, not each other")

    Section("result")
    if bad:
        for n, hits in bad:
            Fail("  %s" % hits[0][2][:96])
            for p, lineno, _ in hits:
                print("        %s:%d" % (p, lineno))
        print("")
        Fail("%d claim(s) written out in more than one file" % len(bad))
        Warn("fix by keeping ONE home and making the others a pointer to it")
        return 1

    Ok("no claim is written out in more than one file")
    return 0


if __name__ == "__main__":
    sys.exit(main())
