"""What the document checks share: output, file reading, and where the other repos are.

The checks read the code repos only to confirm what the documents say about
them, so a repo that is not cloned is skipped with a note rather than failed:
these checks guard the documents, not the machine. No machine config file --
the repos sit side by side (decision 76); OPENPLC_<NAME>_REPO overrides one.
"""

import os
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent
WORKSPACE = DOCS.parent

IS_WIN = os.name == "nt"


def _colour_ok():
    if os.environ.get("NO_COLOR") or not sys.stdout.isatty():
        return False
    if IS_WIN:
        try:
            import ctypes
            k = ctypes.windll.kernel32
            k.SetConsoleMode(k.GetStdHandle(-11), 7)
        except Exception:
            return False
    return True


_COLOUR = _colour_ok()

# A legacy console codepage cannot encode the warning signs these docstrings
# carry; a check must not be silenced by the terminal it runs in.
try:
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except (AttributeError, ValueError):
    pass


def _paint(text, code):
    return "\033[%sm%s\033[0m" % (code, text) if _COLOUR else text


def _emit(text):
    try:
        print(text)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "ascii"
        print(text.encode(enc, "replace").decode(enc, "replace"))


def Section(t): _emit(""); _emit(_paint("===== " + t, "36"))
def Ok(t):      _emit(_paint(t, "32"))
def Warn(t):    _emit(_paint(t, "33"))
def Fail(t):    _emit(_paint(t, "31"))


def read_text(path):
    """A whole file, raw: CRLF kept (so end-of-line regexes see no stray \\r),
    a UTF-8 BOM stripped (so a pattern anchored at the first character matches)."""
    with open(str(path), "r", encoding="utf-8", errors="replace", newline="") as fh:
        text = fh.read()
    return text[1:] if text.startswith("﻿") else text


def _sibling(key, *names):
    """A repo beside this one (or one level further out), "" when absent."""
    named = os.environ.get("OPENPLC_%s" % key, "")
    if named and Path(named).is_dir():
        return named
    for base in (WORKSPACE, WORKSPACE.parent):
        for name in names:
            cand = base / name
            if cand.is_dir():
                return str(cand)
    return ""


def _arduino15():
    if IS_WIN:
        return Path(os.environ.get("LOCALAPPDATA", "")) / "Arduino15"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Arduino15"
    return Path.home() / ".arduino15"


def _core_live():
    """The board package the Arduino IDE has installed, newest version."""
    named = os.environ.get("OPENPLC_CORE_LIVE", "")
    if named and Path(named).is_dir():
        return named
    root = _arduino15() / "packages" / "OpenPLC_Alpha" / "hardware" / "stm32"
    found = sorted((p for p in root.glob("*") if p.is_dir()), key=lambda p: p.stat().st_mtime)
    return str(found[-1]) if found else ""


class _Repos:
    """Where each repo is: beside this one, or named by OPENPLC_<KEY>."""
    DOCS_REPO = str(DOCS)
    BOOT_REPO = _sibling("BOOT_REPO", "OpenPLC_BootLoader")
    CORE_REPO = _sibling("CORE_REPO", "open_plc_arduino")
    TOOL_REPO = _sibling("TOOL_REPO", "OpenPLC_IAPTool")
    PORTTOOL_REPO = _sibling("PORTTOOL_REPO", "OpenPLC_PortsTestingTool")
    TEST_REPO = _sibling("TEST_REPO", "OpenPLC_Test")
    HW_REPO = _sibling("HW_REPO", "Hardware")
    REF_REPO = _sibling("REF_REPO", "ref/Hello_World_OpenPLC", "Hello_World_OpenPLC")
    CORE_LIVE = _core_live()


cfg = _Repos()


def repo(key):
    """The repo for `key` as a Path, or None if it is not cloned here."""
    value = getattr(cfg, key, "")
    return Path(value) if value else None


def skip_missing(what, key):
    """Say a repo was skipped; returns True when it is missing."""
    if repo(key) is None:
        Warn("  SKIP %s: %s is not cloned beside OpenPLC_Instruction" % (what, key))
        return True
    return False


def docs_repo():
    return DOCS


def prod_docs():
    """$PROD: this repo. A citation reads $PROD/docs/tables/STATUS.md."""
    return DOCS
