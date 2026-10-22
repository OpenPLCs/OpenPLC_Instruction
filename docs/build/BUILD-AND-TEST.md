# 构建与测试

路径变量（`$IDE`、`$CORE_LIVE`、`$TOOL` 等）的定义见 [../repo/ARCHITECTURE.md](../repo/ARCHITECTURE.md) 的「路径变量」。测试要的本机路径由 `$TEST/tools/init_machine.py` 探测生成（PortTool 的在 `$PORTTOOL` 的 `tools/local.json`，由 `tools/build.sh find-tools` 生成）；bootloader、板卡包、IAPTool 的部件测试不要本机配置（决策 78）。

> **写路径一律用 `/`。** Windows 的 .NET 路径 API 全都接受正斜杠，Linux 不接受反斜杠 —— `/` 是唯一两边都对的写法。可执行文件后缀（`.exe` 或空）不要写死，`$TEST` 的脚本里用 `common.py` 的 `EXE`。

## 命令行重编 app（不用开 Arduino IDE）

IDE 自带的 CLI 在 `$IDE/resources/app/lib/backend/resources/arduino-cli`（Windows 上带 `.exe`）—— **不在 PATH 上**，`$TEST` 的脚本从 `$TEST/config/machine.py` 的 `ARDUINO_CLI` 拿，板卡包的测试从环境变量 `ARDUINO_CLI` 拿。

```
& $ARDUINO_CLI compile --warnings all `
  --config-file $ARDUINO_CLI_CONFIG `
  --fqbn "OpenPLC_Alpha:stm32:OPEN-PLC:pnum=PLC_H743,usb=CDCgen,upload_method=cdcMethod" `
  --build-path "<IDE 的 sketch 缓存目录>/<hash>" `
  "$TEST/onboard/rs232/SerialPort"
```

`$ARDUINO_CLI_CONFIG` 默认是 `$HOME/.arduinoIDE/arduino-cli.yaml`，两个平台同名。

- **`--config-file` 必须带**，否则找不到 Arduino15 packages 和用户库目录
- **`--warnings all` 必须带** —— arduino-cli 默认 `-w`，什么警告都不打；IDE 里那个 All 档是 IDE 自己的设置，CLI 不继承
- FQBN 和 sketch 路径能从缓存目录的 `build.options.json` 读出来，**别硬猜** —— 菜单项增删过几次，手写的 FQBN 会缺段；2026-10-17 之前的缓存目录里还带着 `xusb=` / `knxrole=`，arduino-cli 不认已删的菜单，照下表改
- `--build-path` 指向 IDE 自己用的缓存目录，这样 `.bin` 落在 IAPTool 一直用的老位置

### 板卡包的菜单（Tools 下）

2026-10-17 清理过，只留这四个（`$CORE_REPO` `boards.txt`）：

| 菜单（FQBN 键） | 选项 | 用途 |
|---|---|---|
| Board part number（`pnum`） | `PLC_H743` | 唯一一项；变体头、flash 大小都挂在它下面 |
| USB support（`usb`） | `CDCgen`（默认）：`Serial` 是 USB 口 1；`CDC`：`Serial` 落到 UART4 | `CDC` 只给 Renode 用（Renode 不模拟 USB） |
| Upload method（`upload_method`） | `cdcMethod`（USB）、`ethMethod`（网口），都是 IAPTool | 只这两条过 bootloader 的签名和版本闸门（[M1](../modules/M1-firmware-upgrade.md)） |
| Force flash（`forceflash`） | `no`（默认）、`yes` | 一次性允许烧低版本 |

删掉的，和为什么：

| 删的 | 为什么 |
|---|---|
| `xusb`（USB 速度） | 板上只接了 OTG_FS 的 PA11 / PA12，High Speed 两项用不了（[HARDWARE-FACTS](../hardware/HARDWARE-FACTS.md)「USB FS 只接了 PA11 / PA12」）；只剩 Full Speed 就不用选 |
| `upload_method` 的 STM32CubeProgrammer SWD / Serial / DFU | `platform.txt` 按旧脚本的位置参数调 `stm32CubeProg.sh`，现在的脚本只认 `-i` / `-f`，三项都跑不起来；就算接上，默认写 `0x08000000`，会盖掉 bootloader。要 ST-Link 直烧用 STM32CubeProgrammer 本身 |
| `knxrole`（KNX 角色） | 角色改在 sketch 里写 `OPENPLC_KNX_ROLE(...)`（[M3](../modules/M3-app-runtime.md) `R3-24`） |
| `xserial` `virtio` `opt` `dbg` `rtlib` | 只声明了菜单名、没有一个选项，IDE 里本来就不显示；对应的构建值用 `platform.txt` 的默认 |

### 二次编译只编改过的

- 同一构建目录再编，只重编改过的文件，core 用缓存：`prebuild.sh` 生成的 `sketch/SrcWrapper.cpp` 内容不变就不改写，`.S` 也带 `-MMD` 生成依赖（2026-10-13 实测，空跑仍约 75–115 s，耗在 arduino-cli 逐个查约 3.5 万个依赖的修改时间）
- 会整体重编的是正常情况：从「文件 → 示例」打开（IDE 每次复制到新的临时目录）、换菜单项（FQBN 变）、改过板卡包

### 签名是自动的，不要手工做

- 签名逻辑在 IAPTool 里（`sign.go` 的 `signBinFile`），`IAPTool cdc/ether` 在内存里直接签，**不需要 `.sig` 文件**
- 烧录前比版本（sketch 的 `OPENPLC_APP_VERSION` 对板上 app）由 IAPTool 做，见 [M1](../modules/M1-firmware-upgrade.md)「版本闸门」

## 其他构建

| 目标 | 命令 |
|---|---|
| IAPTool（Windows / Linux amd64，macOS amd64 + arm64） | `$TOOL/build.py`（Windows 双击 `build.cmd`，Linux / macOS 直接执行）—— 别手搓 `go build`，输出布局是约定好的；macOS 的 `IAPTool` 是按 CPU 选 `IAPTool-amd64` / `IAPTool-arm64` 的启动脚本 |
| TestCase（本机） | `cd $TEST && go build -o Output/<GOOS>/TestCase .`。`$TEST/tools/run_case.py` 找它，别自己拼路径 |
| network_discovery（四平台） | `$CORE_LIVE/tools/discovery/build.py` —— **Arduino IDE 开着会因文件占用失败** |
| bootloader | STM32CubeIDE；测试要的命令行编译是 `$TEST/tools/build_image.py` |

单文件语法检查 bootloader 的改动，不必开 CubeIDE：用 core 包里的
`$A15/packages/OpenPLC_Alpha/tools/xpack-arm-none-eabi-gcc/*/bin/arm-none-eabi-gcc`（Windows 上带 `.exe`），加上 `-fsyntax-only`、
`-mcpu=cortex-m7 -mthumb -DSTM32H743xx -DUSE_HAL_DRIVER` 和工程的 `-I` 路径。
能在烧板之前挡住低级错误。

## 测试分工

每个仓的自检入口、每条用例怎么跑、判据是什么，都在 [HOW-TO-RUN-TESTS.md](../engineering/HOW-TO-RUN-TESTS.md)。

全部用例、覆盖哪条需求、最近结果在 `$PROD/docs/tables/STATUS.md`，这里不另列。

## 排查时容易看错的日志位置

| 想看什么 | 真实位置 |
|---|---|
| network_discovery 的日志 | 系统临时目录下的 `network_discovery.log`（带 `[HH:MM:SS.mmm]` 时间戳）。Windows 是 `%TEMP%`，Linux 是 `$TMPDIR` 或 `/tmp`。**不是** `tools/discovery/bin/<平台>/err.log`（那是 IDE 抓的 stderr） |
| bootloader / app 的日志 | USB 口 1（app 里就是 `Serial`），系统行带 `[sys]`；电脑打开口之前的在 SRAM4 开机缓存里，USB 不通时经网口读，都不通看 SWO（[HOW-TO-RUN-TESTS.md](../engineering/HOW-TO-RUN-TESTS.md)「测试从哪读板子的输出」）。⚠️ `R1-43` `R3-22` 落地前仍在 RS232 端子 C05/C06 |
