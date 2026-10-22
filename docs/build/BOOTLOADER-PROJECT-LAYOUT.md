# OpenPLC Bootloader —— 工程结构概览

**这份只讲"工程长什么样"**：怎么构建、有哪些文件、编出来多大、lwIP 怎么配的。

⚠️ **行为、安全模型、验证状态一律不写在这里，看 `$PROD/README.md` 指的那几层** —— 同一件事写两遍，第二遍必然漂移。

| 想知道 | 去哪 |
|---|---|
| 启动怎么决策、签名怎么验、metadata 怎么记 | [BOOT-SEQUENCE.md](../modules/M1/BOOT-SEQUENCE.md)、[SECTOR-15.md](../modules/M1/SECTOR-15.md)、[M2-ownership.md](../modules/M2-ownership.md) |
| 三个仓库在哪、哪些代码是跨仓镜像 | `$PROD/docs/repo/ARCHITECTURE.md` |
| 引脚、串口、启动模式的实测事实 | [HARDWARE-FACTS.md](../hardware/HARDWARE-FACTS.md) |
| 需求清单和测试矩阵 | `$PROD/docs/tables/STATUS.md` |

## 1. 项目定位

- 目标芯片：STM32H743IIKx（Cortex-M7，2 MB Flash / 1 MB RAM）
- 它讲的是 **bootloader** 工程（`$BOOT`），和 Application 分开（app 侧是 Arduino core，见 [ARCHITECTURE.md](../repo/ARCHITECTURE.md)）
- 构建：STM32CubeIDE 经典 Managed Build（`.cproject` + `Debug/`）。仓库里那份 `CMakeLists.txt` 是 CubeMX 生成的，**当前构建不用它**

## 2. Flash 分区

`Core/Inc/usbd_cdc_flash.h`：

```c
#define ADDRESS_VECTOR        0x20000                              // 128K 偏移
#define IAP_APP_ADDRESS       (FLASH_BASE_ADDR | ADDRESS_VECTOR)   // = 0x08020000
#define RESERVED_TAIL_SECTORS 1                                    // 尾部预留给 bootloader 状态
#define IAP_STATE_SECTOR_ADDR ADDR_FLASH_SECTOR_7_BANK2            // = 0x081E0000
#define IAP_APP_MAX_SIZE      (IAP_STATE_SECTOR_ADDR - IAP_APP_ADDRESS)
```

| 区 | 地址 | 用途 |
|---|---|---|
| bootloader | `0x08000000`–`0x0801FFFF`（sector 0，128K） | 本工程 |
| application | `0x08020000` 起，上限 `0x081E0000` | 1,835,008 B |
| └ KNX 数据（只在程序链接了 `OpenPLC_KNX` 时） | `0x081C0000`（bank2 sector 6，app 区最后一个扇区） | 只有协议栈数据 16 KiB（ETS 写的个体地址和各表；IP 路由器 0x091A 的过滤表在 512 起、长 8192，至少要 8704 B，多出的给 TP 设备 0x07B0 放链接），大小由 `$CORE_REPO/boards.txt` 的 `-DKNX_FLASH_SIZE` 定，布局见 `$CORE_REPO/libraries/OpenPLC_KNX/src/knx_config.h`。这种程序上限因此是 1,703,936 B（1664 KiB），构建时由 `$CORE_REPO/system/extras/postbuild.sh` 检查 |
| bootloader 状态 | `0x081E0000`（bank2 sector 7，128K） | 校准值 8K + 根区 8K + metadata 约 112K（511 条）+ 完整标记，见 [SECTOR-15.md](../modules/M1/SECTOR-15.md) |

**板卡包给 app 的链接上限就是 `upload.maximum_size`（1,835,008 B，等于 bootloader 的 `IAP_APP_MAX_SIZE`）**：`variants/STM32H7xx/H743/ldscript.ld` 的 `FLASH` 长度直接用 `LD_MAX_SIZE`，不再减 `LD_FLASH_OFFSET`，因为 `platform.txt` 传进来的已经是 app 上限。

**扇区 15 只有 bootloader 能写**：app 擦它就会带走校准值和 metadata。core 里有代码写它时 `P19` 报错（`$CORE_REPO/tests/check_no_sector15_writes.py`）。app 侧擦任何扇区都要把 `FLASH_EraseInitTypeDef` 每个字段设全：`VoltageRange` 被原样或进 `FLASH_CR`，bit3 是整 bank 擦除，`P19` 也查这一项（ETS 下载曾因这个残值把 bank2 整个擦掉）。

**本板不提供模拟 EEPROM**：板上没有 EEPROM 芯片（`$HW/Production/Bridge/1436_01_SCHAE-BR.xlsx`），上游 `EEPROM` 库用内部 flash 模拟、默认落在扇区 15，所以整库删除。要存用户数据用 SD 卡。从上游同步 core 时不要把这个库带回来，`P19` 会报红。

⚠️ **`RESERVED_TAIL_SECTORS`（`Core/Inc/usbd_cdc_flash.h`）当前值 1 是对的，别动。** 三处地址守卫都锚在 `IAP_STATE_SECTOR_ADDR` 上，一个都不看这个常量 —— 改它保护不了任何东西，只会静默弄坏 reclaim，而且不会编译报错。

## 3. 编译产物

**必须装进扇区 0 的 128K**（131,072 B；根区在扇区 15，扇区 0 只放代码）。这是需求 **ENG-01**，构建时的尺寸门禁。

**当前大小和余量哪份文档都不记** —— 这个数每次构建都在变。要数字跑 `$TEST/tools/build_image.py`，它每次构建都打印，超了当场 Fail；或者自己看 `Debug/` 下那个 `.bin` 的大小。

## 4. 功能模块清单

| 文件 | 功能 |
|---|---|
| `Core/Src/main.c` | 时钟/MPU/外设初始化，开机窗口读 BOOT0，主循环 `IAP_task()` + `MX_LWIP_Process()` |
| `IAPServer/IAP_server.c` | 命令状态机 + 启动决策（`server_decide()`）+ 交权（`server_jump_to_app()`） |
| `IAPServer/bootloader_state.c` | 扇区 15：metadata 的 append 与回收，回收时带走/写回校准值和根区 |
| `IAPServer/owner_slot.c` | 根区：认领、换主、撤销、恢复出厂、回收时压缩 |
| `IAPServer/bkp_stash.c` | 回收期间把根区和最后一条 metadata 暂存进备份 SRAM |
| `IAPServer/boot_selfupgrade.c` | `flashboot`：在 RAM 里擦写扇区 0 |
| `IAPServer/iap_cert.c` | 叶证书校验（根对叶公钥的签名） |
| `IAPServer/fw_verify.c` | ECDSA P-256 验签（micro-ecc） |
| `IAPServer/iap_auth.c` | 挑战应答认证；nonce 取自 RNG 外设，VBAT 见证在 `DR3` |
| `IAPServer/iap_keyderive.c` | 读芯片 UID（`getuid`、发现身份串、owner 记录） |
| `IAPServer/net_rand.c` | lwIP 的随机种子取自 RNG |
| `IAPServer/sha256.c` | SHA-256 |
| `IAPServer/IAP_boot_handoff.c` | **SRAM4 里的交接记录**：app 用它请求进上传模式，bootloader 用它把复位原因交给 app |
| `IAPServer/safe_outputs.c` | 开机和交权时把 DO、AO、KNX 发送脚置 0（决策 81） |
| `IAPServer/bor_check.c` | 开机检查 BOR 档位 |
| `IAPServer/tcp_server.c` | lwIP raw-TCP，端口 56865，固件传输通道 |
| `IAPServer/udp_server.c` | lwIP UDP 设备发现，含全设备发现限流 |
| `Core/Src/usbd_cdc_flash.c` | flash 擦除/编程，含扇区地址表 |
| `Core/Src/fmc.c` | 外部 SDRAM 初始化 + 上电时序 + 自检。**SDRAM staging 的基础** |
| `USB_DEVICE/*` | USB CDC 通道（1200 bps 敲门由 app 处理，不在这里） |
| `Core/Src/relay.c` | 继电器开关函数，只有工装固件调用；开机不动继电器（决策 71） |
| `Core/Src/crc.c` | 硬件 CRC32 |
| `Core/Src/rtc.c` | RTC 初始化。**不存「为什么进 bootloader」** —— 那在 SRAM4 |

## 5. lwIP 配置要点（`LWIP/Target/lwipopts.h`）

- `NO_SYS=1`、`WITH_RTOS=0`（裸机轮询，无 RTOS）
- `LWIP_DHCP=1`
- `LWIP_NETCONN=0`、`LWIP_SOCKET=0`（只用 raw API）
- `CHECKSUM_BY_HARDWARE=1`

## 6. 构建配置

只保留一个 Debug 配置（`-O0`）；Debug 图标和"直接烧录"图标都用它的产物，不再需要 Release。

---
