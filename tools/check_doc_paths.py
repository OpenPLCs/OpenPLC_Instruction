"""Every file path a document names has to exist.

Case P9. It checks only the shapes whose base directory is unambiguous:

  * markdown links            [text](path/to/OWNERSHIP.md)      -- relative to the doc
  * repo-var paths            $PROD/docs/tables/DECISIONS.md, $BOOT/..., $TOOL/...
  * backticked docs/ paths    `docs/tables/STATUS.md`          -- some repo root

$PROD is this repo. $BOOT, $TOOL, $CORE, $PORTTOOL and $TEST are the code repos
beside it; a repo not cloned is skipped by name, not failed.

It deliberately ignores every other backticked path: a bare `tools/foo.py`
means "relative to whichever repo this paragraph is about", which a checker
cannot know, and guessing produced mostly false alarms. Write `$TEST/tools/<name>.py`
when you want it checked. Line numbers (fmc.c:153-193) are stripped first.

Two more checks on markdown links: a #fragment has to be an anchor the target
really has (a heading turned into an anchor the way GitHub does it, or an
explicit <a id>), and link text that is itself a path has to name the file the
link goes to.

Besides this repo's documents it reads the code repos' release notes, test
READMEs and source comments that name a docs/ path, so a citation from code into
these documents is checked too. --own limits the run to this repo's files.

    python tools/check_doc_paths.py           report; exit 1 on a dead reference
    python tools/check_doc_paths.py --own     only this repo's own documents
    python tools/check_doc_paths.py --list    print every path it resolved

Exit 0 = every named path exists, 1 = at least one does not, 2 = setup problem.
"""

import argparse
import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from _doccheck_common import Fail, Ok, Section, Warn, cfg, docs_repo, prod_docs  # noqa: E402


MD_LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")
HEADING = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t]*#*[ \t]*$")
FENCE = re.compile(r"^[ \t]*(```|~~~)")
HTML_ANCHOR = re.compile(r"<a\s+(?:id|name)=\"([^\"]+)\"")
# Link text that is nothing but a path: it has a slash, or ends in a file
# extension these repos use. A boards.txt key like menu.upload_method is neither.
PATH_TEXT = re.compile(r"^\$?(?:[\w.:+-]*/[\w./:+-]*|[\w.+-]+\.(?:md|c|h|cpp|go|py|ino|sh|bat|txt|json|ld|ioc|html|svg))"
                       r"(?::\d+(?:-\d+)?)?$")
# $BOOT/... and $TOOL:... -- the repo-variable convention the docs declare.
VAR_PATH = re.compile(r"\$(PORTTOOL|BOOT|TOOL|CORE|PROD|TEST)(?:_REPO)?[:/]([\w./+-]+)")
# `docs/...` in backticks. Only docs/, because that prefix pins the base to a
# repo root -- every other bare path in these documents is relative to whichever
# repo the surrounding paragraph is about, which is not knowable from here.
TICK_PATH = re.compile(r"`(docs/[\w./+-]+\.\w+)`")
# A document path written in a source comment. Deliberately narrow: only tokens
# that carry "docs/" and an extension, because anything looser turns this check
# into noise and an ignored check protects nobody. 2026-09-16: 66 such paths
# were left pointing at nothing by the document move and no check could see them.
SRC_PATH = re.compile(r"(?<![\w/$])[\w./+-]*docs/[\w./+-]+\.\w+")
SRC_EXT = (".c", ".h", ".cpp", ".go", ".py", ".json", ".html", ".js", ".txt",
           ".cmd", ".ps1")

SKIP_DIR = {".git", "__pycache__", "Debug", "Release", "node_modules", ".vscode"}
# Placeholders, globs and brace expansions are not claims about a file that
# exists. "machine.{ps1,py}" arrives here truncated at the dot, and "path/to/X"
# is an illustration in a rule about how to write paths.
SKIP_TOKEN = re.compile(r"[<>*?{}]|^https?:|^//|://|^#|^mailto:|(?:^|/)path/to/|\.$")


def github_slug(heading):
    """The anchor GitHub gives a heading: formatting and punctuation dropped,
    lowercased, spaces to hyphens. Letters of any script survive."""
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", heading)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[^\w\- ]", "", text.strip().lower())
    return text.replace(" ", "-")


_ANCHORS = {}


def anchors(md):
    """Every anchor a markdown file offers; repeated headings get -1, -2, ..."""
    if md not in _ANCHORS:
        found, seen, fenced = set(), {}, False
        try:
            lines = md.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            lines = []
        for line in lines:
            if FENCE.match(line):
                fenced = not fenced
                continue
            if fenced:
                continue
            found.update(HTML_ANCHOR.findall(line))
            m = HEADING.match(line)
            if m:
                slug = github_slug(m.group(2))
                n = seen.get(slug, 0)
                seen[slug] = n + 1
                found.add(slug if n == 0 else "%s-%d" % (slug, n))
        _ANCHORS[md] = found
    return _ANCHORS[md]


def link_problem(text, tok, target, doc):
    """Why a markdown link to an existing file is still wrong, or None."""
    frag = tok.split("#", 1)[1] if "#" in tok else ""
    md = doc if tok.startswith("#") else target
    if frag and md is not None and md.suffix == ".md" and md.is_file():
        if unquote(frag).lower() not in anchors(md):
            return "no heading makes the anchor #%s" % frag
    shown = text.strip().strip("`")
    if target is not None and PATH_TEXT.match(shown):
        named = re.sub(r":\d+(?:-\d+)?$", "", shown).rstrip("/")
        if named.startswith("."):
            # Written relative to this document, so it has to be the same file.
            said = Path(os.path.normpath(str(doc.parent / named)))
            if said != Path(os.path.normpath(str(target))):
                return "the text says %s but the link goes to %s" % (named, tok.split("#")[0])
        elif named.split("/")[-1] != target.name:
            return "the text names %s but the link goes to %s" % (named.split("/")[-1], target.name)
    return None


def repos():
    boot = Path(cfg.BOOT_REPO or "")
    tool = Path(cfg.TOOL_REPO or "")
    core = Path(getattr(cfg, "CORE_REPO", "") or "")
    return boot, tool, core, None, docs_repo()


def docs(boot, tool, core, _unused, prod, own=False):
    out = []
    homes = [(prod, ["docs", "README.md", "GLOSSARY.md"])]
    if not own:
        # What the code repos keep as documents: release notes and the READMEs
        # beside their test code.
        homes += [(boot, ["RELEASE-NOTES.md"]),
                  (tool, ["TestCase/host"]),
                  (Path(cfg.PORTTOOL_REPO or ""), ["TestCase/host"])]
    for root, subs in homes:
        if root is None or not str(root) or not root.exists():
            continue
        for s in subs:
            p = root / s.replace("/", os.sep)
            if p.is_file():
                out.append((p, root))
            elif p.is_dir():
                for dp, dirs, fs in os.walk(p):
                    dirs[:] = [d for d in dirs if d not in SKIP_DIR]
                    out.extend((Path(dp) / f, root) for f in fs if f.endswith(".md"))
    return sorted(set(out))


def sources(boot, tool, core, prod):
    """Source files that may name a document in a comment."""
    out = []
    for root, subs in ((boot, ["IAPServer", "LWIP", "Core/Src", "Core/Inc", "TestCase"]),
                       (tool, ["TestCase/tools", "TestCase/host",
                               "internal", "iapcert", "."]),
                       (core, ["libraries", "cores", "tools"]),
                       (prod, ["tools"])):
        if root is None or not str(root) or not root.exists():
            continue
        for sub in subs:
            p = root / sub.replace("/", os.sep)
            if not p.is_dir():
                continue
            if sub == ".":
                out.extend((f, root) for f in p.iterdir()
                           if f.is_file() and f.suffix in SRC_EXT)
                continue
            for dp, dirs, fs in os.walk(p):
                dirs[:] = [d for d in dirs if d not in SKIP_DIR and d != "uecc"]
                out.extend((Path(dp) / f, root) for f in fs
                           if os.path.splitext(f)[1] in SRC_EXT)
    return sorted(set(out))


def resolve(token, doc, doc_root, boot, tool, core, _unused, prod):
    """Where a named path should be, or None if the token is not a claim."""
    if SKIP_TOKEN.search(token):
        return None
    token = token.split("#")[0]
    # fmc.c:153-193 -- the file must exist, the line number is a hint
    token = re.sub(r":\d+(?:-\d+)?$", "", token)
    if not token or token.endswith(("/", ":")):
        return None

    m = VAR_PATH.match(token)
    if m:
        base = {"BOOT": boot, "TOOL": tool, "CORE": core,
                "PORTTOOL": Path(cfg.PORTTOOL_REPO or ""), "TEST": Path(cfg.TEST_REPO or ""),
                "PROD": prod_docs()}[m.group(1)]
        # A repo not cloned here cannot be checked; that is a skip, not a dead path.
        if not base or not str(base) or str(base) == "." or not base.exists():
            return None
        return base / m.group(2).replace("/", os.sep)

    if token.startswith("docs/"):
        # Pinned to a repo root, but which repo depends on the sentence -- so it
        # passes if any repo has it. That is enough to catch a path that moved.
        for base in (boot, tool, core, prod, doc_root):
            if base and str(base) and (base / token.replace("/", os.sep)).exists():
                return base / token.replace("/", os.sep)
        return boot / token.replace("/", os.sep)

    if token.startswith(("./", "../")) or token.endswith(".md"):
        # relative to the document, then to its repo root: docs cite both ways
        for cand in (doc.parent / token, doc_root / token):
            try:
                c = Path(os.path.normpath(str(cand)))
            except (OSError, ValueError):
                continue
            if c.exists():
                return c
        return Path(os.path.normpath(str(doc.parent / token)))
    return None


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--list", action="store_true", dest="list_only")
    ap.add_argument("--own", action="store_true", help="only this repo's own documents and tools")
    args = ap.parse_args()

    Section("every documented path exists")
    boot, tool, core, _unused, prod = repos()
    # $PROD is this repo, so it always resolves; a code repo not cloned here
    # only leaves its own citations unchecked, and says so.
    for key in ("BOOT_REPO", "TOOL_REPO", "CORE_REPO", "PORTTOOL_REPO", "TEST_REPO"):
        value = getattr(cfg, key, "")
        if value:
            print("  %-14s %s" % (key, value))
        else:
            Warn("  SKIP %s: not cloned beside OpenPLC_Instruction; paths into it go unchecked" % key)
    print("  prod    %s" % prod_docs())

    files = docs(boot, tool, core, _unused, prod, args.own)
    srcs = sources(None, None, None, prod) if args.own else sources(boot, tool, core, prod)
    print("  %d document(s), %d source file(s)" % (len(files), len(srcs)))

    dead, wrong, checked = [], [], 0
    for doc, root in files + srcs:
        in_source = doc.suffix in SRC_EXT
        try:
            text = doc.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if in_source:
            for m in SRC_PATH.finditer(text):
                tok = m.group(0)
                target = resolve(tok, doc, root, boot, tool, core, _unused, prod)
                if target is None:
                    continue
                checked += 1
                if not target.exists():
                    dead.append((doc, text[:m.start()].count(chr(10)) + 1, tok))
        for m in MD_LINK.finditer(text):
            tok = m.group(2)
            lineno = text[:m.start()].count("\n") + 1
            target = resolve(tok, doc, root, boot, tool, core, _unused, prod)
            if target is not None:
                checked += 1
                if not target.exists():
                    dead.append((doc, lineno, tok))
                    continue
            if in_source or not (target is not None or tok.startswith("#")):
                continue
            why = link_problem(m.group(1), tok, target, doc)
            if why:
                wrong.append((doc, lineno, tok, why))
        for m in TICK_PATH.finditer(text):
            tok = m.group(1)
            target = resolve(tok, doc, root, boot, tool, core, _unused, prod)
            if target is None:
                continue
            checked += 1
            if not target.exists():
                lineno = text[:m.start()].count("\n") + 1
                dead.append((doc, lineno, tok))
        for m in VAR_PATH.finditer(text):
            tok = m.group(0)
            target = resolve(tok, doc, root, boot, tool, core, _unused, prod)
            if target is None:
                continue
            checked += 1
            if not target.exists():
                lineno = text[:m.start()].count("\n") + 1
                dead.append((doc, lineno, tok))

    if args.list_only:
        print("  %d path reference(s) resolved" % checked)
        return 0

    Section("result")
    print("  %d path reference(s) checked" % checked)
    for doc, lineno, tok in dead:
        Fail("  %s:%d  ->  %s" % (doc, lineno, tok))
    for doc, lineno, tok, why in wrong:
        Fail("  %s:%d  ->  %s  (%s)" % (doc, lineno, tok, why))
    if dead or wrong:
        print("")
        if dead:
            Fail("%d reference(s) name a file that does not exist" % len(dead))
        if wrong:
            Fail("%d link(s) reach a file but not what they say" % len(wrong))
        return 1

    Ok("every path named in a document exists, and every link says where it goes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
