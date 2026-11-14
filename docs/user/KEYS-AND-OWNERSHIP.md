# Setting up a board, keys and factory reset

A board runs only sketches signed with the key of its owner. This page covers setting up a
new board, keeping and sharing keys, handing a board over, and the factory reset that clears
its owner.

## Setting up a new board

1. **Flash the bootloader** over ST-LINK: [FLASH-BOOTLOADER.md](FLASH-BOOTLOADER.md). A board
   that already runs bootloader 0.2.0 skips this.
2. **Install the board package** in Arduino IDE 2: [ARDUINO-IDE.md](ARDUINO-IDE.md).
3. **Upload a sketch.** A new board has no owner and runs nothing. The first upload makes the
   PC's signing key its owner, then uploads. If the PC has no key yet, one is created and its
   path is printed in the upload output.
4. **Back up the key file** (next section). Without it, nobody can upload to this board again
   until it is factory-reset.

## Where the key is

| System | Key file |
|---|---|
| Windows | `%AppData%\openplc\keys\fw_signing_key.pem` |
| Linux | `~/.config/openplc/keys/fw_signing_key.pem` |
| macOS | `~/Library/Application Support/openplc/keys/fw_signing_key.pem` |

The IDE uses this file without asking. To upload from another PC, copy the file to the same
place there. Keep the private key to yourself: anyone holding it can upload to your boards.

The commands below use `IAPTool`, which the board package installs here:

| System | IAPTool |
|---|---|
| Windows | `%LocalAppData%\Arduino15\packages\OpenPLC_Alpha\tools\STM32Tools\0.2.0\win\IAPTool.exe` |
| Linux | `~/.arduino15/packages/OpenPLC_Alpha/tools/STM32Tools/0.2.0/linux/IAPTool` |
| macOS | `~/Library/Arduino15/packages/OpenPLC_Alpha/tools/STM32Tools/0.2.0/macosx/IAPTool` |

`<board>` in a command is the board's IP address, or its USB port while it is in its
bootloader. Commands that change the owner (`setowner`, `revoke`) need the board in its
bootloader: [start it by hand](ARDUINO-IDE.md#starting-the-bootloader-by-hand) first.
`IAPTool getowner <board>` shows which key a board trusts.

## Letting colleagues upload

Each colleague keeps a key of their own; the owner certifies it. The owner's key never
leaves the owner's PC.

1. The colleague creates a key and prints its public half:
   `IAPTool genkey` (creates the key at the place in the table above; skip it if an earlier
   upload already created one there), then `IAPTool pubkey`.
   They send the 128 hex characters to the owner.
2. The owner issues a certificate:
   `IAPTool cert <the 128 hex characters> --key=<owner key> > colleague.cert`
3. The colleague saves it next to their key as `fw_signing_key.pem.cert`. From then on the IDE
   uploads with it; nothing else changes.

To stop a colleague: `IAPTool revoke <board> --key=<owner key> --leaf=<their 128 hex
characters>`, on every board they may upload to. Their next upload is refused; a sketch they
already uploaded keeps running, and `IAPTool getapprevoked <board>` finds those boards so you
can upload again.

## Handing a board to another owner

| Situation | What to do |
|---|---|
| The new owner has the board in hand | Factory-reset it (below); their first upload claims it |
| The board is remote | `IAPTool setowner <board> --current-key=<old owner key> --new-key=<new owner key>`. It needs both key files on one PC. The board then runs only sketches signed by the new owner: upload again with the new key |

## Lost key

Factory-reset the board (below), then upload: the first upload claims it for the key on
this PC.

## Factory reset

Removes the board's owner. Calibration values stay. The sketch stays in flash but does not
start until the next upload claims the board.

1. Reset the board (RESET button, or switch it off and on). LED3 blinks fast for 2 s.
2. Press BOOT0 while LED3 blinks and keep holding it.
3. About 10 s after the reset LED3 lights steadily: the factory reset is armed.
4. Release BOOT0 within 30 s of the reset. The owner is removed and the board waits in its
   bootloader for an upload.

To cancel instead: reset the board while LED3 is lit steadily. Holding BOOT0 longer than 30 s
also cancels it (the board stays in its bootloader, owner kept). Do not hold BOOT0 while
switching on: it is also the chip's boot pin and keeps the bootloader from starting.
