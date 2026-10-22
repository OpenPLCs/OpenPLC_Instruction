# 给用户的接口约定

**有状态的外设一个对象、`begin()` 起；无状态的板级调用是 `openplc` 前缀的 camelCase 函数；引脚常量不带 `_Pin` 后缀。** snake_case 的 `openplc_*` 不进用户 include 的头文件。

| 端口 | 用户用什么 | 引脚常量 | 落地 |
|---|---|---|---|
| USB 口 1 | `Serial`（即 `SerialUSB`）：用户的打印，系统日志的 `[sys]` 行也在这（`R3-22` `R3-23`，[M3](../M3-app-runtime.md)） | — | 待改（`R3-22` `R3-23`） |
| RS232（C05 / C06） | `RS232`：`HardwareSerial`，USART3，只给用户程序接设备；`RS232.begin()` 才打开收发器，core 不往它写（`R3-23`） | `RS232_TX` `RS232_RX` `RS232_EN` | ✅ 2026-10-14 上板 `RS232_Echo` 过；收发器改由 `begin()` 打开待改（`R3-23`） |
| RS485（端子见 [HARDWARE-FACTS.md](../../hardware/HARDWARE-FACTS.md)） | `RS485`：core 定义的对象，USART2；`write()` 时自己拉高 `RS485_DIR`、发完（等到 TC）再拉低，用户不碰方向脚 | `RS485_TX` `RS485_RX` `RS485_DIR` | ✅ 2026-10-14 上板 `RS485_Echo` 过 |
| 以太网 | `Net`：`linkUp()` `hasIP()` `localIP()`（`IPAddress`，没拿到地址时 0.0.0.0）`macAddress(mac)`；core 开机就起网络（IAP 要用），没有 `begin()`。`openplc_net_*` `openplc_udp_server_*` 的声明在 core 内部头文件 `stm32/openplc_net.h`，两个 `*_Autostart.h` 只留给依赖扫描、不再声明函数 | — | 2026-10-14 改完，模拟过（Renode `T3-11` `Ethernet_IP`），2026-10-15 上板过（`T3-06`） |
| SD 卡 | `SD`：`SD.begin()` 不带参数，固定用卡检测脚（低 = 插着，[HARDWARE-FACTS.md](../../hardware/HARDWARE-FACTS.md) `SDIO1_CD`）；`SD.cardPresent()` 不用先 `begin()` | `SDMMC_CD`（其余 SDMMC 脚只有驱动用，不给常量） | 2026-10-14 改完，模拟过（Renode `T3-11` `SD_ReadWrite` `SD_FileReceive`），2026-10-15 上板过（`T3-06`，含拔插卡各报一行） |
| CAN、SDRAM、KNX | `CAN` `SDRAM` `KNX`，已是对象 + `begin()` | `CAN_TX` `CAN_RX`（只有 `CAN` 内部用） | CAN 引脚 2026-10-14 改完，模拟过（Renode `T3-11` `CAN_Counter`），2026-10-15 上板过（`T3-06`） |
| AI / AO、复位原因、VREF、YMODEM | `openplcXxx()` 函数，无状态；复位原因只留 `openplcResetCause()` 一个入口。`openplc_calib.h` 的 snake_case 是跨仓镜像，不动 | — | 2026-10-14 改完，待验证 |

**关掉系统日志**：sketch 里写一行 `OPENPLC_SYSTEM_LOG(OFF);`（同 `OPENPLC_APP_VERSION` 的写法，`ON` 是默认），系统日志照样进开机缓存、`IAPTool log <ip>` 照样读得到，只是不往 USB 口 1 吐（`R3-23`）。

**KNX 角色**：用 `OpenPLC_KNX` 的 sketch 在 `.ino` 里写一行 `OPENPLC_KNX_ROLE(TP_DEVICE);` 或 `OPENPLC_KNX_ROLE(IP_ROUTER);`（同 `OPENPLC_APP_VERSION` 的写法），没写就编不过；IDE 菜单里没有 KNX 角色（`R3-24`，[M3](../M3-app-runtime.md)）。

**认出是哪块板**：电脑打开板子的 USB 口 1（串口监视器连上、DTR 从无到有）时，心跳灯（LED3，`PE2`）快闪约 2 s，然后 `PE2` 回到原来的模式和电平；这 2 s 里 sketch 对 `PE2` 的改动在结束时生效，不用让出这个脚。IDE 端口列表里板子的 COM 口旁标出 `OPEN-PLC`（`R3-25`，[M3](../M3-app-runtime.md)）。

**故障处理**：core 的 `HardFault_Handler` 等四个是弱定义，把故障写进开机日志后复位；sketch 自己定义同名函数就用 sketch 的（2026-10-18 编译核实）。

**不动的**：跨仓镜像（[ARCHITECTURE.md](../../repo/ARCHITECTURE.md) 镜像表，P2 查）、两个 `*_Autostart.h` 的文件名、`OPENPLC_APP_VERSION`。
