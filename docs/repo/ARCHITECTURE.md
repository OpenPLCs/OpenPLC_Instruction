# 三仓布局

这个产品是**三个独立的代码库**（外加工装上位机 `$PORTTOOL`，决策 76），没有共享构建系统。一个功能通常要同时改动其中两到三个。

## 路径变量

全套文档用下面这些变量指代路径，**别的地方不写绝对路径**。

| 变量 | 指什么 |
|---|---|
| `$BOOT` | `OpenPLC_BootLoader` 的 clone（公开仓 `OpenPLCs/OpenPLC_BootLoader`，决策 153）—— bootloader 的 CubeIDE 工程 |
| `$CORE_REPO` | `open_plc_arduino` 的 clone —— 板卡包，在版本控制下 |
| `$CORE_LIVE` | Arduino IDE **真正加载**的那份板卡包（`$A15/packages/.../stm32/<版本>`），**不在版本控制下** |
| `$TOOL` | `OpenPLC_IAPTool` 的 clone（公开仓 `OpenPLCs/OpenPLC_IAPTool`，决策 155）—— IAPTool 和它自己的单元测试 |
| `$PORTTOOL` | `OpenPLC_PortsTestingTool` 的 clone —— PortTool（给硬件工程师的端口测试面板）和它的测试、交付打包（决策 76） |
| `$ETSPROD` | `OpenPLC_ETS_Prod` 的 clone —— ETS 产品文件（`.knxprod`）、它的源 XML，以及 KNX 模块的使用说明（用户 2026-10-03 定） |
| `$TEST` | `OpenPLC_Test` 的 clone —— 整体测试：契约测试和整机测试（决策 78）。2026-10-02 新建 |
| `$HW` | `Hardware` 的 clone —— 原理图、netlist、生产文件 |
| `$REF` | `Hello_World_OpenPLC` 的 clone —— 同一块板子的参考工程 |
| `$IDE` | Arduino IDE 2.x 的安装根目录 |
| `$A15` | Arduino 的数据目录（装着 `packages/` 那个） |
| `$PKGIDX` | `package_index_json` 的 clone —— 只在发板卡包时用 |
| `$PROD` | `OpenPLC_Instruction` 的 clone（公开仓 `OpenPLCs/OpenPLC_Instruction`）—— 产品设计文档：硬件事实、模块、构建、测试方法、决策 |

⚠️ **这里刻意不写任何一条本机的实际路径** —— 这个仓会被 clone 到别处。**这台机器上每一项解析成了什么，问 `$TEST` 里的 `python tools/common.py --probe`**。

`$TEST` 的脚本只认 `$TEST/config/machine.py`（gitignored，由 `$TEST/tools/init_machine.py` 探测生成），它的 selfcheck 的 **ENV** 一步会把实际解析到的路径全部打出来。PortTool 的在 `$PORTTOOL` 的 `tools/local.json`（`tools/build.sh find-tools` 生成）；bootloader、板卡包、IAPTool 的部件测试不要本机配置（决策 78）。

`$CORE_LIVE` 末尾是板卡包版本号，**发版会变**，所以任何地方都不写死它；`$A15/packages/OpenPLC_Alpha/tools/STM32Tools/<版本>` 里那个是随包分发的 IAPTool 版本，两个号互相独立。

## 三个仓库

| | 路径 | 内容 |
|---|---|---|
| **App 侧** | `$CORE_LIVE`（干活的地方）<br>`$CORE_REPO`（git 仓库） | 定制板卡包。编译用户应用；同时拥有 `cores/arduino/main.cpp`、变体头文件 `variants/STM32H7xx/H743/variant_PLC_H743.h`、引脚与外设映射、`libraries/OpenPLC_IAP`、`libraries/OpenPLC_Net`、`tools/discovery/` |
| **Bootloader 侧** | `$BOOT` | STM32CubeIDE 工程（`IAPServer/`、`Core/`、`LWIP/`） |
| **PC 工具侧** | `$TOOL` | Go，产出 `IAPTool.exe` |
| **工装上位机** | `$PORTTOOL` | Go，产出 `PortTool.exe`；工装固件那一半在 `$BOOT/TestCase/porttool/` |

⚠️ **Arduino 板卡包是要分发给其他工程师的**，所以 core 层的改动是共享基础设施，不是本地小修小补。

### App 侧有两份，方向是单向的

`$CORE_LIVE` 是 **Arduino IDE 真正加载的那份**（插件安装目录）。改动先落在这里，在这里编译、烧板、验证。

**只有验证通过的代码才拷进 `$CORE_REPO` 提交。**

- 反过来做没有意义 —— IDE 根本不看 `$CORE_REPO`，改那边不生效。
- ⚠️ **`$CORE_LIVE` 不在版本控制下。** 验证通过后忘了同步，那段代码就只存在于这一台机器上，重装一次 IDE 就没了。
- 同步**继续手动做，不自动化**（2026-09-11 定）。兜底是 P3 `$CORE_REPO/tests/check_core_sync.py`，提交前跑它。

核对两边是否已同步：`$CORE_REPO/tests/check_core_sync.py`（用例 **P3**，发版检查单 `CHK-B3`）。

它**刻意排除六类**，每一类为什么排除写在脚本自己的 `SKIP` 注释里 —— 那是唯一出处，这里不抄。

## 其他位置

| | 路径 |
|---|---|
| **参考示例** | `$REF` —— 发明新写法之前先看这里是怎么做的 |
| **硬件文档** | `$HW` —— 概览 `.txt` + `Production/UpperDeck/Schematics/OpenPLC_UpperDeck_R3.pdf` |
| **整体测试** | `$TEST` —— 契约测试、整机测试、上板脚本、板上 sketch、测试资产。部件测试在各自的仓；每个仓的入口见 [HOW-TO-RUN-TESTS.md](../engineering/HOW-TO-RUN-TESTS.md) 开头 |
| **板卡包索引** | `$PKGIDX` —— Arduino IDE 拉板卡包用的 package index json |

**文档打架时以 KiCad 原理图为准**（确实打过架，见 `$PROD/docs/hardware/HARDWARE-FACTS.md`）。

## 跨仓镜像的代码

因为没有共享构建，下面这些东西在多个仓库里各有一份拷贝。改一处必须改另一处，
否则会静默分叉 —— **不会编译报错**，只会在运行时表现成别的症状。

**同步的规矩（2026-09-16 定）**：

1. **bootloader 是源。** 先在 `$BOOT` 里调试清楚，再同步给其他仓。
2. **改动了下表任何一处，当场问用户要不要同步其余位置** —— 不要自行决定。
3. **不做共享文件**（submodule / 生成拷贝那类），2026-09-16 明确放弃。

"core" 指 `$CORE_LIVE` 和 `$CORE_REPO` 两份（先改前者，验证过再同步到后者）。

「谁在查」一栏是实测的，不是推测 —— 跑 `$TEST/tools/check_mirror_sync.py`（用例 **P2**），
它自己会在输出末尾列出没查的项。

| # | 内容 | 在哪几份（源在最前） | 谁在查 |
|---|---|---|---|
| 1 | MAC 从 UID 派生的算法 | bootloader `LWIP/Target/ethernetif.c`（USER CODE MACADDRESS 块）<br>core `libraries/OpenPLC_Net/src/ethernetif.c` | P2 |
| 2 | 发现回复限流 `discovery_reply_allowed()` | bootloader `IAPServer/udp_server.c`<br>core `libraries/OpenPLC_IAP/src/udp_server.c` | P2（上限 + 窗口两项）。⚠️ **只比数值，不比注释** —— 两边的解释 2026-09-16 已经分叉（core 那份丢了「at 115200 baud」） |
| 3 | 身份字符串格式 `name_uid_role_<卡包版本>_<app版本>`（五段，`_` 分隔，任何字段都不能含 `_`）。bootloader 那一份第 5 段固定填 `-`（它不知道装的是哪一版 sketch） | bootloader `IAPServer/IAP_server.c` 的 `iap_identity_string()`<br>core `libraries/OpenPLC_IAP/src/udp_server.c`<br>tool `IAP_Ether.go` 的 `parseBoardInfoFromReply`、`IAP_CDC.go` | P2 |
| 4 | SRAM4 交接记录 `boot_handoff_t`，以及第 16–23 字节 bootloader 发布给 app 的复位原因（决策 80） | bootloader `IAPServer/IAP_boot_handoff.{c,h}`<br>core `cores/arduino/stm32/IAP_boot_handoff.{c,h}` | P2 |
| 5 | 上传锁的文件名和过期时间 | tool `uploadlock.go`<br>core `tools/discovery/network_discovery.go` | P2（两项） |
| 6 | 机器 ID（UID）的字节序与十六进制格式 | bootloader `IAPServer/iap_keyderive.c`<br>core `libraries/OpenPLC_IAP/src/iap_keyderive.c` | P2 比两个函数的**规范化正文**（2026-09-22 补上，此前完全没查）。⚠️ 不比整个文件 —— `#include` 两边本来就不同（`main.h` / `Arduino.h`） |
| 7 | 证书线格式（128 字节，签名覆盖前 64） | bootloader `IAPServer/iap_cert.h`<br>core `libraries/OpenPLC_IAP/src/iap_cert.h`<br>tool `iapcert/iapcert.go` | P2（长度 + 签名前缀两项） |
| 8 | owner 记录格式（v4，签名前缀 88），根区基址 `0x081E2000`（[SECTOR-15.md](../modules/M1/SECTOR-15.md)） | bootloader `IAPServer/owner_slot.h`<br>core `libraries/OpenPLC_IAP/src/owner_root_ro.c`<br>tool `owner.go`<br>test `$TEST/tools/run_setowner.py`、`inject_owner_record.py`、`host/renode/run.py`（T2-03 自己拼记录，才能造坏签名） | P2（版本、签名前缀、根区基址三项；`run_setowner.py` 查版本） |
| 9 | **RTC 备份寄存器的分配** | bootloader `IAPServer/iap_auth.c`<br>core `libraries/OpenPLC_IAP/src/iap_auth.c`<br>分配表见下 —— **认领任何一个之前先看这里** | 🟡 P2 扫两个 `iap_auth.c` 和 core 的 `backup.h`，**不扫 HID indices** |
| 11 | **`sha256.c` 和 `iap_cert.c` 整个文件** —— 两边本来就一模一样，原先只有头注释不同 | bootloader `IAPServer/`<br>core `libraries/OpenPLC_IAP/src/` | P2 **逐字节**。⚠️ 差一个字节就红，所以改完一边必须同步另一边。<br>**`sha256.h` 不在内** —— 两边的 include guard 名字是刻意不同的；API 真变了 `.c` 必然跟着变，一样抓得到 |
| 12 | **`iap_auth.c`**：`iap_auth_issue_challenge` 整个函数；外加 `iap_auth_verify_and_consume` 里**签名覆盖哪些字节**（`nonce || msg`，顺序和长度） | 同上 | P2 比**规范化正文**（去注释、去空白）。⚠️ **不比整个文件、不比 `verify_and_consume`、也不比 `rng_words`** —— core 那份是刻意的子集（没有 `iap_auth_report_backup_domain`），`verify_and_consume` 两边取当任根的 API 和诊断输出本来就不同，`rng_words` 两边够到的 RNG 句柄不同（core 那份转调 `OpenPLC_Net` 的 `openplc_rng_words()`，决议 67） |
| 13 | **校准值区格式**（魔数、版本、通道数、布局、CRC-32）。格式见 [SECTOR-15.md](../modules/M1/SECTOR-15.md)「校准值区的格式」 | bootloader `IAPServer/calib_area.h`<br>core `libraries/OpenPLC_Ports/src/openplc_calib.h`<br>porttool `src/calarea/calarea.go` | P2 一次比三方（决策 78，「依赖固件源码的 PortTool 测试归哪」那张票）。**2026-09-28 新增** |
| 14 | **AI 换算常数**：AI1 分压 90.6k / 22.6k、AI2 分流 124 Ω、ADC 满量程 2500 mV（硬件出处 [HARDWARE-FACTS.md](../hardware/HARDWARE-FACTS.md)「模拟量」）。工装按它算校准的标称值，app 按它套用，两边不一样系数就错 | core `libraries/OpenPLC_Ports/src/openplc_analog.c`<br>porttool `src/calstore/spec.go` 的 `Range.AINominal` 和它用的常数（决策 136） | P2。**2026-10-03 新增** |
| 15 | **工装协议**：`pt.*` 命令的应答和拒绝原文、`pt.caps` 的形状、采样帧字段、回环计数。demo 只讲其中一个子集，差别见 [PORTTOOL-FLOW.md](../modules/M4/PORTTOOL-FLOW.md)「A.9」 | bootloader `TestCase/porttool/*.c`（工装固件）<br>core `libraries/OpenPLC_Ports/examples/FixtureDemo/`（第 6 步的 demo） | `T4-05`（不是 P2）：同一份 Go 测试对工装固件的模拟板和 demo 的主机版各跑一遍。**2026-10-11 新增** |
| 16 | **CAN 位时序表**（125k / 250k / 500k / 1M，HSE 作内核时钟）和 **ADC 配置**（时钟源与分频、采样时间、分辨率；参考电压按固定 2500 mV，归镜像 14；两边都读一次不平均）（决策 124） | bootloader `TestCase/common/port_can.c`、`port_adc.c`（工装固件）<br>core `libraries/OpenPLC_Ports/src/OpenPLC_CAN.cpp`、`OpenPLC_Ports.cpp`、`boards.txt`、`variants/STM32H7xx/H743/generic_clock.c` | P2。**2026-10-15 新增** |
| 17 | **KNX 组对象编号和订货号**：`$ETSPROD` 的 `knx_objects.json` 是源头，板卡包的头文件由 `tools/gen_product.py` 生成（KEX-15） | etsprod `knx_objects.json`<br>core `libraries/OpenPLC_KNX/src/openplc_knx_objects.h` | P2 用生成函数重算头文件，逐字节比。**2026-10-16 新增** |
| 19 | **开机日志缓存**：SRAM4 的位置和大小、头和记录格式、`[sys]` 前缀（[BOOT-LOG.md](../modules/M1/BOOT-LOG.md)）；三份链接脚本的 `RAM_D3` 起点跟着挪 | bootloader `IAPServer/boot_log.{c,h}`、`STM32H743IIKX_FLASH.ld`、`STM32H743IIKX_FLASH_PORTTOOL.ld`<br>core `cores/arduino/stm32/boot_log.{c,h}`、`variants/STM32H7xx/H743/ldscript.ld` | P2：`boot_log.c` 规范化正文、`boot_log.h` 常量、三份 `RAM_D3` 起点。**2026-10-17 新增** |
| 18 | **工装命令行长度上限** 256 字节：上位机发命令前按它拦 | bootloader `TestCase/porttool/porttool.h` 的 `PORTTOOL_LINE_MAX`<br>porttool `src/ptproto/cal.go` 的 `CommandLineMax` | P2。**2026-10-17 新增** |
| 20 | **`openplc_log` 读开机日志**：请求解析、回答格式（首行 `log <next> <more>`、每条一行、整包 ≤ 1024 字节）、限流每秒 20 个回答（[IAP-PROTOCOL.md](../modules/M1/IAP-PROTOCOL.md)「`openplc_log`」，决策 148） | bootloader `IAPServer/udp_server.c`<br>core `libraries/OpenPLC_IAP/src/udp_server.c` | P2：`log_read_reply_allowed`、`log_read_line`、`log_read_reply` 规范化正文，`LOG_READ_*` 三个常量，`log_read_ctx_t`，请求的匹配条件。**2026-10-17 新增** |
| 21 | **只读查询** `getuid` `getpubkey` `getowner` `getapprevoked`：回答文本、限流每秒 20 个回答（[IAP-PROTOCOL.md](../modules/M1/IAP-PROTOCOL.md)「只读查询」，决策 148）；app 读扇区 15 最新 metadata 的扫法（metadata 区起止地址、记录类型 `M`、一条 7 格、格大小） | bootloader `IAPServer/udp_server.c`（`IAP_server.c` 的 TCP / CDC 也调它）、`IAPServer/bootloader_state.c`<br>core `libraries/OpenPLC_IAP/src/udp_server.c`、`fw_meta_ro.c` | P2：`iap_query_reply`、`query_reply_allowed` 规范化正文，`QUERY_*` 两个常量，UDP 上的分派，metadata 扫法的五个常量。**2026-10-17 新增** |
| 10 | **物理网卡判定** —— 排掉没 up 的、回环、点对点（VPN tun）、无 MAC 的，再按操作系统分类虚拟网卡 | core `tools/discovery/network_discovery.go` 的 `isPhysicalInterface()` + `iface_{windows,linux,darwin}.go`<br>tool `netiface/` | P2。**2026-09-18 新增** —— 决定见 `$PROD/docs/tables/DECISIONS.md` 第 51 条 |

> ✅ 每条由谁查见最后一列；只有第 9 条的 HID indices 只靠人。

> 第 11、12 条做逐字节 / 规范化正文比对（[DECISIONS.md 第 65 条](../tables/DECISIONS.md)），不违反规矩 3：两个仓各自仍是一个真实文件，同步照旧手工做。

### 备份 SRAM 分配表

备份 SRAM（`0x38800000`，4 KiB）和备份寄存器一样跨 bootloader / app 存在，同样没有分配器。

| 范围 | 谁用 | 做什么 |
|---|---|---|
| 整块 4 KiB | **bootloader**（[决策 72](../tables/DECISIONS.md)） | 扇区 15 回收期间暂存根区和最后一条 metadata，回收完清掉（[SECTOR-15.md](../modules/M1/SECTOR-15.md)「回收的六步」） |

**app / core 不得写备份 SRAM。** core 的 `cores/arduino/stm32/backup.h` 只有通用接口，今天没有调用者。

### RTC 备份寄存器分配表

备份寄存器是**跨 bootloader / app 持久存在**的共享资源，而两个镜像分别编译、没有任何机制阻止它们抢同一个。

| 寄存器 | bootloader | app / core | |
|---|---|---|---|
| DR0 | — | — | 空 |
| DR1 | — | `RTC_BKP_INDEX`（`cores/arduino/stm32/backup.h:34` 定义，**当前无人写**） | bootloader 不用（nonce 来自 TRNG，决议 66） |
| DR2 | — | — | 空 |
| DR3 | **VBAT witness** | — | 只证明备份域活着（RTC 走时要它），**不再与重放保护有关** |
| DR4 | — | `HID_MAGIC_NUMBER_BKP_INDEX` | |
| DR5–DR9 | — | — | 空 |
| DR10 | — | `HID_OLD_MAGIC_NUMBER_BKP_INDEX` | |

> ⚠️ **没有分配器，加新用途先改这张表。** 「两个镜像不同时运行所以不冲突」是错的：备份寄存器存在的意义就是跨交接保存状态，先后访问同一格就是冲突（2026-08-17 DR2 撞车过一次，记录在 `$TEST/tools/check_mirror_sync.py` 那一节的注释里）。

## 密钥

板子和各仓里都没有签名私钥，只在用户 PC 上：见 [M2-ownership.md](../modules/M2-ownership.md)「私钥放在哪」。
