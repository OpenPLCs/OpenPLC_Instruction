# OpenPLC_Instruction

Product design documents for the OpenPLC board (STM32H743): hardware facts, what each
module must do and how it is tested, build rules, and the decisions already settled.
The code lives in the sibling repositories; these documents say what the code is for.

Documents are written in Chinese. Code comments, tool output and this README are English.

## Layout

| Path | What lives there |
|---|---|
| `GLOSSARY.md` | Product terms you cannot guess (cross-repo mirror, fixture, calibration values, root / leaf, ...) |
| `docs/hardware/` | Verified hardware facts, each linked to the schematic or datasheet it comes from |
| `docs/modules/` | One document per module (M1 firmware upgrade, M2 ownership, M3 app runtime, M4 production fixture): requirements, test cases, design |
| `docs/build/` | How the bootloader project is laid out and built, and the CubeMX rules |
| `docs/standards/` | What the applicable standards (IEC 61131-2) require of this board |
| `docs/engineering/` | How to run the tests, the test design, engineering requirements |
| `docs/repo/ARCHITECTURE.md` | The repositories, the path variables (`$BOOT`, `$TOOL`, `$CORE_REPO`, `$PORTTOOL`, `$TEST`, `$PROD`), cross-repo mirrored code |
| `docs/tables/` | Decisions (`DECISIONS.md`), status summary, id registry, renamed ids, acceptance checklists, deferred designs |
| `tools/` | Checks that guard these documents |

`$PROD` in a citation means this repository: `$PROD/docs/tables/DECISIONS.md` is
`docs/tables/DECISIONS.md` here.

## Checks

```
python tools/check_docs.py
```

Runs P7 (requirements and test cases agree), P8 (no claim written in two documents),
P9 (every path a document names exists), P13 (no renamed id is still cited) and P18
(the id registry is up to date). P7, P9 and P13 also read the code repositories when
they are cloned beside this one; a repository that is missing is skipped by name.

## License

Copyright (c) 2024-2026 Schaeffer AG. Licensed under Creative Commons Attribution 4.0
International (CC BY 4.0), see `LICENSE`. The code in the sibling repositories has its own license.
