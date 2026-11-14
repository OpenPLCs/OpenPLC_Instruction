# Colleagues, revoking and handing a board over

The basics (the first upload claims a board, where the key file is, a lost key, factory
reset) are in the [user guide](../../README.md#6-keys-who-may-upload). This page is for
teams: several people uploading to the same boards, and boards changing owner.

## IAPTool

The commands below use `IAPTool`, which the board package installs here:

| System | IAPTool |
|---|---|
| Windows | `%LocalAppData%\Arduino15\packages\OpenPLC_Alpha\tools\STM32Tools\0.2.0\win\IAPTool.exe` |
| Linux | `~/.arduino15/packages/OpenPLC_Alpha/tools/STM32Tools/0.2.0/linux/IAPTool` |
| macOS | `~/Library/Arduino15/packages/OpenPLC_Alpha/tools/STM32Tools/0.2.0/macosx/IAPTool` |

`<board>` in a command is the board's IP address, or its USB port while it is in its
bootloader. Commands that change the owner (`setowner`, `revoke`) need the board in its
bootloader: [enter it by hand](../../README.md#entering-the-bootloader-by-hand) first.
`IAPTool getowner <board>` shows which key a board trusts.

On Windows, run the commands in Command Prompt (`cmd`), not PowerShell: PowerShell's `>`
writes the certificate file in an encoding IAPTool cannot read, and `%LocalAppData%` is
written `$env:LOCALAPPDATA` there.

## Letting colleagues upload

Each colleague keeps a key of their own; the owner certifies it. The owner's key never
leaves the owner's PC.

1. The colleague creates a key and prints its public half:
   `IAPTool genkey` (creates the key at the [usual place](../../README.md#6-keys-who-may-upload);
   skip it if an earlier upload already created one there), then `IAPTool pubkey`.
   They send the 128 hex characters to the owner.
2. The owner issues a certificate:
   `IAPTool cert <the 128 hex characters> > colleague.cert` (signed with the owner's key at the
   usual place; add `--key=<file>` for a key kept elsewhere)
3. The colleague saves it next to their key as `fw_signing_key.pem.cert`. From then on the IDE
   uploads with it; nothing else changes.

## Revoking a colleague

`IAPTool revoke <board> --key=<owner key> --leaf=<their 128 hex characters>`, on every board
they may upload to. Their next upload is refused; a sketch they already uploaded keeps
running, and `IAPTool getapprevoked <board>` finds those boards so you can upload again.

## Handing a board to another owner

| Situation | What to do |
|---|---|
| The new owner has the board in hand | [Factory-reset](../../README.md#7-factory-reset) it; their first upload claims it |
| The board is remote | `IAPTool setowner <board> --current-key=<old owner key> --new-key=<new owner key>`. It needs both key files on one PC. The board then runs only sketches signed by the new owner: upload again with the new key |
