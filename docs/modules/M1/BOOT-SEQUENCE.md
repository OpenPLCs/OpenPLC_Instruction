# 启动流程：决定跑谁，然后交出去

**这份回答一件事：一次复位之后，板子怎么决定跑 app 还是留在 bootloader，以及怎么把硬件交出去。**

判据和用例在 `$PROD/docs/engineering/HOW-TO-RUN-TESTS.md`，
已拍板的取舍在 `$PROD/docs/tables/DECISIONS.md`，flash 上那本账在 [SECTOR-15.md](SECTOR-15.md)。

## 两个阶段，分开的理由

| 阶段 | 做什么 | 在哪 |
|---|---|---|
| **Phase 1** | **只决定，不动手**：跑 app 还是留下，返回答案 | `$BOOT/IAPServer/IAP_server.c` 的 `server_decide()` |
| **Phase 2** | 按上一阶段的结论**打开对应的命令通道** | 同文件 `IAP_servers_start()` |

**Phase 1 刻意不跳转**，跳转由调用方自己做（`server_jump_to_app()`）。

### Phase 1 为什么能在任何外设初始化之前跑完

它只需要四样东西：**读 flash、软件 SHA-256/ECDSA、一个 BOOT0 引脚、SRAM4 里的交接记录**。
USB、以太网、FMC 一个都不用碰。

**这正是它存在的形态**：走 app 那条路时，那些外设从头到尾没被初始化过，
所以 app 几乎不继承我们的任何状态。

> **「从没初始化过」不可能弄错；而一张反初始化清单要靠人维护，会悄悄烂掉。**

### 接在 CubeMX 生成代码的哪两个点上

| 阶段 | 接入点 | 那时已经起来的东西 |
|---|---|---|
| Phase 1 | `USER CODE BEGIN SysInit` | 只有最小 GPIO；`RS232_Enable`（PB10）留在低，收发器从不打开，UART4 不初始化（`R1-43`）。`printf` 只进 SWO（ITM）和 SRAM4 开机缓存（[BOOT-LOG.md](BOOT-LOG.md)）。工装镜像（`PORTTOOL_ENABLE=1`）例外：它另开收发器和 UART4 当命令口 |
| Phase 2 | `USER CODE BEGIN 2` | 这个模式需要的外设都起来之后 |

Phase 1 里先过开机窗口（系统指示灯快闪那 2 秒，`main.c` 的 `boot_window()`），窗口结束那一刻读一次 BOOT0：没按就是不按；按着就留在 bootloader，之后只继续看是否长按到 10 秒武装恢复出厂。结果交给 `server_decide()`；
返回 `IAP_NONE` 就直接 `server_jump_to_app()`。

## BOOT0 按住的话，别的都不算

物理逃生舱**一票否决**：谁在复位窗口里按住了按钮，就是要 bootloader，
交接请求和签名结果都没有投票权。**我们无法知道他会用哪个通道，所以全部打开。**

⚠️ **即便如此，那两次读取仍然必须发生**：
- `boot_handoff_take()` 是消费请求记录的唯一动作 —— 不读，那条请求会把**下一次**启动也钉在这里
- 签名结果要喂给 UDP 发现的角色名和 `getapprevoked`，这两件事都不参与这次决定

## 输出一开机就置 0，一直保持到 sketch 接管（决策 81）

`main()` 的第一批语句：先锁存复位原因，紧接着 `safe_outputs_init()`（`$BOOT/IAPServer/safe_outputs.c`）把
DO1–DO8 置 0、AO 的 PA4 / PA5 拉低（AO 0 mA）、KNX 发送脚 PB14 拉低（悬空时 STKNX 一直从总线抽流，见 [HARDWARE-FACTS.md](../../hardware/HARDWARE-FACTS.md)「KNX 接口」）。继电器 RY1–RY6 由 `MX_GPIO_Init()` 置 0，开机不再动（决策 71）。

| 选这个位置的理由 | |
|---|---|
| 越早越好 | 它前面只有锁存 `RCC->RSR`（必须第一个读）；MPU、cache、`HAL_Init()`、`SystemClock_Config()`（等 PLL 锁定）都在它后面，省下的是这些步骤的时间 |
| 不依赖任何初始化 | 只写 RCC 的 GPIO 时钟使能位和 GPIO 寄存器，不用 HAL、不用时钟树 |

**交权时再做一遍**：`server_jump_to_app()` 里的 `HAL_DeInit()` 会复位全部 GPIO 端口，引脚回到高阻；
所以它之后、跳转之前再调一次 `safe_outputs_init()`。这是决策 4「冷板子」的一个例外，范围只到这 11 个脚。
板卡包从启动到 sketch 第一次写之前不碰这些脚（`initVariant()` 是空的弱函数，`analogWrite` / `pinMode` 都是第一次调用时才配置）。

引脚出处：`$HW/STM32H743IIK6_GPIO_ASSIGNMENT_Schaeffer_Bridge_20260822.xlsx` 第 92–93 行（AOUT1 / AOUT2）、
第 99–106 行（HSFET_1–8）。复位到这一行之前的几毫秒、以及掉电时，AO 仍不确定（等示波器实测）。

## 开机检查欠压复位（BOR）档位

3.3 V 掉到 BOR 门限以下时芯片由硬件直接复位，复位后输出全为 0。
门限存在选项字节里，**bootloader 只读不写**：`MX_GPIO_Init()` 之后 `bor_level_report()`（`$BOOT/IAPServer/bor_check.c`）读
`FLASH->OPTSR_CUR` 的 `BOR_LEV`（第 3:2 位），不是 3 档（2.7 V）就在开机日志里打一行警告。

| `BOR_LEV` | 门限（`stm32h7xx_hal_flash_ex.h` 里 `OB_BOR_LEVELx` 的注释） |
|---|---|
| 0 | 1.6 V（相当于关掉） |
| 1 | 2.1 V |
| 2 | 2.4 V |
| 3 | **2.7 V，本板要的** |

产线工站（以及实验室已有的板子）用 ST-Link 写一次：

```
STM32_Programmer_CLI -c port=SWD -ob BOR_LEV=3
```

⚠️ 这条命令的写法照 STM32CubeProgrammer 的选项字节语法，**还没在本板上跑过**；写完后板子上电，开机日志里不再有那行警告就算写对了。

## 复位原因交给 app（决策 80）

bootloader 开机先读走并清掉 `RCC->RSR`，app 再读它就是空的。所以 `boot_handoff_take()` 把这次锁存的原值
写进 SRAM4 交接区第 16–23 字节（原值 + 校验），app 用 `boot_handoff_published_reset_rsr()` 读，
板卡包 `OpenPLC_Ports` 的 `openplcResetCause()` 把它译成「看门狗 / 上电 / 复位键 / 软件复位……」。
上游 `IWatchdog::isReset()` 读的是 `RCC->RSR`，在本板上永远是 false，不要用它。

## 交接记录为什么放 SRAM4，不放 RTC 备份寄存器

**一个正在跑的镜像要求「下次复位后留在上传模式」，只有这一条通道** ——
`$BOOT/IAPServer/IAP_boot_handoff.h` 的 `boot_handoff_request()`，bootloader 只读 `boot_handoff_take()`。

| | 为什么不是 RTC 备份寄存器 |
|---|---|
| **没有前置条件** | 写 RTC 备份寄存器时，只要 `PWR_CR1.DBP` 恰好没置位就**静默失效**，编译器和 HAL 返回值都不会告诉你。以太网升级路径曾因此静默坏过一次 |
| **不需要初始化** | SRAM4 不用开时钟、不用 MPU 区、不用外设配置，所以启动决策能在**任何东西初始化之前**做完 |
| **生命期正好** | RAM 挺得过热复位、挺不过掉电，而「进一次上传模式」正好是热复位范围的请求。带电池的寄存器会把过期请求留到下一次上电 |
| **不依赖 VBAT 和 RTC 配置** | — |

**地址是保证，不是约定**：两份链接脚本都把 `RAM_D3` 起点设在 `0x38000020`，
所以链接器不可能往前面那 32 字节放东西。那 32 字节在 32 字节对齐处，正好是一条 Cortex-M7 cache line。

⚠️ **记录里的枚举值是格式的一部分**：只许追加，**永远不要给已有的值重新编号**。

### 冷启动第一次碰这块内存，必须是写

**上电复位之后，SRAM4 的内容和它的 ECC 校验位都是随机的，两者对不上。**
所以这块区域里任何一个字的**第一次访问必须是写** —— 先读会引发不可纠正的 ECC 错误，直接 BusFault。

初始化覆盖**整个保留区**，不只是当前版本用到的字段。只有冷启动路径会调它，
调完之后这一整个上电周期内每个字都可以安全读。

### cache 维护是无条件正确的，这是刻意的

写完之后把存储推到物理内存、并丢掉缓存里的副本，**这样紧接着的读回校验读到的是内存，不是刚写的那条 cache line**。

两个维护调用在数据 cache 关闭时都是无害的空操作 —— **这正是重点**：
**不管正在跑的镜像怎么配置了它的 cache，这个文件都是对的，而且不需要任何 MPU 区。**
（这条正是 `$PROD/docs/modules/M3/CONSTRAINTS.md` 那条约束的落地：不能依赖 app 恰好关掉了什么。）

### 读回校验

写完再读回来确认 —— 一次被硬件丢弃的写和一次成功的写**长得一模一样**，不读回就会带着旧标志复位、启动进错误的模式。

### 认不出来的时候怎么办

| 看到什么 | 怎么处理 |
|---|---|
| 魔数位置是第三种值 | 只有这个文件会写这里，而且只写 0 或魔数。**第三种值意味着有东西写了不该写的地方**（野指针、DMA、链接脚本把这块让出去了）或者翻位了。**报告，但仍然启动 app** —— 签名校验才是真正的关卡，为一个坏掉的字把板子钉在 bootloader 里，等于把一次毛刺变成一次停机 |
| 版本比本 bootloader 新 | 头部是冻结的，所以 `mode` 仍然可读；只是看不见 `check` 之后追加的东西 |
| 有请求，但认不出是哪个通道 | **留下来，全部通道都服务。** 这是可恢复的；跳进 app 会丢掉一条明确说了「别走」的请求。**不要猜单个通道** |
| 什么都没有 | **刻意沉默。** 复位按钮、看门狗、app 自己复位 —— 每次启动都落在这里，报告它会把日志淹掉 |

⚠️ **无论哪条分支都要消费掉这条记录**：读一次就没了，所以**不可能有一条过期记录把板子跨重启地钉在 bootloader 里**。

## 跳转：交还硬件的顺序是有讲究的

只有 `server_decide()` 返回 `IAP_NONE` 时才走这条路，而且**只在启动路径上**——
上传完成走的是复位，不是跳转，这也是 I-cache 不掺和进来的原因。

交还硬件的步骤、顺序和每步的理由在 [M3 应用运行环境](../M3-app-runtime.md) 第 1 节，这里不抄。

⚠️ **交接那一瞬间串口上多两个坏字节**（偏移 502，`[` `0xC2`，bootloader 自己的输出里没有），原因未知，功能无影响；取舍见 `$PROD/docs/tables/DECISIONS.md` 第 49 条。

### 跳转函数必须是 `naked`

普通 C 函数里改了 MSP 之后，编译器仍按**旧栈**生成收尾代码（恢复寄存器、释放局部变量），SP 被弄乱后总线错误 —— 在 `server_jump_to_app()` 上真发生过。`naked` 的 `jump_to_app()` 没有编译器生成的开头和收尾，**设置 MSP 和跳转之间插不进任何东西**。

## 命令分帧：必须等到结束符

一条文本命令由结尾的 `'\n'` 或 `'\r'` 分帧，两种都收（只发 `'\r'` 的裸终端也要能用）。

**不等结束符会怎样**：一条比一个 USB CDC 包或一个 TCP 段更长的命令 ——
例如 `flash <size> <crc32> <128-hex-sig> <cert_hex> <noncesig_hex>`，约 610 字节 ——
会拆成好几次 `IAP_data_recv()` 送达；每次回调都从偏移 0 覆写的话，解析时只剩最后一个分片，`flash` 会被当成 `Unknown command`。

兜底有两层：缓冲写满也算一帧；结束符永远不来则由 `IAP_task()` 的陈旧缓冲检查兜住。

## 写进 flash：什么时候才真的有风险

整个暂存机制的意义就在这一步：**镜像先在外部 SDRAM 里过完 CRC 和签名，通过了才擦 app 区。**

> **这是当前装着的那个 app 第一次面临风险的时刻，而且暴露时间只有「擦 + 写」，不是整个传输过程。**

**万一在这中间失败**：app 区半写，metadata 还描述着旧镜像，
于是下次启动报告「应用无效」并请求重新上传 —— **和被打断的传输留下的是同一种可恢复状态。**

⚠️ `HAL_FLASH_Program` 每次固定消耗一整个 32 字节 flash 字，所以拷贝长度向上取整，
**用擦除值填充** —— 这样越过镜像末尾读到的是擦干净的 flash，不是残留的 SDRAM 内容。

## TCP 通道：一次只服务一个会话

`$BOOT/IAPServer/tcp_server.c`。

| 规则 | 为什么 |
|---|---|
| **同时只允许一个会话** | 第二个连接会抢走回复通道，并往同一个接收缓冲里灌数据。被拒的 pcb 由 lwIP 自己中止 |
| **只有持有接收状态的那个会话能清它** | 否则任何陌生人的连接/断开都会打断正在进行的传输 |
| **不是持有者发来的数据直接丢弃** | 而不是混进正在接收的镜像里 |
| **安静超过 60 秒就断** | 一个卡住的对端不能一直占着那唯一的会话槽。计时用 lwIP 的 500 ms 粗粒度 tick，所以是每秒轮询一次、60 秒放弃 |

## 「link is DOWN」要等 5 秒才下结论

`$BOOT/IAPServer/IAP_server.c` 的 `IAP_link_report()`。lwIP 初始化时只读一次 PHY 状态，那时自协商常常还没完成；所以开通道后 **5 秒链路仍没起来**才打这句；早于此判会先报 DOWN 再拿到 IP。2026-10-10 真板子核实：插网线不报，拔网线约 5 秒后报。

## 网络发现：限流，以及那条日志为什么必须闭嘴

`$BOOT/IAPServer/udp_server.c` 的 `discovery_reply_allowed()`。
⚠️ **跨仓镜像第 2 条** —— core 侧同名函数在 `libraries/OpenPLC_IAP/src/udp_server.c`。

窗口 1 秒，超过 `DISCOVERY_MAX_REPLIES_PER_SEC` 就不再回复。
（**按全设备封顶而不是按源 IP**，理由见 `$PROD/docs/tables/DECISIONS.md` 第 3 条。）

### 日志一个窗口只说一次，这是限流的一部分

**只有每个窗口的第一次拒绝会打印**（计数恰好等于上限的那一次），之后整窗静默。

理由是四步，缺一步就看不出必要性：

1. 有人用发现请求猛灌板子
2. 如果**每丢一个包就打印一行**，那些 `printf` 都要进日志：bootloader 是 SRAM4 开机缓存 + SWO（[BOOT-LOG.md](BOOT-LOG.md)）
3. **开机缓存只有 4 KB**，几十行就把开机记录和故障记录整条挤掉；接着调试器时每个字符还要等 SWO 腾出位置，
   比以太网灌进来的速度慢几个量级，板子会卡在 `printf` 里
4. **于是这条日志本身，就比它要报告的那次洪水更像一次拒绝服务**，还抹掉了真正要看的记录

论证只在这里写一份，两边代码注释各留一句结论指过来。

## MAC 地址从芯片 UID 派生

`$BOOT/LWIP/Target/ethernetif.c` 的 USER CODE MACADDRESS 块。
⚠️ **跨仓镜像第 1 条** —— core 侧是 `openplc_make_mac_from_uid()`。

**为什么不用生成的那个**：CubeMX 生成的 MAC 是**编译期常量**，
所以同一个局域网上两块板会直接冲突。

派生方式：

```
h = UIDw0 ^ (UIDw1 << 7) ^ (UIDw2 >> 3) ^ 0xA5C39E17

MAC[0] = 0x02          bit1=1 本地管理，bit0=0 单播
MAC[1..4] = h 的四个字节（高位在前）
MAC[5] = UIDw0 ^ UIDw1 ^ UIDw2
```

**用户 app 可以自己另选一个** —— 设备是靠 UID 定位的，不靠地址。

两块板算出的 MAC 不同，2026-09-28 实测（`R1-14`，每块板 MAC 互不相同，见 [M1-firmware-upgrade.md](../M1-firmware-upgrade.md) 功能表）。
