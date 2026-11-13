# OpenPLC_Instruction

User instructions and product design documents for the OpenPLC board (STM32H743), all for
release 0.2.0. The code lives in the sibling repositories; these documents say how to use it
and what it is for.

The user instructions are in English. The design documents are in Chinese; code comments,
tool output and this README are English.

`$PROD` in a citation means this repository: `$PROD/docs/tables/DECISIONS.md` is
`docs/tables/DECISIONS.md` here.

## 1. User instructions

| Document | What it covers |
|---|---|
| [docs/user/FLASH-BOOTLOADER.md](docs/user/FLASH-BOOTLOADER.md) | Flashing the bootloader onto a board over ST-LINK |
| [docs/user/ARDUINO-IDE.md](docs/user/ARDUINO-IDE.md) | Installing the board package in Arduino IDE 2 and uploading a sketch |

## 2. Hardware

| Document | What it covers |
|---|---|
| [docs/hardware/HARDWARE-FACTS.md](docs/hardware/HARDWARE-FACTS.md) | Verified hardware facts, each linked to the schematic or datasheet it comes from |
| [docs/standards/IEC-61131-2.md](docs/standards/IEC-61131-2.md) | What IEC 61131-2 requires of this board |

## 3. Modules

One main document per module (requirements, test cases, design), with its detail documents below it.

| Document | What it covers |
|---|---|
| [docs/modules/M1-firmware-upgrade.md](docs/modules/M1-firmware-upgrade.md) | M1 firmware upgrade: the bootloader and uploads |
| [docs/modules/M1/BOOT-SEQUENCE.md](docs/modules/M1/BOOT-SEQUENCE.md) | Start-up: deciding whether to stay in the bootloader or start the application |
| [docs/modules/M1/IAP-PROTOCOL.md](docs/modules/M1/IAP-PROTOCOL.md) | The commands bootloader and application accept on the wire |
| [docs/modules/M1/CHALLENGE-AUTH.md](docs/modules/M1/CHALLENGE-AUTH.md) | Challenge-response authorisation of state-changing commands |
| [docs/modules/M1/FLASHBOOT.md](docs/modules/M1/FLASHBOOT.md) | Replacing the bootloader in place (`flashboot`) |
| [docs/modules/M1/SECTOR-15.md](docs/modules/M1/SECTOR-15.md) | Layout of the last flash sector: calibration, root area, metadata |
| [docs/modules/M1/BOOT-LOG.md](docs/modules/M1/BOOT-LOG.md) | Boot log buffer in SRAM4 |
| [docs/modules/M2-ownership.md](docs/modules/M2-ownership.md) | M2 ownership and trust: root key, certificates, revocation, factory reset |
| [docs/modules/M3-app-runtime.md](docs/modules/M3-app-runtime.md) | M3 application runtime: the Arduino board package |
| [docs/modules/M3/USER-API.md](docs/modules/M3/USER-API.md) | API conventions for sketches |
| [docs/modules/M3/CONSTRAINTS.md](docs/modules/M3/CONSTRAINTS.md) | The design must not restrict the user's application |
| [docs/modules/M3/CALIBRATED-ANALOG.md](docs/modules/M3/CALIBRATED-ANALOG.md) | AI / AO in physical units with calibration values |
| [docs/modules/M3/KNX-TP-DATA-LINK.md](docs/modules/M3/KNX-TP-DATA-LINK.md) | KNX TP data link layer |
| [docs/modules/M4-production-fixture.md](docs/modules/M4-production-fixture.md) | M4 production fixture |
| [docs/modules/M4/PORTTOOL-FLOW.md](docs/modules/M4/PORTTOOL-FLOW.md) | Port test fixture: control model and per-port test procedure |
| [docs/modules/M4/PRODUCTION-FRAMEWORK.md](docs/modules/M4/PRODUCTION-FRAMEWORK.md) | Production test framework: plan files and step sequences |
| [docs/modules/M4/PROD-CONFIG-ITEMS.md](docs/modules/M4/PROD-CONFIG-ITEMS.md) | Production test configuration items |

## 4. Repositories and build

| Document | What it covers |
|---|---|
| [docs/repo/ARCHITECTURE.md](docs/repo/ARCHITECTURE.md) | The repositories, the path variables (`$BOOT`, `$TOOL`, `$CORE_REPO`, `$PORTTOOL`, `$TEST`, `$PROD`), cross-repo mirrored code |
| [docs/build/BUILD-AND-TEST.md](docs/build/BUILD-AND-TEST.md) | How to build and test |
| [docs/build/BOOTLOADER-PROJECT-LAYOUT.md](docs/build/BOOTLOADER-PROJECT-LAYOUT.md) | Bootloader project layout: flash partitions, size budget, modules, lwIP |
| [docs/build/CUBEMX-RULES.md](docs/build/CUBEMX-RULES.md) | Rules for changing the CubeIDE project |

## 5. Testing

| Document | What it covers |
|---|---|
| [docs/engineering/README.md](docs/engineering/README.md) | Engineering requirements |
| [docs/engineering/HOW-TO-RUN-TESTS.md](docs/engineering/HOW-TO-RUN-TESTS.md) | How to run the tests, and the pass criteria |
| [docs/engineering/TEST-DESIGN.md](docs/engineering/TEST-DESIGN.md) | How the tests are built, and why |
| [docs/engineering/BOOTLOADER-STAND-IN.md](docs/engineering/BOOTLOADER-STAND-IN.md) | Bootloader stand-in: the real code on the PC instead of a hand-written fake board |
| [docs/engineering/HOW-TO-RUN-PORTTOOL-TESTS.md](docs/engineering/HOW-TO-RUN-PORTTOOL-TESTS.md) | PortTool tests |
| [docs/engineering/PORTTOOL-DEMO-ON-BOARD.md](docs/engineering/PORTTOOL-DEMO-ON-BOARD.md) | Fixture software demo on a real board |

## 6. Decisions and tables

| Document | What it covers |
|---|---|
| [GLOSSARY.md](GLOSSARY.md) | Product terms you cannot guess (cross-repo mirror, fixture, calibration values, root / leaf, ...) |
| [docs/tables/DECISIONS.md](docs/tables/DECISIONS.md) | Decisions already settled, with reasons and when to reopen them |
| [docs/tables/STATUS.md](docs/tables/STATUS.md) | Status summary: how far each requirement has got |
| [docs/tables/ACCEPTANCE-CHECKLIST.md](docs/tables/ACCEPTANCE-CHECKLIST.md) | Acceptance checklists |
| [docs/tables/DEFERRED-DESIGNS.md](docs/tables/DEFERRED-DESIGNS.md) | Designs worked out but deferred |
| [docs/tables/ID-MAP.md](docs/tables/ID-MAP.md) | Id registry: where each id lives |
| [docs/tables/RENAMED-IDS.md](docs/tables/RENAMED-IDS.md) | Renamed ids, old to new |

`tools/` holds the checks that guard these documents.

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
