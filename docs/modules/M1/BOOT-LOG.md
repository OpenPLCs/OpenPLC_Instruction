# 开机日志缓存（SRAM4）

用户 2026-10-17 定（口 1 每次打开只吐没吐过的、一行最多 200 字节，都按这份）。要求见 [M1](../M1-firmware-upgrade.md) `R1-43`、[M3](../M3-app-runtime.md) `R3-22` `R3-23`。放 SRAM4 是为了存住电脑来不及打开口 1 的那段开机输出；链接脚本挖出这 4 KB，app 就不会把它当普通内存用掉。

bootloader 和 app 往同一块缓存里写系统日志；电脑打开 USB 口 1 时 app 把还没吐过的吐出去，IAPTool 随时能读全部。复位后保留，断电清空。

## 位置

| 项 | 值 |
|---|---|
| 起点 | `0x38000020`（紧接 32 字节交接记录，见 [BOOT-SEQUENCE.md](BOOT-SEQUENCE.md)「交接记录为什么放 SRAM4」） |
| 大小 | 4096 字节：32 字节头 + 4064 字节记录区 |
| 链接脚本 | 三份（bootloader 两份、板卡包一份）的 `RAM_D3` 改成 `ORIGIN = 0x38001020, LENGTH = 64K - 32 - 4096`，链接器放不进来 |
| 缓存一致性 | app 开着 D-cache 时，每写完一条就按地址清 cache 行（同交接记录的做法），否则软复位后内容丢在 cache 里 |

## 头（32 字节，一条 cache 行）

| 偏移 | 字段 | 说明 |
|---|---|---|
| +0 | `magic` u32 | `0x474F4C50`（"PLOG"） |
| +4 | `version` u16 | 1 |
| +6 | `size` u16 | 4096 |
| +8 | `head` u32 | 下一条写在记录区的哪个偏移 |
| +12 | `tail` u32 | 最旧一条在哪个偏移 |
| +16 | `seq` u32 | 下一条的序号 |
| +20 | `sent` u32 | 已经吐到口 1 的最后序号 + 1 |
| +24 | `check` u32 | `~(magic ^ version ^ size ^ head ^ tail ^ seq ^ sent)` |
| +28 | 保留 | 0 |

## 记录

| 字段 | 长度 | 说明 |
|---|---|---|
| 同步字节 | 1 | `0xA5` |
| 长度 `len` | 1 | 文本字节数，1–200；更长的拆成几条 |
| 序号 | 2 | `seq` 的低 16 位，用来查断档 |
| 文本 | `len` | 一行，不含换行，含前缀，如 `[sys][BL] Reset cause: POR` |
| 校验 | 1 | CRC-8（多项式 0x07），覆盖长度、序号、文本 |

记录区环形使用；放不下时从 `tail` 起整条丢最旧的。

## 前缀

一律 `[sys]` 加来源标签：

| 标签 | 谁写 | 例 |
|---|---|---|
| `[BL]` | bootloader 的全部 `printf` | `[sys][BL] ** APP Mod ...` |
| `[BOOT]` | core 进 app | `[sys][BOOT] millis=12` |
| `[NET]` | core 拿到 IP | `[sys][NET] ip=192.168.0.32 mac=…` |
| `[FAULT]` | 故障处理（bootloader 和 app） | `[sys][FAULT] HardFault pc=0x… lr=0x… cfsr=0x… hfsr=0x… bfar=0x…` |
| `[LOG]` | 缓存自己 | `[sys][LOG] buffer reset: corrupt` |
| `[KNX]` | `OpenPLC_KNX`（编程模式、ETS 重启、`-DKNX_DEBUG` 的协议栈输出）；只在板卡包里定义，bootloader 不用 | `[sys][KNX] programming mode on` |

app 里 `printf` 的行：自带 `[` 标签的保留原标签、前面加 `[sys]`；不带的只加 `[sys] `（`printf` 来自不同的库，标不出统一来源）。

## 什么时候查、坏了怎么办

bootloader 和 app 开机各查一次：头的 `magic` / `check` 对、从 `tail` 到 `head` 每条同步字节、长度、校验都对、序号连续，才算有效。

| 查到 | 处理 |
|---|---|
| `magic` 不对 | 上电冷启动或从没写过：初始化，不报 |
| 其余任何一项不对 | 整块丢掉、初始化，写一条 `[sys][LOG] buffer reset: corrupt` |
| `version` 比自己新 | 同上 |

## bootloader 怎么写

| 项 | 做法 |
|---|---|
| 初始化 | `main()` 里 `SCB_InvalidateDCache()` 之后、第一个 `printf` 之前调 `boot_log_init(cold)`，`cold` = 锁存的复位原因含 POR。不能更早：写完要按地址清 cache 行，D-cache 的 RAM 没初始化时按地址操作会 BusFault |
| `printf` | `__io_putchar` 写 SWO（ITM），同时按行攒进缓冲，遇换行加 `[BL]` 前缀写一条；空行不写，满 200 字节先写 |
| 跳 app 前 | `server_jump_to_app()` 把没换行的半行写掉 |
| 故障 | 故障处理先写一条 `[FAULT] <名字> pc= lr= cfsr= hfsr= bfar=`，再在 SWO 上打完整报告（报告的各行也作为 `[BL]` 进缓存） |
| 不阻塞 | 写缓存只关中断拷贝，SWO 每字符最多等 1000 次；没有 USB、UART 参与 |

## 读出

| 谁 | 读什么 |
|---|---|
| app，口 1 的 DTR 置位时 | 序号 ≥ `sent` 的各条依次吐出，再把 `sent` 推到最新；口开着时新写的一条同时直接发出 |
| `IAPTool log <ip>`（bootloader 和 app 都回，经网口 UDP `openplc_log`，见 [IAP-PROTOCOL.md](IAP-PROTOCOL.md)「`openplc_log`」） | 从 `tail` 到 `head` 全部，不动 `sent`。经 USB 口 2 读等双 CDC |
| `OPENPLC_SYSTEM_LOG(OFF);` 的 sketch | 照写缓存，不往口 1 吐 |

## 镜像

bootloader 和板卡包各一份实现，位置、头、记录格式、前缀必须一致，列入 [ARCHITECTURE.md](../../repo/ARCHITECTURE.md) 跨仓镜像，由 P2 比对。写入要关中断，故障处理里也能调。
