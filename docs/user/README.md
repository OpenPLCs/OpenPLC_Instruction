# User instructions

For board package, bootloader and IAPTool 0.2.0. What changed in this release, and how to
upgrade a board already in service, is in the
[release notes](https://github.com/OpenPLCs/OpenPLC_BootLoader/blob/0.2.0/RELEASE-NOTES.md).

## Getting started

| Document | What it covers |
|---|---|
| [FLASH-BOOTLOADER.md](FLASH-BOOTLOADER.md) | Building the bootloader and flashing it onto a board over ST-LINK (STM32CubeIDE or STM32CubeProgrammer) |
| [ARDUINO-IDE.md](ARDUINO-IDE.md) | Installing the board package in Arduino IDE 2, picking the port, writing and uploading a sketch, starting the bootloader by hand |
| [KEYS-AND-OWNERSHIP.md](KEYS-AND-OWNERSHIP.md) | Setting up a new board, where the key is, letting colleagues upload, handing a board over, a lost key, factory reset |

## Using the board in a sketch

Start from the examples under *File > Examples* (libraries `OpenPLC_Ports`, `OpenPLC_KNX`,
`OpenPLC_SDRAM`): each says what to connect and what you should see. The library READMEs
below ship with the board package.

| Document | What it covers |
|---|---|
| [OpenPLC_Ports](https://github.com/OpenPLCs/OpenPLC_Arduino_PKG/blob/v0.2.0/libraries/OpenPLC_Ports/README.md) | Which object is which port, analog values in mV and mA, outputs at power-up and reset, the port examples |
| [OpenPLC_SDRAM](https://github.com/OpenPLCs/OpenPLC_Arduino_PKG/blob/v0.2.0/libraries/OpenPLC_SDRAM/README.md) | Using the 64 MB external SDRAM |
| [OpenPLC_SD](https://github.com/OpenPLCs/OpenPLC_Arduino_PKG/blob/v0.2.0/libraries/OpenPLC_SD/README.md) | SD card and file system |
| [OpenPLC_KNX](https://github.com/OpenPLCs/OpenPLC_Arduino_PKG/blob/v0.2.0/libraries/OpenPLC_KNX/README.md) | KNX roles, the `KNX` object, the TP bus, the KNX examples |
| [ETS product](https://github.com/OpenPLCs/OpenPLC_ETS_Prod/blob/master/README.md) | The ETS product file and how to program the board with ETS |

## Keys and uploads from the command line

| Document | What it covers |
|---|---|
| [IAPTool](https://github.com/OpenPLCs/OpenPLC_IAPTool/blob/v0.2.0/README.md) | Every IAPTool command and option, for uploads and ownership without the IDE |
