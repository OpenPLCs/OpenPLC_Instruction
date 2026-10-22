# bootloader 替身：用真代码代替手写假板子

**是什么**：把 `$BOOT/IAPServer` 的真源码，加板卡包 `OpenPLC_IAP/src/udp_server.c`（app 一侧的重启握手），编成两个 PC 程序：`bootstand_boot`（bootloader 那一半）和 `bootstand_app`（app 那一半），由 `bootstand.py` 在每次模拟复位时轮流启动，和真板子上两个程序轮流运行一样。IAPTool 的契约测试（T1-18a–g、T1-34）对着它跑，不再对着手写的假板子 fake_board.py（已删）。

**为什么**：手写假板子是 bootloader 协议的第二份实现，必然和真 bootloader 漂开（换掉前查出 6 处不一致）；用真代码就没有第二份。

## 住哪、怎么编

| 项 | 定案 |
|---|---|
| 位置 | `$TEST/host/bootstand/`。要 `$BOOT`、`$CORE_REPO`、`$TOOL` 三个仓，按决策 78 归契约层 |
| 平台 | 只在 Windows 上跑（决策 143） |
| 构建 | CMake，和 `$BOOT/tests` 同一套写法；源码只读引用 `$BOOT` 和 `$CORE_REPO`，不拷贝。分两个程序：bootloader 和板卡包各有一份同名函数（`iap_auth`、`iap_cert`、`sha256`、`uECC`，跨仓镜像），放不进一次链接 |
| 驱动 | `$TEST/host/fakeboard/` 的 `run_cases.py`（T1-18）和 `run_ide_upload.py`（T1-34）改为启动替身 |
| 端口 | 和假板子一样：烧写和命令走 61865（绑不上自动换冷门端口），发现另外在 56865/UDP 应答（见 HOW-TO-RUN-TESTS 的假板子端口说明） |

## 真的是什么，替掉的是什么

| 真代码（只读编进来） | 替身自己写的 |
|---|---|
| `$BOOT/IAPServer`：`IAP_server.c`、`tcp_server.c`、`udp_server.c`、`bootloader_state.c`、`bkp_stash.c`、`owner_slot.c`、`iap_auth.c`、`iap_cert.c`、`iap_keyderive.c`、`fw_verify.c`、`sha256.c`、`net_rand.c`、`uecc/uECC.c`、`IAP_boot_handoff.c`、`boot_log.c` | lwIP raw API（`udp_*`、`tcp_*`、`pbuf_*`）桥到 PC 的 socket |
| 板卡包 `OpenPLC_IAP/src/udp_server.c`：app 在跑时的重启挑战与重启；它读开机缓存，所以 `cores/arduino/stm32/boot_log.c` 一起编 | HAL 桩（flash 擦写、CRC、RNG、复位等）；CRC 是标准 CRC-32 IEEE 再取反，和 `$BOOT/Core/Src/crc.c` 的配置一致 |
| | flash、SDRAM、SRAM4（交接记录和开机缓存）、备份 SRAM 放在源码里的原地址（`0x08000000`、`0xC0000000`、`0x38000000`、`0x38800000`），由 PC 在固定地址上分配；整个程序链接在 4 GiB 以下，因为固件是 32 位的，真 flash 驱动把地址当 `uint32_t` 传；flash 内容存成文件，模拟复位后还在 |
| | 真代码的 `printf` 直接上 stdout，不进开机缓存；开机缓存只照 `main.c` 的顺序初始化，跳 app 前的刷新是空函数 |
| | 角色切换：没有有效 app 时跑 bootloader 那一半；收完镜像、模拟复位后，镜像有效就切到 app 那一半 |

## 一处特别处理

| 情况 | 怎么做 | 为什么 |
|---|---|---|
| `jump_to_app` 是 ARM 汇编 | `$BOOT/IAPServer/IAP_server.c` 的 `IAP_SERVER_HOST_TEST` 打开时不编那段汇编，改调替身的 `iap_server_host_jump_to_app()` | 照 `bootloader_state.c` 的 `BOOTLOADER_STATE_HOST_TEST` 先例；固件编出来不变 |

## 怎么跑

| 做什么 | 命令（在 `$TEST` 下） |
|---|---|
| T1-18a–g 和它里面的 T2-28–T2-30 | `python host/fakeboard/run_cases.py`，selfcheck 的 `T1-18a-T1-18g` 一步就是它 |
| T1-34 | `python host/fakeboard/run_ide_upload.py`，要 arduino-cli，几分钟，不进 selfcheck |
| T1-22、T1-38、T2-05、T2-09、T2-19、T2-20、T2-36 | `python host/fakeboard/run_lifecycle.py [--only ID]`，selfcheck 的 `T1-22` `T1-38` `T2-05` `T2-19` 四步就是它 |
| T1-01、T1-02、T1-05–T1-14、T1-23、T1-24、T1-26、T1-28、T1-30、T1-32、T2-01、T2-03、T2-11、T2-12、T2-14–T2-17、T2-25、T2-26 | `python host/fakeboard/run_protocol.py [--only ID]`，selfcheck 的 `T1-01` `T1-13` `T1-28` `T1-30` `T1-32` `T2-01` `T2-11` `T2-15` 八步就是它 |
| 单独起一块替身 | `python host/bootstand/bootstand.py --state <目录> --fresh [--root <128 位十六进制公钥>] [--discovery-port 56865] [--uid <24 位十六进制>] [--gesture none\|upload\|factory] [--fail-after-erase N] [--fail-after-program N]` |
| 按 BOOT0 过开机窗口 | `--gesture`：只作用于这次起电后的第一次启动，照 `$BOOT/Core/Src/main.c` 开机窗口那段：`upload` 留在上传模式，`factory` 先恢复出厂再留在上传模式 |
| 掉电 | `--fail-after-erase N` / `--fail-after-program N`：一次启动里第 N 次擦 / 写做完后进程立即结束（flash 是映射文件，已写的留着），监管进程随后冷启动，故障不再注入 |

两个驱动脚本每次都先编替身（`host/bootstand/build/`，gitignored），要 `HOST_CC` 和 CMake（在 PATH 上或 `HOST_CC` 旁边）。替身往 stdout 打 `[stand-in] root <公钥>`（根变了就打）、`[stand-in] reset`、`[stand-in] jump to app`、`[stand-in] ... serving on <端口>`，脚本读这几行和真代码自己的 `printf` 判结果。

## 测不到什么

真 lwIP、MAC、PHY 和时序；复位时 MAC 一起被拉掉（所以真板子烧写成功收不到 `OK`）；`flashboot`（替身直接拒绝，T1-18 / T1-34 不发它）；USB CDC 通道。替身不跑 `MX_RTC_Init()`，所以每次启动都会打一行 `Backup domain was lost`，只是日志，不影响判定。

⚠️ 换成真代码后，原来在假板子上过的用例如果失败，**先当成 IAPTool 或用例判据的问题去查**，不改替身去迁就用例：那正是要找的不一致。
