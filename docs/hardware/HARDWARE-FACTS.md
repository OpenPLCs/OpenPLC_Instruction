# 硬件实测事实

这里每一条都核实过，标注了核实方式和日期。**没核实的不要往这里写。**

> 排查引脚问题时 `Hardware/Production/UpperDeck/netlist.ipc`（IPC-D-356 网表）比原理图 PDF 快得多：
> `grep -E "U5 +-[0-9]+" netlist.ipc` 直接列出每个引脚在哪个网络。

## RS232 路径（PC10 / PC11 / PB10）

核实：KiCad 原理图 `OpenPLC_UpperDeck_R3.pdf` 第 5 页（2026-08-07）+ `netlist.ipc` 逐脚（2026-08-10）。

MAX3221EIPWR（U5），网名 `TXD_RS232_PC10`、`RXD_RS232_PC11`、`ENABLE_RS232_PB10`：

- **PC10 → U5 DIN**（收发器输入，高阻）
- **PC11 ← U5 ROUT**（收发器**输出**，推挽 —— 绝不能从外部往这里灌信号，曾因此出现"发得出收不到"的现象）
- **PB10 = 使能**，高有效，经 MOSFET Q5
- 外部设备接**端子 C05 (TxD) / C06 (RxD) + GND (C02/C11/C12)**，那里是真正的 RS232 电平（±12V）—— **TTL 适配器接上去可能烧掉适配器**

### PB10 拉低 = 整片关断，不只是"不能读"

一个 GPIO 驱动 MAX3221 的**两个**控制脚，其中一条经 MOSFET **反相**：

| PB10 | U5-12 `FORCEOFF` | Q5 (SI2356DS) | U5-1 `EN` | 芯片状态 | 能发能收 |
|---|---|---|---|---|---|
| 低（R68 下拉，**默认**） | 0 | 关断 → R67 上拉 | 1 = 接收器输出高阻 | **Shutdown，电荷泵停转** | 都不行 |
| 高 | 1（`FORCEON` U5-16 永久接 3V3） | 导通 → 漏极接地 | 0 = 接收器输出使能 | Normal | 都行 |

关键：RS-232 的 ±5V 线电平由芯片内部**电荷泵**升压产生，泵一停，发送驱动器**物理上产生不出电平** —— 所以 **PB10 为低时 printf 一个字节都到不了线上**。

⚠️ 函数名 `Enable_RX_RS232` 只描述了 `EN`（接收器三态）那一半，漏掉了 `FORCEOFF`（整片开关）这更重要的一半，容易误判成"只影响接收"。

### app 里由 `RS232.begin()` 打开

core 开机不碰 PB10（保持 R68 下拉的低，芯片关断）；`RS232.begin()` 配好 PC10 / PC11 之后再拉高，`RS232.end()` 拉低（`R3-23`，[M3](../modules/M3-app-runtime.md)）。

bootloader 不拉高 PB10（`R1-43`）；只有工装镜像（`PORTTOOL_ENABLE=1`）为了把 UART4 当命令口才打开。


### 电荷泵余电：关了收发器之后仍有几个字节能出来

MAX3221 的 ±5.5V 线电平由**电荷泵**用几只外部电容产生。PB10 拉低时泵停止开关，但电容上的电荷是**指数衰减**的，衰减期间驱动器仍能产生合规的 RS-232 电平。

| 现象 | 机制 |
|---|---|
| bootloader 交权前关了收发器，app 的 `[BOOT] millis=12` 仍然出得来（2026-09-19 实测，决策 100 之前） | 交权后 12 ms，余电还够 |

余电只决定收发器关掉后还能漏出几个字节。

## UART4 与 USART3：同两个引脚，两个复用功能

`PC10 / PC11` 上有两个可选功能：**AF8 = UART4，AF7 = USART3**。

- bootloader 的 printf 控制台现在走 **UART4**，到 MAX3221 再到 RS232 端子 C05/C06（`R1-43` 落地后不再往 RS232 打印）
- core 里的 `RS232` 走 **USART3**（`core:cores/arduino/main.cpp` 的 `HardwareSerial RS232(PC_11_ALT1, PC_10_ALT1)`）。**`ALT1` 就是选 AF7 的写法**，线一根没变

`PH13 / PH14` 那一对也是 UART4（接到扩展口 JunctionLink J4-11 / J4-12）。**同一个 UART 外设只有一个句柄槽位，最后一次 `begin()` 赢** —— 所以 app 侧的控制台放在 USART3 上，扩展口才拿得住 UART4（下表）。

### app 侧三条通道各走哪个外设（2026-09-20 定）

| 谁 | 外设 | 引脚 | 出口 |
|---|---|---|---|
| `printf` / stdout、`core_debug` | 不走 UART | — | 系统日志：SRAM4 开机缓存 + USB 口 1（就是 `Serial`），`R3-22`；代码在 `$CORE_REPO/cores/arduino/Print.cpp` 的 `_write` |
| `RS232` | **USART3** AF7 | PC10 / PC11 | RS232 端子 C05 / C06，只归 sketch |
| `Serial1`（`PIN_SERIAL_TX` / `PIN_SERIAL_RX`） | **UART4** AF8 | PH13 / PH14 | JunctionLink 扩展口 J4-11 / J4-12 |

工装固件不一样：它的命令和日志都走 RS232 端子（UART4 接在同一对脚上，决策 147 的例外）。
`DEBUG_PINNAME_TX` 必须显式写成 `PC_10_ALT1`：不写的话 core 会取 `PeripheralPins.c` 里第一个
USART3 TX，那是 **PB10 —— 本板的 RS232 使能脚**。

两个宏定义在 `core:variants/STM32H7xx/H743/variant_PLC_H743.h`，由用例 `P4`（变体断言，
`$CORE_REPO/tests/variant_check/uart_routing/`）钉住，改错编译就不过。

⚠️ **bootloader 侧不受这条影响** —— 它有自己的 `_write`，`printf` 一直走 UART4 / PC10。

### USART3 在这颗芯片上有三组引脚，本板只有一组能用

核实自 `$HW/STM32H743IIK6_GPIO_ASSIGNMENT_Schaeffer_Bridge_20260822.xlsx` 的「复用功能 Alternate Functions」列。⚠️ **查复用功能一律用这份，不要用 core 的 `PeripheralPins.c`** —— 那是跟着硬件走的抄件。

| 组 | TX | RX | 本板这两个脚的信号名 |
|---|---|---|---|
| 一 | PB10 | PB11 | `RS232_EN` / `RMII_TX_EN` —— 都占了 |
| 二 | **PC10** | **PC11** | `RS232_TXD` / `RS232_RXD` —— **唯一可用的一组**；bootloader 用 UART4(AF8)，app 用 USART3(AF7) |
| 三 | PD8 | PD9 | `FMC_D13` / `FMC_D14` —— SDRAM 数据线 |

**所以「把控制台从 UART4 挪到 USART3、把 UART4 让给扩展口」只有 PC10/PC11 这一种走法，线一根不用动**（[DECISIONS.md 第 35 条](../tables/DECISIONS.md)把它记成了重开条件）。

⚠️ **`Serial` 不是 `Serial4`。** 当前 FQBN 用 `usb=CDCgen`，`WSerial.h` 的 `#if !defined(Serial)` 守卫让 `Serial` 保持为 USB CDC，**碰不到 UART4**。要验 UART4 的行为必须显式用 `Serial4`。

## USB 菜单影响 `Serial` 的含义

当前 FQBN 用的是 `usb=CDCgen`，此时 `Serial` 被 `#define` 成 `SerialUSB`，**它不是硬件串口**。已在设备上证实：全用 `Serial` 的回显 sketch 是通过 USB CDC 回显的。

## USB FS 只接了 PA11 / PA12

2026-09-28 核实自 xlsx `GPIO_ASSIGNMENT` 行 60/61/123/124/143 和 `Hardware/Production/UpperDeck/netlist.ipc`：USB 只有 D-/D+（PA11 / PA12），**没有 VBUS、ID、SOF**。OTG_FS 的另外三个候选脚另有他用：

| 脚 | 板上是 |
|---|---|
| PA8 | `HSFET_5`（Digital Out 5） |
| PA9 | `HSFET_6`（Digital Out 6） |
| PA10 | `KNX_RX` |

**软件含义**：板卡包的 `PinMap_USB_OTG_FS[]` 只该有 PA11 / PA12 —— USB 初始化会把表里每一条都配成 USB 功能，多一条就抢走一个脚。

## PG9 就是 BOOT0 网

核实：Bridge 原理图第 5 页网表 + 实测（2026-08-12）。

网络 `KNX_Prog_KEY` = **PG9（U1 ball C10）+ BOOT0（ball D6）+ SW2 pin1 + R58 (10k) + J2 pin9**。

**PG9 不是普通 GPIO，它决定 MCU 的启动源。**

**R58 = 下拉到 GND**（实测：PG9 配 PULLUP / PULLDOWN / NOPULL 各读一次，三次全 0）。由此：

1. BOOT0 网静态为低 → 复位必然从 flash 启动，不会进 ROM DFU
2. `boot0_is_pressed()` 的 active-high 判断**正确**（SW2 按下拉到 3V3）
3. PG9 **只能配成输入**：配成推挽输出时按下 SW2 = 3V3 经引脚对地短路

PG9 配成 input 不影响复位行为：**复位那一刻 MCU 所有 GPIO 都回到默认态**，固件配的推挽输出在那个瞬间并不存在，压住这条网的始终只有 R58 那个 10k 下拉。

**PG9 的输入配置在 `.ioc` 里**：`PG9.Signal=GPIO_Input`，生成的 `MX_GPIO_Init()` 直接配成
`GPIO_MODE_INPUT` + `GPIO_NOPULL`。实测（2026-09-16，SWD 直读）：
bootloader 阶段 `GPIOG_MODER` 的 PG9 位是 `00`，松开 `IDR` bit9 = 0、按住 = 1，启动日志同步报
`BOOT0 button is pressed!`。

⚠️ **app 跑起来之后，PG9 回到模拟模式（`MODER` 位 = `11`），`IDR` 恒读 0。**
Arduino core 不配这个脚，它停在复位默认值，而**模拟模式断开数字输入缓冲器**。
**所以要量 BOOT0，只能在 bootloader 阶段量** —— 在 app 阶段读 IDR 会得到「没按」的假象。

### 有过一份「改成输入把 RESET 键弄坏了」的报告，那是误判

⚠️ **真因是同一次改动里删掉了 `SystemClock_Config()`** —— MCU 因此在 VOS3 + 64 MHz + 0 等待周期
下读 flash，超出规格。**和这个引脚无关。**

## SDRAM 占掉的 39 个脚（用户 sketch 碰得到）

权威清单在 `Core/Src/fmc.c` 的 `HAL_FMC_MspInit()` 里那段 `FMC GPIO Configuration` 注释（2026-08-17 时在 `:224-264`，**行号会漂，按函数名找**）。

这 39 个脚**只连**板载那颗 AS4C32M16SB（64MB，映射在 `0xC0000000`），别的什么都不接。

| 组 | 数量 | 脚 |
|---|---|---|
| 数据 `D0–D15` | 16 | PD14 PD15 PD0 PD1 · PE7–PE15 · PD8 PD9 PD10 |
| 地址 `A0–A12` | 13 | PF0–PF5 · PF12–PF15 · PG0 PG1 PG2 |
| 控制 | 10 | PG4 PG5（BA0/1）· PE0 PE1（NBL0/1）· PG8（SDCLK）· PH2（SDCKE0）· PH3（SDNE0）· PF11（SDNRAS）· PG15（SDNCAS）· PC0（SDNWE） |

⚠️ **变体把 MCU 全部引脚都注册成 Arduino 数字引脚**（`NUM_DIGITAL_PINS 140`），所以用户写 `digitalWrite(PE7, HIGH)`（PE7 = `FMC_D4`）**能编译、能运行、把 SDRAM 数据线拽死**。现象是"SDRAM 偶发读到垃圾"，而且和肇事那行代码之间没有任何提示。

**2026-08-17 起这 39 个脚在变体头里有名字了** —— `core:variants/STM32H7xx/H743/variant_PLC_H743.h` 的 `FMC_RESERVED_*`。**起名不阻止任何事**（`digitalWrite(PE7, ...)` 照样编得过，这是刻意的），只是让人在头文件里就能看见。改 `fmc.c` 的引脚时**两边都要改**，`FMC_RESERVED_PIN_COUNT` 那个 39 是给编译期断言用的锚。

**这不是排布错误** —— 这 39 个脚和本板所有对外 IO（DOUT×8 / DIN×8 / AIN×2 / AOUT×2 / RS232 / RS485 / CAN / KNX）一个都不撞，连 BOOT0 的 PG9 都恰好夹在 PG8 和 PG15 中间空着。**是缺一道防护。**

### 这条总线上没有任何可以下探头的地方

**查的是** `Hardware/Production/Bridge/1436_01_SCHAE-BR` 的 Sheet 5（MPU）和 Sheet 6（Memory）。

| | |
|---|---|
| 两端封装 | U1 `STM32H743IIK6` **UFBGA176，0.65 mm 球距**；U6 `AS4C32M16SB-7BIN` **54-ball FBGA，0.8 mm** |
| 中间有没有器件 | **一个都没有**。16 根数据线全部是球到球直连，无串联电阻、无排阻、无测试点 |
| 板上仅有的 4 个测试点 | TP1 / TP2 `/RESET`、TP3 `VREF`、TP5 `ETH_nINT` —— 都不在总线上 |
| 已核实的球号 | `FMC_D0` = `PD14` = U1 **ball M14** ↔ U6 **ball A8**；`FMC_D1` = `PD15` = U1 **ball L14** ↔ U6 **ball B9** |

⚠️ **别再提"量某根数据线的电阻"或"用示波器看 SDRAM 那一端"** —— 两端出线都在封装阴影内（0.65 mm 球距的扇出过孔只能落在那里），万用表和示波器都没有落点。数据总线上的故障**只能靠软件、冷热喷剂、X-ray 或换板对照**去定位。

⚠️ **R32 / R33 那两个 0Ω 不在 `FMC_D2/D3` 上**，它们在 32.768 kHz 晶振（`XTAL2`）那一路。`PD0`（U1 ball B12）和 `PD1`（ball C12）到 SDRAM 同样是直连。

## RTC 走 LSE，实测 180 s 不差秒

2026-09-10 用户在 CubeMX 里改完并重新生成之后实测。决定在 [DECISIONS.md 第 36 条](../tables/DECISIONS.md)，重新生成后的必查项在 [CUBEMX-RULES.md](../build/CUBEMX-RULES.md)。RTC 走时校准只在 LSE 上才有意义。

| 项 | 实测 |
|---|---|
| 时钟源 | `pt.run rtc.read` 回 **`clk=lse`**。⚠️ 这个字段读的是 `RCC_BDCR.RTCSEL`，不是写死的文字 —— 它**曾经**是写死的 `lsi`，换 LSE 那天就变成了谎话 |
| 走时 | **RTC 走 180 s，PC 时钟走 180.0 s**。⚠️ RTC 只报到秒，所以这只能说明「误差 < 1 s / 180 s」。**够用了** —— LSI 的 ±5% 在 180 s 上是 ±9 s，一眼就能看出来，而这里看不出来 |
| 起振 | **没有 5 秒停顿。** 复位后板子立刻出 banner。晶振要是没起振，`HAL_RCC_OscConfig()` 会阻塞到 `LSE_TIMEOUT_VALUE`（5000 ms） |
| 掉电保持 | ✅ 2026-09-19 真断电（ST-Link 量到 0.00V）后备份寄存器里的值还在。⚠️ **两边 RTC 时钟源必须一致**，否则每次 bootloader ↔ app 切换都会清空备份域，见 [DECISIONS.md 第 57 条](../tables/DECISIONS.md) |

## 时钟源：板上的晶振，和 HSI48 / LSE 的规格余量

2026-10-22 核实。晶振型号出自 Bridge 贴片表和 BOM（`$HW/Production/Bridge/`）；哪颗 25 MHz 接 MCU 出自 `$HW/Bridge_overview.txt`，网表没逐脚核对。用法定在 [DECISIONS.md 第 157 条](../tables/DECISIONS.md)。

| 项 | 事实 | 出处 |
|---|---|---|
| HSE | `XTAL3` ABM8AIG-25.000MHZ-12-2Z，无源晶体，所以是 `RCC_HSE_ON` 不是 BYPASS。另一颗 25 MHz（`XTAL1` ABM3B）只给以太网 PHY | Bridge 贴片表、BOM |
| LSE | `XTAL2` ABS07-120-32.768KHZ-T：CL 6.0 pF，ESR 典型 55 kΩ、最大 60 kΩ | Abracon 手册 2021-05-26 版 |
| HSE 的负载电容 | `C48`、`C49` 各 3.9 pF 到地。型号里的 `-12` 按 Abracon 的命名应是 CL 12 pF，手册没对过 | `$HW/Production/Bridge/1436_01_SCHAE-BR.pdf` 第 5 页、`1436_01_SCHAE-BR.xlsx` |
| LSE 的负载电容 | `C46`、`C47` 各 1.5 pF 到地，串 `R32`、`R33` 0 Ω | `$HW/Production/Bridge/1436_01_SCHAE-BR.pdf` 第 5 页 |
| HSI48 不校准的精度 | 30 °C 时 47.5–48.5 MHz（±1%），−40–125 °C 时 −4.5%–+3.5%；USB 全速要求 ±0.25%，所以 **USB 用 HSI48 必须开 CRS** | DS12110 Rev 10 表 46 |
| LSE 各档能带的晶振 gmcrit 上限 | `LOW` 0.5、`MEDIUMLOW` 0.75、`MEDIUMHIGH` 1.7、`HIGH` 2.7 µA/V | DS12110 Rev 10 表 45 |
| LSE 驱动档什么时候能改 | **LSE 开着时改不动**，要先关 LSE 再设。rev Y 上两个中档的寄存器编码对调，读写都要按芯片版本换算 | HAL `stm32h7xx_hal_rcc.h:7734`、`:7746`（RM0433 原文没核对） |
| 本晶振的 gmcrit | 按 AN2867 的 4·ESR·(2πF)²·(C0+CL)²（C0 取分销商标的 1.2 pF）：典型 0.48、最大 **0.53 µA/V**，**`LOW` 档不够** | 计算 |
| 各档起振用时（实测） | 2026-11-03 板子 UID …0029：`LOW` / `MEDIUMLOW` / `MEDIUMHIGH` / `HIGH` 都是 130–132 ms，每档 2 次都起振、没有 `fallback`。四档几乎一样，多半是 LSERDY 本身的固定延时（约 4096 个 LSE 周期 = 125 ms），RM0433 原文没核对 | PortTool 晶振页 `rtc.lsemargin` |
| 各档频率偏差（实测，对 HSE 量） | 同一块板：`LOW` −31.3、`MEDIUMLOW` −43.2、`MEDIUMHIGH` −60.4、`HIGH` −90.6 ppm，驱动档越高频率越低。`MEDIUMLOW` 连量 10 分钟（594 次）−43.35 到 −42.90 ppm，漂移 0.45 ppm。读数含 HSE 自己的误差 | PortTool 晶振页 `rtc.lsemargin`、`rtc.lsefreq` |
| 两颗晶振对真实时间（实测） | 同一块板、`MEDIUMLOW`：RTC 对 NTP 时间快 **+44 ppm**（±10，量了 31 分钟），即 LSE 快约 44 ppm；与上一行合起来，HSE 快约 87 ppm。两颗都超出 ±20 ppm 的容差，方向都是偏快，和两组负载电容都比晶振要求的小对得上（这个因果没验证） | `$PORTTOOL/TestCase/tools/rtcdiag.py`，2026-11-03 |
| 480 MHz | 只有 rev V 芯片能跑，且结温不超过 105 °C。本板芯片是 rev Y 还是 rev V **没核实** | DS12110 Rev 10 第 22 页脚注 |

## SRAM4 的 no-init 机制

bootloader 的两个链接脚本（`STM32H743IIKX_FLASH.ld`、`STM32H743IIKX_FLASH_PORTTOOL.ld`）和板卡包的 `ldscript.ld` 都把 SRAM4 前 32 字节挖出来给 boot handoff 记录（`RAM_D3 ORIGIN = 0x38000020`）。

启动代码不碰这 32 字节，所以放在那里的变量**能活过软复位**（掉电仍然丢）。

**将来需要"跨软复位保留、又不想依赖 VBAT"的状态时，用这个机制扩展即可**，不要另起炉灶去用 RTC 备份寄存器。

`CMakeLists.txt` 和 `cmake/gcc-arm-none-eabi.cmake` 用的是 `STM32H743IIKX_FLASH.ld`。

## Digital In 八路：MCU 侧有外部 10k 上拉，固件不要再开内部上拉

2026-08-27 逐条追 `Hardware/Production/UpperDeck/netlist.ipc` + `bom.csv` 得到，为写板级用例 1 而查。

每一路都是同一个形状，从比较器到 MCU 一共三个元件：

```
LM339LV 开集输出（U3/U4）──┬── 10k 上拉到 +3V3
                          └── 50R 串阻 ── UpperDeck J7 ── MCU 引脚
```

| Digital In | MCU 引脚 | 10k 上拉 | 50R 串阻 | J7 管脚 |
|---|---|---|---|---|
| 1 | PC6 | R60 | R76 | J7-9 |
| 2 | PB5 | R61 | R77 | J7-10 |
| 3 | PB6 | R66 | R78 | J7-11 |
| 4 | PB7 | R59 | R75 | J7-12 |
| 5 | PH10 | R43 | R71 | J7-13 |
| 6 | PH11 | R44 | R72 | J7-14 |
| 7 | PI5 | R45 | R73 | J7-15 |
| 8 | PI6 | R46 | R74 | J7-16 |

**对固件的意义**：DIN 引脚配 `GPIO_MODE_INPUT` + `GPIO_NOPULL` 就够了。开集输出遇到"读不到高"的第一反应通常是打开 MCU 内部上拉 —— 这里**不要**：内部约 40k 并上外部 10k 会拖慢上升沿，而且一旦哪块板漏贴了上拉电阻，内部上拉会把这个缺陷盖住，测不出来。

**比较器有供电**时，空载（端子上没有电压）比较器「+」节点被 1k1 拉到 0 V，低于 0.400 V 基准，输出管导通主动灌地 —— 所以未接线的通道恒读 0。

⚠️ **没有 24 V 的时候恰好相反，八路全部恒读 1。** 2026-08-27 实测：只靠 ST-Link 的 3.3 V 供电时 LM339 没有电源，输出管根本导不通，10k 上拉独占这条线。**「恒读 0」和「恒读 1」是两个不同的故障**：恒 0 = 有电但没接线，恒 1 = 整个模拟/24 V 供电没上来。用例 1 现在把两者分开报。

## 模拟量：没有外部基准，必须使能片内 VREFBUF

2026-08-27 实测 + 核实。**这一条决定 ADC 和 DAC 能不能用**。

Bridge 的 BOM 里**没有任何基准电压芯片**，VREF+ 只挂了退耦。不使能片内 VREFBUF，VREF+ 就悬空在 1.2 V 以下 —— 现象是 ADC 读数变成 `0x8000`/`0x4000` 这类精确的 2 的幂（SAR 不收敛，停在中点猜测），DAC 输出接近 0。

**两个必做动作，缺一不可：**

```c
__HAL_RCC_VREF_CLK_ENABLE();        /* VREFBUF 在 APB4 上有独立时钟位 */
HAL_SYSCFG_VREFBUF_VoltageScalingConfig(SYSCFG_VREFBUF_VOLTAGE_SCALE0);
HAL_SYSCFG_VREFBUF_HighImpedanceConfig(SYSCFG_VREFBUF_HIGH_IMPEDANCE_DISABLE);
SET_BIT(VREFBUF->CSR, VREFBUF_CSR_ENVR);
while ((VREFBUF->CSR & VREFBUF_CSR_VRR) == 0U) { }
```

⚠️ **只开 SYSCFG 时钟是不够的。** 漏掉 `__HAL_RCC_VREF_CLK_ENABLE()` 时，对 `VREFBUF->CSR` 的写入会被静默丢弃，寄存器读回来是 `0x00000000`，固件只会报"没 ready"，看不出原因。

**实测 SCALE0 = 2493 mV**（标称 2.5 V，VREFINT 原始值 32235）。选 2.5 V 不是随便挑的 —— 模拟前端两条路径都正好配这个满量程，见下。

⚠️ **VRR 置位时输出还没稳，置位后固定再等 20 ms 才读**（`$BOOT/TestCase/common/port_vref.c:35-38`）：2026-08-28 VRR 一置位就测，一次开机 2493 mV、下一次 2763 mV，这个误差会乘进每个 ADC 读数、温度和 DAC 码值。

⚠️ 使能 VREFBUF 的前提是 VREF+ 没有被外部驱动。本板成立：VREFINT 读到满量程 → VREF+ < 1.216 V → 引脚是悬空的，不是被接到 3V3。2026-10-08 原理图核实（Bridge 原理图第 2 页 `SHEET02-Power`）：VREF+（P1）网络 `STM_VREF+` 只接 C44 1 µF、C45 100 nF、TP3，接 VDDA 的 R28 是 `0 R DNP`（贴片表 `Pick Place for 1436_01_SCHAE-BR-PCB.txt` 同为 DNP）；这条网络经 Bridge J1-27 → UpperDeck J7-17 引到 UpperDeck 的 `/VREF`（JP3-2、JP4-2）。**所以 DAC 满量程 = VREFBUF 输出，不是 3.3 V。**

要换成外部基准，就让 VREFBUF 进高阻、从 `TP3` 接入外部电压：要在 2.0 V 到 VDDA 之间（DS12110 Rev 10 表 87），而且只能在 VREFBUF 进高阻之后接。固件和面板的做法见 [PORTTOOL-FLOW.md](../modules/M4/PORTTOOL-FLOW.md) B.4「外部基准」。

### PC3_C 的 SYSCFG 模拟开关：模拟用途要「开」

`SYSCFG_PMCR.PC3SO` 复位默认是**关**（PC3_C 与数字 PC3 单元相连）。2026-08-27 同一个节点两种状态各读一次：**开路 raw ≈ 10200，闭合 raw ≈ 8600，差约 16%** —— 闭合时数字单元会加载这个节点。**模拟采样一律置 1（开路）。**

## 模拟输出 AOUT1 / AOUT2：XTR111，JP1 / JP2 选电压档，JP3 / JP4 加偏置

2026-10-15 核实：UpperDeck 原理图 `OpenPLC_UpperDeck_R3.pdf` 第 3 页「Analoger Ausgang」+ 网表 `netlist.ipc` + BOM，XTR111 手册（TI SBOS375D）§5.5、§7.1.3、§7.1.4。没上板量过。

| 元件（AO1 / AO2） | 值 | 作用 |
|---|---|---|
| R13 / R16 | 10 kΩ 5% | DAC 脚（PA4 / PA5）→ XTR111 VIN |
| R17 / R18 | 1 kΩ 1% | DAC 脚对地 |
| R9 / R10 | 1024 Ω 1% | R_SET：SET 脚对地 |
| R11 / R14 + JP3 / JP4 | 40.2 kΩ 1% | JP 闭合时把 VREF（2.5 V，见上节）接到 VIN，给 4–20 mA 加偏置（手册 §7.1.4 的两电阻网络） |
| JP1 / JP2 | 焊接跳线 | 闭合时 SET 脚接到输出端子 = 电压输出档；开路 = 电流档（手册 §7.1.3 Figure 7-2「Current (open) or Voltage (closed)」） |

算法（V_DAC = DAC 码 × 2500 / 4095 mV）：

| | JP3 / JP4 开路 | JP3 / JP4 闭合 |
|---|---|---|
| VIN | = V_DAC | = (40.2 × V_DAC + 10 × VREF) / 50.2 ≈ 0.801 V_DAC + 498 mV |
| 电流档（JP1 / JP2 开路）：I = 10 × VIN / 1024 Ω | 0–24.4 mA，20 mA 时 V_DAC = 2048 mV | 约 4.86–24.4 mA：码值 0 时也有 4.86 mA，到不了 4 mA |
| 电压档（JP1 / JP2 闭合）：端子电压 = VIN | 0–2.5 V | 约 0.50–2.5 V |

⚠️ **0 码时到不了 0**（2026-10-16 真板实测，AO1 电流档 470 Ω）：DAC 缓冲开时设 0 端子上约 0.16 mA，缓冲关或通道关时约 1 µA；缓冲关又带不动 R17 / R18 的非 0 输出，所以**软件只在设 0 时关缓冲**（[决策 152](../tables/DECISIONS.md)）。

⚠️ 电压档的满量程只有约 2.5 V（VREF），不是 0–10 V。产品目标是 0–10 V / 0–20 mA，电路会调整去达到（用户 2026-10-15，决策 134「量程目标」）。R17 / R18 的 1 kΩ 是 DAC 输出的负载，对精度的影响没量过，由校准修正。

## 模拟输入前端：九个焊接跳线出厂全开路

2026-08-27 从 `Hardware/Production/UpperDeck/` 的网表 + BOM + 贴片坐标核实。

**JP1–JP9 九个跳线全部是裸铜焊盘，出厂一律开路。** 判据和当初定 JP7（CAN 终端电阻）完全一样：`designators.csv` 里九个都在（PCB 上有焊盘），但 `positions.csv` 和 `bom.csv` **一条都没有**（无贴片坐标、无物料）。对照组：确实贴了的 R69 在三份文件里都有。

**后果：JP5/JP6 开着的时候，MCU 的 PC3_C 和 PA6 两个引脚是彻底悬空的** —— 和端子之间、和地之间都没有通路。此时读到的一切都只是悬空脚，不是端子信号。

⚠️ **「悬空读到多少」这件事两次测不一样，别拿读数反推跳线状态。**

| 什么时候 | 什么固件 | 读到 |
|---|---|---|
| 2026-08-27 | bring-up 固件 | 约 **380 mV**（16 位 raw ≈ 10200），抖动 |
| 2026-09-10 | 工装镜像 `ain` 会话 | **AIN1 raw=12、AIN2 raw=0**，即 ≈ 0 mV |

同一天的对照组：`temp` 会话走**同一个 hadc1** 读 PA0/PA3，得到 813/823 mV（31/32 °C，合理），VREFINT 也正常（`vdda=2503`）—— **所以 ADC 本身没问题，是这两个引脚上确实什么都没有。**

两次都符合「引脚没接东西」，只是悬空脚停在哪个电位不确定。**判断跳线焊没焊，以网表 + BOM 为准**（就是上面那张表），不要用读数。

### 每个通道两条路，结构相同

```
端子 ──┬─ JPx 脚2-3 ── 68k ──┬── 22k6 ── GND          电压档
       │                     └── JPy 脚1-2 ── MCU
       └─ JPx 脚1-2 ── 374R ─┬── 124R ── GND          电流档
                             └── JPy 脚2-3 ── MCU
```

| 通道 | 端子 | 端子侧跳线 | MCU 侧跳线 | 68k / 22k6 | 374R / 124R | MCU 引脚 |
|---|---|---|---|---|---|---|
| AIN1 | UpperDeck J3-4 | **JP9** | **JP5** | R19 / R20 | R23 / R24 | PC3_C |
| AIN2 | UpperDeck J4-1 | **JP8** | **JP6** | R21 / R22 | R25 / R26 | PA6 |

电阻都是 0.1%，ESD 保护是 `PESD5Z2.5`（D5/D7/D9/D11）。

**换算（两档都正好配 2.5 V 满量程，这就是选 VREFBUF SCALE0 的理由）：**

| 档 | 换算 | 满量程对应 |
|---|---|---|
| 电压 | 端子 mV = 引脚 mV × **4.0089**（比例 22.6/90.6 = 0.2494） | 10.0 V ↔ 引脚 2.494 V |
| 电流 | 端子 µA = 引脚 mV × 1000 / **124** | 20 mA ↔ 引脚 2.48 V；4 mA ↔ 0.496 V |

⚠️ 电流档那个 **374R 是保护电阻**：总阻 498 Ω，误把 10 V 电压源接到电流档时限流到 20 mA，引脚只到 2.48 V，烧不掉。它不参与换算 —— MCU 只跨在 124R 两端。

### 档位决定（用户 2026-08-27 定）

**AIN1 = 电压档，AIN2 = 电流档。** 要让它们通，得用锡桥这四处：

| 通道 | 档 | 桥哪里 |
|---|---|---|
| AIN1 | 电压 | **JP9 脚 2–3** + **JP5 脚 1–2** |
| AIN2 | 电流 | **JP8 脚 1–2** + **JP6 脚 2–3** |

⚠️ **焊上去不可逆。桥之前先对着上面那张网表图确认焊盘编号。**

## CAN 接口（PB9 / PI9，Upper Deck）

2026-08-26 从原理图 / 网表 / BOM 核实，为写 CAN 端口测试而查。**bootloader 不用 CAN**，这一节纯粹是硬件事实登记。

| 项 | 事实 | 出处 |
|---|---|---|
| MCU 引脚 | **PB9 = FDCAN1_TX**（ball B4）、**PI9 = FDCAN1_RX**（ball D3），**AF9** | `Hardware/STM32H743IIK6_GPIO_ASSIGNMENT_Schaeffer_Bridge_20260822.xlsx` sheet GPIO_ASSIGNMENT 行 95-97；`Hardware/Production/UpperDeck/netlist.ipc:260-261` |
| 为什么只能是这一对 | FDCAN2 全部引脚被占（PB12=RMII_TXD0、PB5/PB6=DIN2/DIN3、PB13=HSFET_1）；FDCAN1 其余复用脚也被占（PD0/PD1=FMC、PA11/PA12=USB FS、PH13/PH14=UART4） | 同 xlsx 行 8/27/28/53/54/65/68/69/83/84/99 |
| 收发器 | **U8 = TI ISO1044BDR**，SOIC-8，**隔离**型 CAN FD 收发器。**没有 STB/EN/silent 脚** —— 8 个脚全占满，listen-only 只能靠外设的 `FDCAN_MODE_BUS_MONITORING` | `Production/UpperDeck/BOM/1435_00_SCHAE_UD_PCB_Project.csv:51`；`netlist.ipc:259-266` |
| 隔离侧电源 | **U7 = PDS1-S5-S5-M / MPB1205**，5V→5V 隔离 DC/DC 1 W，**装在板子底面**，输入经 L1（6.8 µH）从 +5V 来。⚠️ U7 不出电 = 收发器驱动不了总线 | 同 BOM `:50`；`positions.csv:192` |
| 隔离侧地 | `CAN_GND`，与数字地 `GNDD` 分开。`R83`/`R84` 是 **0R DNP**，贴上就破坏隔离 —— **不要贴** | `netlist.ipc:426-427, 445-446`；BOM `:42` |
| 测试点 | `TP_CAN_VDD1`（隔离 5V）、`TP_CAN_GND1`。⚠️ **CAN_H / CAN_L 上没有测试点**，示波器只能夹 J10 螺丝端子 | `netlist.ipc:599, 593` |
| LED | **没有。** 网表里 CAN 相关网络上没有任何 D 器件 | 网表全扫 |
| 内核时钟 | 本工程从未配过 `FDCANSEL`。**复位默认是 `FDCANSEL=00` = HSE。** 在目标上核实过：`D2CCIP1R` 读 `0x00000000`，而 `RCC_FDCANCLKSOURCE_HSE` 就是 0（`Drivers/STM32H7xx_HAL_Driver/Inc/stm32h7xx_hal_rcc_ex.h:1442`）。`TestCase/common/port_can.c` 仍显式选 HSE = 25 MHz（125k/250k/500k/1M 四档 prescaler=1 整除） | 在线读寄存器；HAL 头文件 |

### 端子号

|  | 功能 | 连接器 | 网络 |
|---|---|---|---|
| **C08 / A08** | **CAN H** | J10 pin 1 | `CAN_H` |
| **C07 / A07** | **CAN L** | J10 pin 2 | `CAN_L` |
| **A09** | **CAN_GND** | J11 pin 4 | `CAN_GND` |

端子字母 **C / A 两套并存**，指同一批端子：`Klemmblockzuordnung.pdf` 叫 C01–C12，KiCad 原理图 p1 叫 A01–A12。

⚠️ **端子编号以网表 `netlist.ipc:245-256` 和原理图 `OpenPLC_UpperDeck_R3.pdf` p1 为准**（两者一致）。A09=CAN_GND、A10=RS485 A、A11=RS485 B。

⚠️ **这里的 A01–A12 是 Upper Deck 的板内局部编号，等于产品级的 C01–C12。`A` 这个字母不全局唯一** —— Lower Deck 另有一排 Klemmblock A（A01–A16，装 DO1–DO8 和电源）。**单写 `A08` 有歧义**：产品级是 Digital Out 6，Upper Deck 原理图是 CAN H。跨仓引用一律写产品级字母（C 排）。

⚠️ **`Klemmenbezeichnungen-R.pdf` 和 `Klemmblockzuordnung.pdf` 这两张图在这里是错的**（用户 2026-09-11 确认）：它们**漏标了 `CAN_GND`**，于是 09 号往后整体错开一位，把 RS485 A/B 标成了 C09/C10。正确的是 **C09=CAN_GND、C10=RS485 A、C11=RS485 B**。同一份图还把 **A08 的 "Digital Out 6" 印成 "Digital Out 3"**。图纸不改（要和生产方对得上），以这里为准。

> 这处陷阱最早只写在 CAN 旧端口测试的头注释里（该测试已按决策 87 删除），一直没传出来 —— 2026-09-11 发现时，错的 C09/C10 还住在给工装方的接口文档、`PORTTOOL-FLOW.md`（两处）、PORT-BRINGUP-PLAN.md（四处，含一条让人接线的指令；该文件已删）、固件两处 `term=`、面板的接线提示、以及两份假板子测试夹具里。

CAN 两根信号跨板走 Upper Deck **J8 pin2（CAN_TXD_PB9）/ pin3（CAN_RXD_PI9）**（`netlist.ipc:391-392`）。

### 终端电阻出厂是断开的

**R69 = 120R 1% 已贴**，但串在 **JP7** 上 —— 一个 `SolderJumper_2_Open`，出厂**开路**（`designators.csv:86` 有它，但 BOM 和 `positions.csv` 都没有条目，就是一块裸铜）。所以**整板未端接**。要端接只能用锡把 JP7 桥上，不可逆。短线（<1 m）500 kbit/s 用不着；需要的时候优先打开对端设备自带的终端电阻。

出处：BOM `:40`；`Schematics/OpenPLC_UpperDeck_R3.pdf` p5；`netlist.ipc:420-421`。

## KNX 接口（STKNX U9，Upper Deck）

出处：`Production/Bridge/1436_01_SCHAE-BR.pdf` p5、`Production/UpperDeck/netlist.ipc`、`Schematics/OpenPLC_UpperDeck_R3.pdf` p4。实现：工装 `$BOOT/TestCase/KNX/`，app 侧 `$CORE_REPO/libraries/OpenPLC_KNX/`（[KNX-TP-DATA-LINK.md](../modules/M3/KNX-TP-DATA-LINK.md)）。

**U9 = STKNX，是裸模拟 TP1 收发器，不是 TP-UART** —— 没有字节级主机协议，**TP1 的位时序要 MCU 自己产生**。STKNX 全部工作电源取自 KNX 总线（pin 11 `KNX_A`），总线不供电时整个隔离侧是死的。

| 信号 | MCU 引脚 | 复用 | 说明 |
|---|---|---|---|
| `KNX_TX` | **PB14** | TIM12_CH1 / AF2 | 高 = 有源脉冲，低 = 空闲 |
| `KNX_RX` | **PA10** | TIM1_CH3 / AF1 | ⚠️ **低 = 有源脉冲，高 = 空闲**（低有效，2026-09-09 实测，见下） |
| `KNX_OK` | **PD7** | GPIO | STKNX pin 21，总线电源正常。⚠️ **这块板子上恒为 LOW，不跟总线走**，见下 |
| `KNX_VCC_OK` | **PH12** | GPIO | STKNX pin 19，VCCCORE 正常 |
| `KNX_Prog_LED` | **PG11** | GPIO | ⚠️ **这根线上没有 LED**：只经板间连接器到 Upper Deck J8-10，不接任何器件（Bridge 原理图 p5；`Production/UpperDeck/netlist.ipc` 的 `/KNX_PROG_LED`）。板上心跳灯是 LED3 `HBEAT`，经 R63 330R 接 **PE2** |
| `KNX_Prog_KEY` | **PG9** | — | ⚠️ **和 BOOT0 同一条网**，KNX 代码从不驱动它 |

**TP1 位时序**（STKNX datasheet DocID031327 Rev 1 §5.1 p17）：位周期 **104 µs**（9600 bit/s）；逻辑 1 / 空闲 = `KNX_TX` 全程低；逻辑 0 = `KNX_TX` 高 35 µs 再低 69 µs。

**收发链极性：TX 不反相，RX 反相。**

- **TX**：`+3V3 → U12 LED 阳极；阴极 → R88 332R → PB14`。PB14 低点亮 LED；U12（TLP2362）反相开集，LED 亮则输出低；R94 10k 上拉到 VCCCORE。**净结果 PB14 高 → STKNX pin 24 高 → 有源脉冲。**
- **RX**：`VCCCORE → R89 332R → U13 LED 阳极；阴极 → STKNX pin 23`。pin 23 低点亮 LED，U13 开集输出把 PA10 拉低。`/KNX_RX` 是**低有效**：pin 23 空闲为高 → LED 灭 → PA10 被 MCU 内部上拉拉高；有源脉冲时 pin 23 低 → LED 亮 → PA10 低。**所以 PA10 空闲为高、有脉冲为低。**

⚠️ **收进来的位要取反，发出去的不用**（用户 2026-09-09 确认，代码里就是这样）。取反在 `knx_slot_level()`（`TestCase/KNX/knx_test.c:618`）：`slots` 位为 1 返回 0。加上上面 RX 那一路的反相，一共反了两次，所以字符解码是对的、环回能通 —— 但**引脚层的极性理解一直是反的**，两处后果：

1. `TIM1_CC_IRQHandler`（`TestCase/KNX/knx_test.c:295`）把上升沿当脉冲起点，按实际极性那是脉冲**终点**，于是 `w_avg` / `d_avg` 的角色整个互换。实测 `w_avg=152 d_avg=37`：`porttool_knx.c:27` 说 `w_avg` 应接近 35 µs，实际是 **`d_avg=37` 才是那个 35 µs**
2. `knx_bus_state()` 原来判「总线供电、空闲」要求 PA10 为低，于是这块板子恒判 `bus=odd`。**2026-09-09 已改成只看 PH12**，`ok=`/`idle=` 照旧报出来但不参与判定

**报文级已经端到端验证过了（2026-09-09），所以极性这件事不影响 KNX 可用性：**

`pt.start knx mode=frames` 90 秒，47 条 GroupValueWrite 发出、47 条原样收回且**校验字节通过**（`crc_raw=47 crc_inv=0 crc_bad=0`）、收到 47 个 `L_Ack ACK`。ACK 只可能来自装置里的真实 KNX 设备（固件没有自动应答逻辑），**用户在 ETS5 总线监视器里看到了这 47 条**。

结论：位/字符层的极性理解是反的，但 `knx_slot_level()` 又取反一次，两次抵消，**字节层和报文层都是正的**。`crc_raw` 对 `crc_inv` 就是这件事的运行时判据 —— 哪天硬件改了，数字自己会换边，不用改代码。

⚠️ **PB14 绝不能悬空。** 没有 LED 电流时 U12 输出释放，R94 把 STKNX pin 24 拉高，收发器会持续从总线抽流。STKNX 自己在 pin 24 上只有 6 µA 下拉，拉不过 10k。**空闲时 PB14 必须驱动为低。**

⚠️ **`/KNX_RX` 板上没有上拉**，不同于另外三个光耦（R92/R93/R94）。高电平只能来自 **MCU 内部上拉**，所以 PA10 一律配 `GPIO_PULLUP`。

**总线供电特征**（用来一眼分辨总线有没有电）：

| 状态 | PH12 | PD7 | PA10 |
|---|---|---|---|
| 总线供电、空闲 | HIGH | ❓ | **HIGH** |
| 总线无电 | LOW | ❓ | HIGH |

⚠️ **2026-09-09 拔线实测的结果**（`pt.start knx mode=listen`，拔掉 C03/C04 再插回，两轮）：

| | PH12 `vcc` | PD7 `ok` | PA10 `idle` |
|---|---|---|---|
| 总线接着 | 1 | **0** | 1 |
| 总线拔掉 | **0** | **0** | 1 |

- **PH12 是唯一跟着总线走的一项** —— 拔掉变 0、插回变 1，两轮都复现。**它单独就够判「总线有没有电」**
- **PA10 恒为高**，符合上面「空闲为高」的推导。总线拔掉后仍然是空闲，所以还是高，一致
- **PD7 恒为 0，拔插都不动。** 隔离侧掉电时 pin 21 输出应释放、板上上拉应把 PD7 拉高，实测没有 —— **这一项没查清**。可能是那一路光耦输出常通、上拉没生效、或 STKNX 在这个外部网络下不驱动 pin 21。要定论得量 PD7 电压或查那一路网表。⚠️ **在查清之前，不要把 PD7 当成总线电源的判据**

**与 datasheet 的四处偏差**（外部网络其余部分逐点符合 Figure 3 buck-disabled，CGATE 10 µF + CVDDHV 220 µF 正好是 Table 8 的 30 mA fan-in 那一行）：

| # | 偏差 | 软件能不能看见 |
|---|---|---|
| a | R88/R89/R90/R91 = 332 R，TLP2362 的 LED 电流典型 5.4 mA、最坏 4.3 mA；TLP2362 建议 IF(ON) ≥ 7.5 mA，只保证 IFHL ≤ 5.0 mA 时开关。⚠️ R89/R90/R91 由 VCCCORE 供电，其 IREG 上限 20 mA，空闲时三个 LED 同时亮 —— **不能简单靠减小电阻解决** | 能，表现为丢脉冲计数 |
| b | `/KNX_RX` 没有板上上拉 | 能 |
| c | C27（CVDDHV）是 220 µF / **10 V**，Table 2 要求 ≥ 35 V | ❌ 只能手工量 |
| d | C20（CREF）是 470 nF / **10 V**，同样要求 ≥ 35 V。VREF 自己的 KNX_OK 门限在 9.7 V…13.5 V | ❌ 只能手工量 |

## microSD 卡座（SDMMC1，1 位，Bridge J6）

2026-09-25 核实：Bridge 原理图 `Hardware/Production/Bridge/1436_01_SCHAE-BR/1436_01_SCHAE-BR_页面_4.png`（Sheet 4 "Bridge I/O"，D1–D5 区）看网络 + xlsx `GPIO_ASSIGNMENT` 行 49–52 看 MCU 引脚。Bridge 没有网表，没做逐脚网表核对。

| 信号 | MCU 引脚 | 说明 |
|---|---|---|
| `SDIO1_CLK` | **PC12**（A12） | 经 EMI 滤波 U5（VEMI65AC-HCI-GS08）到 J6 CLK |
| `SDIO1_CMD` | **PD2**（D12） | 同上，10k 上拉 |
| `SDIO1_D0` | **PC8**（G14） | 同上，10k 上拉 |
| `SDIO1_CD` | **PE6**（B3） | 10k 上拉 + 100R 到 J6 CD1，CD2 接地：**低 = 已插入** |
| `SDIO1_D1/D2/D3` | — | 原理图标「not used」，只在 J6 侧上拉，**不接 MCU** → 只能跑 1 位总线 |

**软件含义**：板卡包的 `PinMap_SD[]` 只该有 PC8 / PC12 / PD2 三条，SD 库必须设 1 位总线。

## 引脚分配表：硬件工程师的 xlsx

`Hardware/STM32H743IIK6_GPIO_ASSIGNMENT_Schaeffer_Bridge_20260822.xlsx`，单张 sheet `GPIO_ASSIGNMENT`，138 行覆盖 UFBGA176 上用到的每一个脚。列是：序号、引脚名、**BGA 球号**、备用功能全表、附加功能（ADC/DAC/WKUP）、**信号名**、电源域、中英文说明。取自原理图 Sheet05-MPU。

**这份表管什么、不管什么**（2026-09-01 逐条核对过）：

| 事实 | 谁说了算 | 为什么 |
|---|---|---|
| **信号名、BGA 球号、备用功能** | **这份 xlsx** | 全仓库文档里的球号已和它逐条比对，**没有一处不一致** |
| 外设怎么配（时钟、AF、模式） | `OpenPLC_BootLoader.ioc` | CubeMX 工程定义，见 [CUBEMX-RULES.md](../build/CUBEMX-RULES.md) |
| 端子号、跨板连接器、板上是否真的布了线 | `Hardware/Production/*/netlist.ipc` + 原理图 | **xlsx 只说 MCU 这一侧**，它列出一个信号不等于板子上接了 |

### 已知的三处出入

1. **xlsx 漏了 `PE15 = FMC_D12`。** 第 42 行是空的，`FMC_D12` 整条不在表里。`.ioc` 有（`PE15.Signal=FMC_D12_DA12`），本文件上面那张 FMC 表也有。**是表缺行，不是工程错** —— 该反馈给硬件。
2. **`PI2 = RS485_EN` 在这块板上不存在。** 表里有，Bridge 板布到了 J2，但 UpperDeck 一根没接。**这是「xlsx 只说 MCU 侧」的典型例子。**
3. **RS485 两根信号有两套标签。** xlsx 叫 `RS485_TX`（PD5）/ `RS485_RX`（PD6）；网表叫 `RS485_DI_PD5` / `RS485_RO_PD6`。同一条网，看哪份文件用哪个名。

### xlsx 有、这份文档以前没记过的脚

多数是以太网 / FMC / 晶体 / NC，不必单独记。有实际功能的这几个记一下：

| 引脚 | 球 | 信号名 | 说明 |
|---|---|---|---|
| **PE2** | A2 | `LED_DRIVER` | 系统指示灯驱动，**高亮低灭**。xlsx 把它归在「未使用引脚」一节下，但它有功能 |
| **PE6** | B3 | `SDIO1_CD` | SD 卡检测，**低 = 已插入** |
| PC9 | F14 | `DAC1_EXTI9` | 预留 |
| PB1 / PF9 | R4 / L2 | `C-ADC2_HSPEED` / `C-ADC4_HSPEED` | 预留，ADC 高速通道 |
| PG10 / PB2 | B10 / M6 | `SPI1_NSS` / `SPI3_MOSI` | 预留 |

`DIN1`–`DIN8` 在表里的信号名带编码器后缀（`DIN1_PC6-Enc1a` … `DIN8_PI6-Enc4b`），八路兼作四组编码器 A/B 相。

## 主控板（Bridge）上的三个 LED

2026-10-13 按 Bridge 原理图 `$HW/Production/Bridge/1436_01_SCHAE-BR.pdf` 第 5 页、BOM `1436_01_SCHAE-BR.xlsx`、贴片坐标 `Pick Place for 1436_01_SCHAE-BR-PCB.txt` 核实；三个都在 BOM 里、都贴（顶层）。

| 位号 | 颜色 | 丝印旁的名字 | 接在哪 | 什么时候亮 | 位置（贴片坐标 mm） |
|---|---|---|---|---|---|
| LED1 | 绿 | 3V3 OK | 3V3 → R61 330R → LED1 → GND | 上电就常亮 | (32.1, 16.3)，和 LED2 挨着，在 BOOT0 键 SW2 (28.0, 25.7) 旁边 |
| LED2 | 黄 | 5V0 OK | 5V0 → R62 750R → LED2 → GND | 上电就常亮 | (33.2, 16.3) |
| LED3 | 绿 | HBEAT | **PE2** → R63 330R → LED3 → GND，**高亮低灭** | 只有固件把 PE2 拉高时 | (64.7, 39.1)，离另两个远，R63 在它旁边 (64.8, 36.4) |

⚠️ **`$HW/Bridge_overview.txt` 写的是「5V0 OK(绿)、3V3 OK(黄)」，颜色和原理图 / BOM 相反**：BOM 里 LED2（5V0 OK）是黄（150040YS73220），LED1（3V3 OK）是绿。以原理图和 BOM 为准；那份概览的错报给用户，不在 `$HW` 里改。

## 两路板载温度是 LM50 线性传感器

2026-09-28 按下层板网表 `$HW/Production/LowerDeck/netlist.ipc` 核实。

| 位号 | 器件 | 脚 1 | 脚 2（输出） | 脚 3 |
|---|---|---|---|---|
| U1 | LM50BIM3/NOPB | `5V0` | `TEMP_SCPROT` → PA0 | `GNDD` |
| U2 | LM50BIM3/NOPB | `5V0` | `TEMP_HSSW` → PA3 | `GNDD` |

输出 500 mV + 10 mV/°C（LM50 数据手册），`BoardTemperature` 例程按此换算，是对的。⚠️ 与两处抄件不符，以网表为准：`$CORE_REPO/variants/STM32H7xx/H743/variant_PLC_H743.h:228-229` 写作 NTC；`$HW/LowerDeck_overview.txt:32,85` 写作 5V 线性稳压器。

## 3.3 V 从哪来、24 V 掉到多少时它才跟着掉

2026-10-03 读 `$HW/Production/JunctionLink/netlist.ipc` 和 `bom.csv` 核实：

| 事 | 结论 | 怎么核实的 |
|---|---|---|
| 3.3 V 由谁产生 | Junction Link 上的 IC1，LMR50410 降压（`bom.csv`：IC1/IC2/IC3 都是 LMR50410XDBVR，三路分别出 3.3 V、5 V、5 V_EXT） | BOM + 网表 |
| 它的输入 | 直接接 `24V0`（netlist 第 202–203 行：IC1 的第 4、5 脚都在 `24V0` 上）；第 3 脚 `/3V3FB`、第 6 脚 `/3V3SW` | 网表 |
| 有没有外部欠压门限 | **没有**：第 4、5 脚同接 `24V0`，也就是使能脚直接接输入，没有分压电阻设门限 | 网表（第 4、5 脚谁是 EN 不影响这个结论，两脚同网） |
| 24 V 掉到多少 3.3 V 才开始掉 | 输入约 10 V 时 3.3 V 仍为 3.27 V、正常启动；再往下（约 9 V 起）**开机时每秒约 16 次反复复位**，每次只到开机窗口（疑为开机负载把 3.3 V 拉过 BOR，未核实）；约 3 V 时 3.3 V 跌到 1.1 V 后关断。均在额定输入范围之外 | 2026-10-08 上板：手调电源（电压为用户读数，约值）+ ST-Link 每 0.7 s 量 3.3 V + 串口日志 |

含义：24 V 从额定值往下掉的大部分区间里 3.3 V 还在，MCU 照常跑；3.3 V 真正掉到芯片的欠压复位（BOR，定在 2.7 V）时，24 V 已经接近没电。

## 继电器 RY1–RY6 是 HF41F/005-HST：一组常开，AgSnO2 触点

2026-10-12 按 `$HW/Production/LowerDeck/bom.csv:17`（RY1–RY6 = `HF41F/005-HST`）和宏发 HF41F 手册（2025 Rev. 2.00，[宏发官网英文版](https://source.hongfa.com/Uploads/Product/PDF/HF41F_en.pdf)，2026-10-14 和中文版核对一致；`$HW` 里没有这份手册）核实；原理图 `OpenPLC_LowerDeck_R3.pdf` 同型号，2026-10-14 用户看过实物也是这个件。

| 事 | 手册原值 |
|---|---|
| 型号拆解 | `005` 线圈 5 VDC；`H` 一组常开；无 `8` 垂直安装；`S` 塑封型；`T` AgSnO2 触点 |
| 机械耐久性 | 1 x 10^7 次（不加载） |
| 电耐久性 | H 型 6 x 10^4 次，**只给了 AgNi 触点**（6 A 250 VAC / 30 VDC 阻性、85 °C、1 s 通 9 s 断）；**AgSnO2 的电寿命手册没给**（特性曲线也全是 AgNi 测的；手册注明其他负载可向宏发索取） |
| 最高动作频率 | **手册没给**；电寿命按 1 s 通 9 s 断标定 |
| 动作 / 释放时间 | ≤ 8 ms / ≤ 4 ms（额定电压下） |

代码、面板、文档里用到继电器寿命的，只引用这一节、只用手册给了的数，没给的就写没给（用户 2026-10-12：「不要猜，用器件信息来同步」）。

⚠️ 文档里原来写的「机械寿命 3 万次」不对：3 x 10^4 是 Z 型（一组转换）常开触点的 AgNi 电寿命，本板是 H 型。
