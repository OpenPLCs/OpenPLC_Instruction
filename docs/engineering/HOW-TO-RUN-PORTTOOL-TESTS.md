# PortTool 的测试（`$PORTTOOL`）

PortTool 仓的测试都在 `$PORTTOOL/TestCase/` 下，入口是本仓自己的菜单 `TestCase/test.sh`（Windows 上在 Git Bash 里跑；带参数不出菜单）：

```
tools/build.sh find-tools   # 第一次：探测本机工具，写 tools/local.json
TestCase/test.sh all        # go test（含面板词典检查）/ go vet / T4-01 / T4-05 / T4-02（接模拟板）；quick 跳过 T4-02
```

用例定义在 [M4 产线工装](../modules/M4-production-fixture.md)。

## 主机侧测试（`TestCase/host/`，不需要板子）

| 目录 | 怎么跑 | 覆盖什么 |
|---|---|---|
| `host/porttool_caps/` | `TestCase/test.sh t4-01`，即 `CGO_ENABLED=1 CC=<HOST_CC> go test -race -count=1 -v ./TestCase/host/porttool_caps/ -args -build`（`HOST_CC` 用 `go run ./tools/ptbuild get HOST_CC` 取）。不带 `-build` 时不编固件，只拿已提交的 `caps_golden.txt` 跑 Go 那半（`go test ./...` 就是这样） | **T4-01** 端口工装的协议契约，判据见 `$PORTTOOL:TestCase/host/porttool_caps/PORTTOOL-CAPS-TEST.md`（贴着代码放，没有搬过来） |
| `host/porttool_demo/` | `TestCase/test.sh t4-05`，即 `go test -count=1 -v ./TestCase/host/porttool_demo/ -args -build`，要 `HOST_CC` 和它旁边的 g++（或 `$CXX`）；板卡包取 `$CORE_REPO`，没设就取 `tools/local.json` 的 `CORE_REPO`。两边都编进 `Output/build/porttool_demo/`，不动 `Output/bin/`（开着的面板占着那里的模拟板）。不带 `-build` 时跳过 | **T4-05** 第 6 步的 demo（`$CORE_REPO/libraries/OpenPLC_Ports/examples/FixtureDemo/`）和工装固件讲同一套协议：同一份 Go 测试对两边各跑一遍。demo 只编协议核心，板卡包 API 是桩；判据和测不到的东西见 [M4 产线工装](../modules/M4-production-fixture.md) 的 `T4-05` 行 |
| `host/porttool_panel/` | 在仓根 `go run ./TestCase/host/porttool_panel --port COMx`（**真板子**）或 `--port sim`（**模拟板，不用板子**，见下），要本机的 Chrome（`tools/local.json` 的 `CHROME`，「找本机工具」探测） | **T4-02** 面板在真浏览器里点一遍，判据见下面「T4-02 的判据」 |
| `host/porttool_plan/` | `go test ./TestCase/host/porttool_plan/` | **T4-04** 方案执行器与面板接口，覆盖什么见下面「T4-04 覆盖什么」 |
| `host/porttool_plan/` 的 `ref_test.go`、`src/slcan/`、`src/simboard/` | `go test ./TestCase/host/porttool_plan/ ./src/slcan/ ./src/simboard/` | **T4-04 的标准机和人工填数部分**（决策 103）：`on: "ref"` 一对步骤的先起标准机、后停、看门狗续期和解除、门和开关、没接标准机记 ERROR；`UserReading` 的数走 `ptcheck`、原样进报告、不是数或没人可问记 ERROR；随包方案的 DI 走位 8 拍、DO 标准机读、方波翻转次数、CAN `normal` 在**两块交叉接线的模拟板**上跑通；SLCAN 驱动对着假串口开通道、收发、回送加一。⚠️ 测不到：真 CANable 和真 CAN 总线（驱动只对假串口跑过）、真标准机（模拟板之间只接了 DO→DI，CAN 是模拟板自己回环）、真端子电压 |

### T4-02 的判据

T4-02 是 `go run` 的程序（chromedp 驱动 Chrome），不是 `go test`：它要 `--port`、要起 PortTool 和 Chrome、一跑几分钟，所以 `go test ./...` 只编译它不跑它。

按段排；布局和各块的定义见 [PORTTOOL-FLOW.md](../modules/M4/PORTTOOL-FLOW.md) C.3.6，AI / AO 见 C.3.2。

| 段 | 判据 |
|---|---|
| ① | 页面语法、页面异常和控制台 error 直接判失败 |
| ② | 连接前后：控制口是下拉、模拟板排最后，连上才放开页面（测试类型也是）、断开再关上，记下的控制口 |
| ③ | 布局（决策 128）：测试类型在左栏最下、只有研发测试和工装完整测试，没有制作标准机；研发测试是端口 / 卡片 / 日志，端口页头左半端口名和端子、右半其余（还没测过的端口右半只写「还没测过。」），工装完整测试是中间 + 右侧「正在进行」；菜单和端口列表不发 `pt.start`（AI / DI 页也是，点「开始读取」才读，决策 137），同组互斥，功能测试只剩产线 CAN 项。工装完整测试三层：唯一的启动按钮「配置完成，开始测试」；四块子测试各带时间（功能 / 用户级单次 / 10 / 30 分钟 / 1 小时，老化 1 / 2 / 4 / 8 小时，安规没有）；卡片只有勾选、参数和「项目 / 预期」，没有开始、组时长和结果 |
| ④ | 三种配置：改了的配置重开面板还在，配置页不发 `pt.start`；第 ③ 层每个端口每一项写明在这项测试里怎么跑、出现在哪几类；DI 对端人工写明完整测试跳过；CAN 没接标准机时默认上位机、只列上位机的判据；DO 人工只列压降判据；用户级写明真板子跑 demo、没有 SDRAM 和 RS232；老化里 AO 带负载写明开到结束 |
| ⑤ | 测试项「开始」：勾选的项出结论、没勾的记没测，问题框答了给结论；带时长时「开始」下写日志路径 |
| ⑥ | 每个端口用不要人、不要对端的项各开始一次，端口结论必须是通过 |
| ⑦ | 卡片上不剩协议词；控制口回环的发 / 收 / 丢计数旁写明不是该口结论 |
| ⑧ | 连接区：板子时间在走，自动回环框可切换，RS485 绑上 / 断开（真板子；模拟板上 RS485 已由识别认出，不手绑），对端出错显示原因；转换器自动识别（决策 146）：连上后自动认出 RS485 是 `SIM-A`、CAN 是 `SIM-CAN`，`sim.wiring` 接错后点「重新识别」两行各写出哪个口的暗号出现在哪、退回手选，拔掉 RS485 的线后写「什么都没收到」 |
| ⑨ | 各端口专项：CAN 卡片能选对端，CAN 分析窗口（决策 111）开始后弹出、两个方向各发一帧都对上、结束记只记录；RS232 选 19200 跑过；KNX 端口结论不看只记录的诊断，`frames` 卡片开着时列出报文、停止记停下；DI 正交两块模拟板数满 400；研发 AI / AO / DI / DO 卡（决策 137）：没有「开始」，AI / DI 进页不发 `pt.start`、点「开始读取」才读、再点停止并按勾了的路记结果，DO 勾了路按「输出」才出，离开再回来填过的值、结果和最近一次测试时间还在；六个通信口的断开恢复卡（决策 150）各开始一次：问人拔掉、自己断开（`sim.cut`）、问人插回、恢复后卡上列出方案的恢复用时判据，按随包方案判出通过，记恢复用时、丢帧 |
| ⑩ | AI / AO：档位只有电压 / 电流且按 UID 记住；校准走查出回归和 k、b、残差不判；校准点表的误差按 ±1 % FS 标过 / 不过（AO 也是）、不拦拟合；验证点默认落在拟合点之间、重合时提示不拦；读数逐点列原始值 / 换算值 / 标准值 / 偏差 |
| ⑪ | 完整测试：没勾就按不下开始，第 5 步安规要选结论；运行中第 ② 层显示在跑 / 没勾跳过，跑完通过和满进度条；第 6 步在模拟板上灰掉；「正在进行」框整个运行中高度不变，端口列表亮灯，结果、日志、存下的报告步号一致，点结果一行定位到端口和卡片、日志只看这一步，日志两个勾选过滤，跑完结果和日志留着、按钮回到「配置完成，开始测试」；USB 枚举和收发默认都勾（只测一次的不和可重复的互斥），AO 带负载列出每路 ±1 % FS 判据 |
| ⑫ | 换判据方案清掉已有结论 |

⚠️ **模拟板测不到**：真转换器收发暗号、真接线和端子上真收到暗号、控制口「自动找」和手选时的拔插识别（这三样不碰本机真串口，只有 `src/ptmatch`、`src/ptpanel/match_test.go` 的假串口覆盖，要上板看）、真拔线（断开恢复卡在模拟板上由 `sim.cut` 断开，只验面板流程，RS232 转换器拔掉后同名口重开只有 Go 测试的替身覆盖）、真 USB CDC、真转换器接上后链路通不通、真 ST-Link 烧录和第 6 步、真 CANable 和 CAN 波特率（模拟板的 CAN 分析窗口走面板这头的假线）、真的模拟量和 24 V 信号、100 Hz 下漏不漏数（这些由 Go 测试的替身或上板覆盖）；外观好不好看只能人看。

⚠️ **转换器对端（`$PORTTOOL/src/ptpanel/link.go`）在 T4-02 里不跑回送**：模拟板自己扮演每个对端，RS485 一行在模拟板上由识别认出 `SIM-A`、不手绑，收发、回送和 `sink` / `source` 切换一行都不经过。它只靠 `link_test.go` 的单元测试，真转换器上的行为要上板看。

⚠️ **一台机器上同时只能跑一份**：第二份启动时直接退出并说明，因为两份共用日志文件和 exe 旁的配置文件。

### T4-04 覆盖什么

| 部分 | 覆盖什么 |
|---|---|
| 判据算子 | 缺字段一律判失败 |
| 执行器 | 超时与判据失败分得开、重试保留被它替掉的那次失败、失败后的门闸看最后一个真跑过的步骤 |
| 随包方案 | `plans/bench-smoke.json` 和 `plans/station6-poweron.json` 都能拿假板子跑通；方案里的 `pt.run` 目标对着 caps 的 `runs=` 离线校验（打错名字、写一个固件没报过的目标，两种都要报） |
| 面板的方案接口 | 只剩列表和判据选择（决策 102）：**方案名出不了 plans 目录**，`/api/items` 只给板子报了的端口、判据按所选方案解出 |
| 工装完整测试（`full_test.go`） | 一次一份记录、文件名带 SN、安规答案进 `extra`、没通过的步下次问「从第 N 步继续」、停下记 `STOPPED` 后面记 `SKIPPED`、模拟板不写记录、带着产线的根要标红；`safety.questions` 的校验；「烧进板子」写的是这块板自己的镜像、根区不动 |
| 测试项「开始」（`items_test.go`，[PORTTOOL-FLOW.md](../modules/M4/PORTTOOL-FLOW.md) C.3.6「测试项怎么跑」） | 勾 3 项出 3 条结论、没勾的记 SKIPPED、卡片改的参数发到板子、同组互斥和不许改的参数拒跑、人答「否」判不过、选了时长时只测一次的项只跑一次而其余项重跑、会话同时开着、第一次不过就全停并点灯、KNX 只记录的诊断不算端口结论、`/api/lib/start` 和 `/api/ask` 走一遍（看门狗是替身，时长只用几百毫秒，测不到真板子上几小时的长跑） |
| 失败码和断开恢复（`recover_test.go`、`src/ptreport/failcode_test.go`、`src/ptlib/recover_test.go`，C.3.6「失败码」「断开恢复」） | 失败码拼法（判据「字段-算子」、原因码、通道、通过和只记录没有码）、报告顶上汇总；六个断开恢复项在模拟板上由 `sim.cut` 断开、问人拔掉再问插回、按随包严 / 宽两份方案的暂定判据判出通过，判据收紧时不过（失败码 `eth.recover.recover_ms-range`），删掉方案里这一步时回到只记录、不算进端口结论；各口的断开 / 线回来 / 接上判法；RS232 转换器拔掉后控制口按同名重开（假板子关掉再换一块）、在新连接上读复位原因。测不到真线、真转换器和真 USB 重新枚举 |
| 转换器自动识别（`src/ptmatch`、`src/ptpanel/match_test.go`，[PORTTOOL-FLOW.md](../modules/M4/PORTTOOL-FLOW.md) C.3.6「转换器自动识别」） | 哪些口不碰（蓝牙、ST 的 USB 编号、CANable）；`OK match` 的解析；每个端子的结论（认出、没收到、收到不是暗号、两个口、别的端子那类的号、没有 CANable、旧固件、会话在跑）；「自动找」只认回了 `OK porttool=` 的口、两个都回时不选；识别时假串口真收到了各自的暗号、RS485 认出后绑上并记进 `porttool_ports.json`。全是假串口，测不到真转换器和真接线 |

⚠️ **ST-Link 是替身**（`src/stlink/stlinktest`，内存里的 2 MiB flash）：证明发了哪些擦写、写回不碰空格子，证明不了 CubeProgrammer 和真芯片的行为。

## 模拟板：手上没板子时怎么联调

**它是什么**：`TestCase/porttool/` 那些 `.c` 原样编成的 PC 程序，只换掉外设 stub 和最外层 main。命令解析、`pt.caps`、会话逻辑、帧格式、版本号全是固件那份源码，所以固件改了它编不过 —— **不会漂移**。设计理由见 `$PROD/docs/tables/DECISIONS.md` 第 29 条。

```bash
tools/build.sh sim                                        # 编本机的，产出 Output/bin/windows/porttool_simboard.exe
tools/build.sh sim --os linux                             # 用 zig 交叉编，产出 Output/bin/linux/porttool_simboard（另有 darwin、darwin-arm64）
porttool                                                  # 面板的端口列表里选 "sim"
porttool run --port sim --yes src/plans/station6-poweron.json
go run ./TestCase/host/porttool_panel --port sim          # T4-02，不用板子
```

**T4-03 是同一个程序跑 Linux 版**：`--wsl Debian` 让面板在 WSL 里起（用 `Output/bin/linux/PortTool`），浏览器仍是 Windows 上的 Chrome。先 `usbipd attach --wsl` 把串口挂进去，`--port` 写 WSL 里的名字，如 `/dev/ttyUSB1`。

**面板怎么找到它**：`PORTTOOL_SIM` 指定的；没指定就先看 `PortTool.exe` 旁边，再从 exe 所在目录和工作目录往上找 `Output/bin/<本机平台>/`（`src/simboard.Find`）。C 外壳在 `$PORTTOOL/src/simboard/c/`，源文件清单 `sources.txt` 和 T4-01 共用一份。交付包里它就在 exe 旁边（决策 112）。

**模拟板静态链接，不依赖任何 DLL**：动态链接时会加载到 PATH 上 `stlink_server` 目录里那份 32 位 `libwinpthread-1.dll`，以 `0xC000007B` 退出（面板上表现为连上 sim 却没有端口列表，2026-09-29）。

**造故障看面板怎么显示**（手敲进它的 stdin，或在面板底部的命令框里）：

| 命令 | 干什么 |
|---|---|
| `sim.help` | 列全部 |
| `sim.din 0x00` | 数字输入全低，看 din 判失败 |
| `sim.vdda 1800` | 基准坏掉，落在方案的 2400–2600 之外 |
| `sim.ain <ch> <mv>` / `sim.temp <ch> <mv>` | 单路模拟量读数 |
| `sim.link 0` | 拔网线（PHY 的 BSR 和 netif 一起变） |
| `sim.cut <口> <ms>` | 把 `eth` / `usb` / `rs232` / `rs485` / `can` / `knx` 断开这么多毫秒再自己接回，断开恢复卡片在模拟板上自己发它（PORTTOOL-FLOW C.3.6「断开恢复」）；`rs232` 断开期间 stdout 不出、stdin 不收 |
| `sim.walk 1` | 数字输入自己轮转，看面板动起来 |
| `sim.cal 0` / `sim.cal 1` | 校准值区擦掉 / 按本机 UID 写回（增益 1、偏移 0，开机默认是写了的），看「没烧校准值」怎么显示 |

⚠️ **`sim.` 开头的命令真板上一条都没有**，由 `sim_main.c` 自己拦下，不进固件的 `dispatch()`。

⚠️ **它证明不了任何硬件行为。** 读数全是 stub 造的一块理想板子，每根对端线都当接好的；UART 中断收发、`rx_errors`、真 ADC、真 PHY 都不在里面。**它验的是 PC 侧的线路和方案文件。**
