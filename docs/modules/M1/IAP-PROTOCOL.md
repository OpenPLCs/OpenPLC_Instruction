# IAP 协议 · bootloader 和 app 在线上认哪些命令

> `takeown` / `getpubkey` / `flashboot` 三行按[决策 72](../../tables/DECISIONS.md)；没有根时拒绝 `flashboot` 2026-10-08 上板通过（`T1-32`），IDE 上传时第一次认领上板待验。

**这份是命令一览。** 每条命令的格式、要不要认证、会回什么。
为什么是这个形状，各自的专门文档里写着，这里只给指针。

实现：bootloader 在 [`IAP_server.c`](../../../../OpenPLC_BootLoader/IAPServer/IAP_server.c) 的 `process_command()`
和 [`udp_server.c`](../../../../OpenPLC_BootLoader/IAPServer/udp_server.c)；
app 在 core 的 [`udp_server.c`](../../../../open_plc_arduino/libraries/OpenPLC_IAP/src/udp_server.c)。
**命令表以代码为准**，两边对不上时是这份文档过期了。

## 传输

| 通道 | 谁在听 | 端口 / 形式 |
|---|---|---|
| TCP | bootloader | `OPENPLC_SERVER_PORT`（56865），定义在 `$BOOT/Core/Inc/IAP_config.h`。同时只接一个连接，第二个直接拒绝（`IAPServer/tcp_server.c` `_accept()`） |
| UDP | bootloader 和 app | 同一个端口。只收发现、（app 的）重启请求、读开机日志和只读查询 |
| USB CDC | bootloader | 和 TCP 同一个命令解析器；不理 1200 波特率 |
| USB CDC | app | 不收命令（只读查询等双 CDC 之后在 USB 口 2 上回，决策 148）。主机把波特率设成 1200（`MAGIC_CDC_RATE`）就写交接记录 `BOOT_REQ_CDC` 并复位进 bootloader，**无认证**（core `usbd_cdc_if.c` 的 `CDC_SET_LINE_CODING`） |

**TCP 和 CDC 上一条命令以 `\n` 或 `\r` 结尾，按前缀匹配**（`process_command()` 用 `strncmp`）。没有结尾的残片 500 ms 后丢弃。
一条命令可以跨多个 TCP 段 / USB 包到达。

**UDP 一个数据报就是一条命令，不带换行，按整串精确匹配**（`strcmp`；`openplc_log` 例外，见下）。回答也不带换行。接收缓冲 bootloader 64 字节、app 512 字节，超出的截掉。

## bootloader 的命令（TCP / CDC）

| 命令 | 认证 | 回答 |
|---|---|---|
| `openplc_server_where_r_y` | 无 | 身份串，五段 `名称_UID_角色_卡包版本_-`，角色是 `BOOTLD` 或 `BOOTLD-INVALID`（没有可启动的 app） |
| `ping` | 无 | `OK` |
| `info` | 无 | bootloader 版本串（`Boot Loader <版本>` 加回车换行）。**只在 bootloader 的 TCP / CDC 上回**，见「只读查询」 |
| `getuid` | 无 | 机器 ID（十六进制）。这条和下面三条是只读查询，UDP 上 bootloader 和 app 也回 |
| `getpubkey` | 无 | 板子**当前信任的根**公钥，128 个十六进制字符；**没有根时回 `none`**。IAPTool 靠它判断要不要自动认领 |
| `getowner` | 无 | 当前 owner 记录的 generation，未认领为 `0` |
| `getapprevoked` | 无 | `yes` / `no` / `none` —— 签装着那个 app 的叶有没有被撤销；`none` 是没有可启动的 app |
| `authchallenge` | 无 | 一个 nonce（32 个十六进制字符）；RNG 失败回 `ERR`。见 [CHALLENGE-AUTH.md](CHALLENGE-AUTH.md) |
| `takeown <公钥hex>` | **不设门**（决策 72），USB 或网口都行；**只在板子没有根时接受** | `OK` / `Refused` / `Bad key`。只用于第一次认领，IDE 上传时由 IAPTool 自动发 |
| `setowner <gen> <新公钥hex> <签名hex>` | 当前主人的签名 | `OK` / `Refused` / `Bad args` / `Bad length` / `Bad hex` |
| `setownerwipe <gen> <新公钥hex> <签名hex>` | 同上 | 成功时板子复位、**不回话**；回 `Refused` 说明什么都没擦 |
| `revoke <叶公钥前 16 字节hex> <签名hex>` | 当前主人的签名 | `OK` / `OK already revoked` / `Refused` / `Bad …` |
| `flash <size> <crc32hex> <镜像签名hex> <证书hex> <nonce签名hex>` | 叶证书 + 挑战应答 | 见下一节 |
| `flashboot …` | 同 `flash` 的字段；镜像签名用 **owner 根**验，**没有根时拒绝** | 见 [FLASHBOOT.md](FLASHBOOT.md) |
| 其他 | — | `Unknown command`。UDP 上不认的命令不回：bootloader 只打日志，app 什么都不做 |

签名覆盖哪些字节、证书格式：见 [M2 归属与信任](../M2-ownership.md) 和 [CHALLENGE-AUTH.md](CHALLENGE-AUTH.md)。

## 一次 `flash` 的往返

1. 发 `authchallenge`，拿到 nonce
2. 发 `flash …`。nonce 签名覆盖 `sha256(nonce ‖ "flash <size> <crc32hex> <镜像签名hex>")`。
   通过回 `OK`，进入接收；板子没有根时回 `Refused`（同 `flashboot`），其他不通过回 `ERR`，**都不擦任何东西**
3. 发镜像字节，每收一块回 `OK`，先落进 SDRAM
4. 收齐之后校验，回答是下面之一。⚠️ 最后一块的 `OK` 先发，结论紧跟其后，两段可能落在同一次读里

| 回答 | 意思 |
|---|---|
| **（不回话，板子复位后重新上线）** | 成功。复位会把 MAC 和 USB 一起带走，所以成功在线上是沉默的：网口只能靠「板子重新上线」确认，USB 上是 COM 口随复位消失（`$BOOT` `IAPServer/IAP_server.c` 里只有接受这条路复位） |
| `Checksum Failed` | CRC 不对；带后缀 `- SDRAM staging buffer failed its self-test` 时是暂存区坏了 |
| `No Signature` | 没带有效签名 |
| `Signature Failed` | 签名不对、叶被撤销，或开机时的密码学自检失败 |
| `Flash Failed` | 镜像是好的，写 flash 失败，重传即可 |
| `Failed` | 发送的字节超过暂存区 |

## UDP

| 发 | 谁回 | 回答 |
|---|---|---|
| `DISCOVER` / `openplc_discover` / `openplc_server_where_r_y` / `ping` | bootloader 和 app | 身份串。app 的第五段是 sketch 的版本号，bootloader 是 `-`。整台设备有发现限流 |
| `openplc_server_reboot_challenge` | app | nonce；RNG 失败时**不回** |
| `openplc_server_reboot <证书hex> <nonce签名hex>` | app | 不回。通过就复位进 bootloader。签名覆盖 `sha256(nonce ‖ "openplc_server_reboot")`；有冷却时间，窗口内重复的请求被忽略 |
| `openplc_log [<from>]` | bootloader 和 app | 开机日志缓存里序号 ≥ `from` 的记录，见下一节。无认证；有自己的整台设备限流 |
| `getuid` / `getpubkey` / `getowner` / `getapprevoked` | bootloader 和 app | 和 TCP 上同一条命令的回答一字不差，见「只读查询」 |

app 不认 TCP 上的任何命令；要烧写或改归属，先用上面这条把它送进 bootloader。

### `openplc_log`：读开机日志缓存

`IAPTool log <ip>` 用它把 [BOOT-LOG.md](BOOT-LOG.md) 的整个缓存分几次读出来（`R3-22`）。按 `boot_log_read_all` 读，**不动 `sent`**。

| 项 | 约定 |
|---|---|
| 请求 | `openplc_log <from>`，`from` 是十进制序号；不带就是 0。`openplc_log` 后须紧跟空格或串尾 |
| 回答 | ASCII，整包不超过 1024 字节：首行 `log <next> <more>`，其后每条记录一行 `<seq> <文本>`，都以 `\n` 结尾 |
| 取哪些 | 序号 ≥ `from` 的记录从旧到新，放到下一行会超 1024 字节为止；`from` 比最旧一条还旧时从最旧一条起，断档从序号上看得出 |
| `next` / `more` | `next` 是下一次该请求的 `from`；`more` 为 `1` 表示因为装不下而停，`0` 表示已到最新 |
| 文本 | 记录里的 `\r` `\n` 换成空格，保证一条一行 |
| 认证 | 无：内容和发现回答一样不含秘密（UID、IP、复位原因、故障寄存器），只读 |
| 限流 | 整台设备每秒最多 20 个回答，超出的请求静默丢弃：一次读满约 5 个回答，上限把它当反射放大器时的流量压在约 20 KB/s（同发现限流的理由，决策 3） |
| 谁回 | bootloader 和 app，格式和限流相同（决策 148，跨仓镜像 20）；读不到时 IAPTool 报「没有回答，固件可能太旧」 |

### 只读查询：app 运行时也回

`getuid` `getpubkey` `getowner` `getapprevoked` 四条，板子在 bootloader 还是 app 里都回，回答文本和上面 bootloader 命令表一样（决策 148，跨仓镜像 21）。IAPTool 的 `getowner` / `getapprevoked` 和改归属前读状态，碰到 app 就走 UDP 问，不重启板子。

| 项 | 约定 |
|---|---|
| 请求 | 命令名整串精确匹配，不带参数 |
| 回答 | 两边同一个函数 `iap_query_reply()` 拼的文本；bootloader 的 TCP / CDC 也调它，只是前缀匹配不变 |
| 认证 | 无：只读，内容和发现回答一样不含秘密（公钥是公开的） |
| 限流 | 整台设备每秒最多 20 个回答，超出的静默丢弃；和发现、`openplc_log` 各算各的 |
| `getapprevoked` 在 app 里 | app 在跑就说明 bootloader 判过它有效，所以只看扇区 15 最新那条 metadata（app 自己按 bootloader 的扫法读，[SECTOR-15.md](SECTOR-15.md)「上电：扫一遍」） |
| `info` | **只在 bootloader 的 TCP / CDC 上回**：版本串编在 bootloader 镜像里、没有固定地址，app 只知道自己编译时的板卡包版本，答不出板上装的是哪版 bootloader |
| USB | app 的 USB 口现在不收命令；双 CDC 之后口 2 也回这四条 |
