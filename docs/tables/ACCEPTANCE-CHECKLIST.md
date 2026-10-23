# 验收单

**每一条都要有判据**，"看起来正常"不算通过。判据的写法沿用 [HOW-TO-RUN-TESTS.md](../engineering/HOW-TO-RUN-TESTS.md) 的四栏格式。

三份清单用途不同，不要混：

| 清单 | 什么时候跑 | 谁跑 |
|---|---|---|
| [CHK-A · 改动后自检](#chk-a--改动后自检) | 每次改了固件 / 工具 | 开发 |
| [CHK-B · 发版验收](#chk-b--发版验收) | 打 tag 之前 | 开发 |
| [CHK-C · 单板出厂](#chk-c--单板出厂) | 每一块板子 | 产线 |

---

## CHK-A · 改动后自检

由快到慢，**前一层不过就不要往下走** —— 上板调试的每一轮都比主机测试贵一个数量级。

| # | 做什么 | 判据 | 命令 |
|---|---|---|---|
| CHK-A1 | 主机侧 Go 测试（用例 **T1-15**） | 全过 | `$TOOL`：`python tests/selfcheck.py` |
| CHK-A2 | 主机侧 C 测试（用例 **T1-16**） | 全过 | `$BOOT/tests`：`ctest --preset local -R T1-16`（编译器写在 gitignored 的 `CMakeUserPresets.json`） |
| CHK-A3 | 整模块静态检查（用例 **H3**） | 无输出 | `$TOOL` 和 `$TEST` 各自：`go vet ./...`（都在各自的 selfcheck 里） |
| CHK-A4 | bootloader 构建 | **0 errors 0 warnings**，且 `.bin` ≤ **131,072 B**（整个扇区 0，链接脚本 `FLASH LENGTH = 128K`） | `$TEST`：`python tools/build_image.py`（自己按链接脚本判尺寸），或 `python tools/flash_bootloader.py` 的构建阶段 |
| CHK-A4b | 工装镜像构建 | **0 errors**，只许有那条刻意的 `#warning`，链接用的是 `STM32H743IIKX_FLASH_PORTTOOL.ld`。不设大小上限：工装镜像由 ST-Link 整片写入，不走 IAP | `$PORTTOOL` 里 `start.sh fixture`。⚠️ **2026-09-08 之前这一项是不通过的** —— 溢出 47,608 字节（当时记在已删的第一次上板清单里） |
| CHK-A5 | 烧写 + 启动日志 | 见 [T3-01](#t3-01--启动门禁) | `$TEST`：`python tools/flash_bootloader.py` |
| CHK-A6 | 设备行为用例 | 全过 | `$TEST`：`TestCase all --ip=<板子IP> --bin=<app.bin> --key=<板子信任的 .pem>` |
| CHK-A7 | 变体断言（用例 **P4**） | 全过 | `$CORE_REPO`：`python tests/selfcheck.py` |

**每个仓有自己的自检入口**，一览在 [HOW-TO-RUN-TESTS.md](../engineering/HOW-TO-RUN-TESTS.md) 开头（决策 78）。

CHK-A4 的上限是整个扇区 0，因为根区 2026-09-30 起在扇区 15（决策 72）；超了链接器会报 `region FLASH overflowed`。

⚠️ **CHK-A6 里 `all` 不含要人动手的用例**（T1-17、T2-01、T2-05），它们会被点名跳过而不是静默略过。要跑得单独按 id 跑，见 [HOW-TO-RUN-TESTS.md](../engineering/HOW-TO-RUN-TESTS.md)。

---

## CHK-B · 发版验收

先跑完 A，再跑这里。**这里是每次发版都要过的固定项**。

**每次发版跑四样**：被发的那个仓自己的自检、`$TEST` 的全部契约测试（`python tools/selfcheck.py`）、`$TEST` 里和它有关的整机项、`$PROD` 的文档检查（`python tools/check_docs.py`）。

| 发什么 | 整机项 |
|---|---|
| 板卡包 | 例程逐个上板（`$TEST`：`python tools/run_examples.py`）、T1-34（`$TEST`：`python host/fakeboard/run_ide_upload.py`） |
| IAPTool | T1-34、五条用户路径（CHK-B9） |
| bootloader | 五条用户路径、掉电（T1-21 / T1-22）、按住 BOOT0（T1-27） |
| PortTool | 只跑它自己的自检 |

| # | 做什么 | 判据 | 哪个仓、哪条命令 |
|---|---|---|---|
| CHK-B1 | 版本号三处一致（用例 **P1**） | `$BOOT/Core/Inc/IAP_config.h` 的 `OPENPLC_FW_VERSION` == core `boards.txt` 的 `build.fw_version` == 发布说明。⚠️ **这三处都是「卡包版本」**；sketch 的 **app 版本不在其中**，它每个 sketch 都不同，不是跨仓镜像 | `$TEST`：`python tools/check_version_sync.py` |
| CHK-B2 | 跨仓镜像代码同步（用例 **P2**） | `$PROD/docs/repo/ARCHITECTURE.md`「跨仓镜像的代码」表里每一项两边一致 | `$TEST`：`python tools/check_mirror_sync.py` |
| CHK-B3 | Arduino 包已同步进 git（用例 **P3**） | `$CORE_LIVE` 与 `$CORE_REPO` 逐文件一致（比对命令在 ARCHITECTURE.md） | `$CORE_REPO`：`python tests/check_core_sync.py` |
| CHK-B4 | **出厂板第一次上传就被认领**（用例 **T2-35**） | 一块刚造好出厂态的板子，本机没有私钥：经 USB 上传 → IAPTool 打印生成的私钥路径并认领 → app 起来；之后 `getpubkey` 返回那把公钥。见 [M2 归属与信任](../modules/M2-ownership.md) | 上板，人在场 |
| CHK-B5 | 捆绑升级风险已写进发布说明 | `OpenPLC_BootLoader/RELEASE-NOTES.md` 的 Upgrade rules 与**当前扇区 15 的布局**相符：校准值 8 KiB、根区、metadata、完成标记（[SECTOR-15.md](../modules/M1/SECTOR-15.md)，决策 72） | 人工对照 `$BOOT/RELEASE-NOTES.md` |
| CHK-B6 | 全新板子路径 | 一块从未烧过 app 的板子：`BOOTLD-INVALID` → 上传（没有根时自动认领）→ 正常启动 | 上板，人在场 |
| CHK-B8 | **清空重写走一遍**（`setowner --wipe`） | 一块已认领、且至少作废过一个叶的板子：`IAPTool setowner <ip> --current-key=... --new-key=... --wipe` → 板子复位 → `getowner` 报新根、generation 延续、启动日志 `96/96 revoke slot(s) free`。板子回收的是扇区 15，不碰扇区 0 | `$TOOL` 编出的 IAPTool，命令见左 |
| CHK-B7 | 升级路径 | 一块跑着**上一版**的板子：先烧 bootloader，再传 app，正常启动 | 上板，人在场 |
| CHK-B9 | **五条用户路径各走一遍** | 从出厂态开始跑 `python3 tools/run_five_paths.py --elf <boot.elf> --cdc <COM口>`，步骤和判据见 [HOW-TO-RUN-TESTS.md](../engineering/HOW-TO-RUN-TESTS.md)「五条用户路径 · 从出厂态跑一整轮」（按[决策 72](DECISIONS.md) 写）；每步都达到它自己的判据。要真板子、USB 线，人按一次 BOOT0 十秒（[决议 69](DECISIONS.md)） | `$TEST`：`python3 tools/run_five_paths.py`，见左 |

⚠️ **CHK-B7 是唯一能抓住捆绑升级风险的用例。** 只测 CHK-B6 永远发现不了"新 bootloader 读不懂旧 journal"。

---

## CHK-C · 单板出厂

产线逐板执行。**每条都要能在几十秒内判完**，否则产线跑不动。

| # | 做什么 | 判据 |
|---|---|---|
| CHK-C1 | 烧 bootloader | ST-Link 报下载完成且校验通过 |
| CHK-C2 | 启动日志 | 有 `SDRAM staging buffer OK`；`Reset cause` 合理；crypto 自检未报错 |
| CHK-C3 | **MAC 唯一** | 记录本板 MAC，**和已出货记录比对不重复** |
| CHK-C4 | 以太网 | 拿到 IP，UDP 发现有应答 |
| CHK-C5 | USB CDC | 枚举出串口，`ping` 答 `OK` |
| CHK-C6 | RS232 | `$TEST/onboard/rs232/SerialPort` 回显正常 |
| CHK-C7 | 烧 app | 上传成功并正常启动 |

### CHK-C1–C7 第一次完整跑过：2026-09-28，第二块板

七条全过。两块板的 MAC：

| 板 | UID，w0 w1 w2 | MAC |
|---|---|---|
| 第一块 | `00240039 3033510C 38313437` | `02:bb:49:3e:a8:02`（由 UID 按同一算法算出） |
| 第二块 | `00390029 34325103 39393938` | `02:bb:f5:38:99:12`（开机日志实测，与算出的一致） |

⚠️ 同一个 UID 有两种字序：porttool 的 `uid=` 是 w0 w1 w2（`$BOOT/TestCase/porttool/porttool.c`），发现报文的 `hardwareId` 是 w2 w1 w0（`$BOOT/IAPServer/iap_keyderive.c`）。

⚠️ **CHK-C3 的「和已出货记录比对」**：出货记录的位置 2026-10-10 已定为 `records/<UID>/`。

---

## T3-01 · 启动门禁

任何上板测试之前都先过这一关。`tools/flash_bootloader.py` 会自动判。

⚠️ **这条 2026-08-22 之前叫 `T0`。** 它不属于 `T1-07`–`T1-10` 那一系列（那些是设备行为用例，定义在 [HOW-TO-RUN-TESTS.md](../engineering/HOW-TO-RUN-TESTS.md)，`T0` 从来不在那里），所以给了它自己的前缀。

| 日志 | 含义 | 接下来 |
|---|---|---|
| `SDRAM staging buffer OK (2 MiB at C0000000)` | ✅ 暂存区可用 | 继续 |
| `** SDRAM SELF-TEST FAILED at offset ... **` | ❌ FMC 或上电时序坏了 | **停**。先修 FMC，上传测试全部无意义 |
| USB 口 1 一个字节都没有 | 口被别的程序占着，或 USB 没枚举 | 看脚本提示的占用进程；或经网口读开机缓存，再不行看 SWO（[HOW-TO-RUN-TESTS.md](../engineering/HOW-TO-RUN-TESTS.md)「测试从哪读板子的输出」） |

**当前状态：✅ 通过。**

自检失败**不改变任何控制流** —— 板子仍然安全（上传会在 CRC 那步失败、app 区不受影响），这行日志的作用只是把根因直接说出来，省掉"为什么每次都 Checksum Failed"的排查。
