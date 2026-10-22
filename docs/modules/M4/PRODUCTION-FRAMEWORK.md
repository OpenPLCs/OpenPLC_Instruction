# 产线测试框架 —— 方案文件与步骤序列

**这份文件定义上位机产线侧的形状**：一份方案文件怎么写、有哪些步骤类型、执行语义是什么。

- `pt.*` 协议本身 → [PORTTOOL-FLOW.md](PORTTOOL-FLOW.md) 的 A 部分
- 取舍理由 → [DECISIONS.md](../../tables/DECISIONS.md) 第 22–25 条

> **固件不参与这份文件描述的任何事。** 按[第 22 条](../../tables/DECISIONS.md)，板子只吐原始值，判定全在这里。

---

## 一、参考架构（用户 2026-09-07 给的截图）

用户给了另一个项目的产线测试软件截图 —— `AiLinkFactoryAutoV0.01`，一个语音产品的产线工装。**它不是我们的东西，内容全不一样，但形状是我们要的那个形状。**

### 三栏 = 三层

| 栏 | 内容 |
|---|---|
| 左 | **方案文件树** —— `HaierVoice.jts`，一整套测试方案是**一个可加载的文件** |
| 中 | **有序步骤表** —— `SELECT` 复选框 + `ITEM` 名称。勾掉就是跳过这一步 |
| 右 | **属性网格** —— 选中某一步，显示它的参数，按组折叠 |

选中 `PushBinToBoard` 时右栏显示的分组：

```
Adb      AdbCommand        = adb push
BinFile  BinFileFromPath   = ../bin/uart_test
         BinFilePushToPath = /tmp
Tool     ToolFileName      = MK-TMYYMK-01(ADB)_1.3…
         ToolName          = adb.exe
杂项     ExecuteCondition  = PASS
         RetryCount        = 0
         RetryInterval     = 200
         SleepTimeAfter    = 0
         SleepTimeBefore   = 0
         Timeout           = 20000
```

### 三条要抄的

1. **「杂项」那六个字段是每个步骤都有的，与步骤类型无关。** 这是框架和「一堆脚本」的分界线。
2. **外部工具是配置项，不是驱动代码。** `ToolName = adb.exe` + `AdbCommand = adb push` —— 框架只管起进程、传参、收结果。工具版本（`ToolFileName`）也进方案，所以换工装工具不改程序。
3. **人工判定是一个步骤类型**（`User Confirm`）。我们的指示灯目视和安全测试结果正好落在这里。

### 一条不抄的

**他们每个功能一个手写步骤类型**（`UartCheck` / `SoundRecording` / `soundPlay`）。我们不这么做 —— 见[第 25 条](../../tables/DECISIONS.md)，我们有 `pt.caps` 自描述，三个通用类型就够，加端口不动程序。

### 从他们的类型名读出的分类

| 类 | 他们的步骤 |
|---|---|
| 生命周期 | `Init` `Deinit` |
| 追溯 / MES | `Parse Label`（扫码解析 SN）`iMES Pre Check` `CreatFactoryTest` `MoveTinatest` `CreatTinatestOk` `SynchronizeDataToFlash` |
| 设备交互 | `Find Device` `CheckAppStartSucc` `PushBinToBoard` `UartCheck` |
| 产品专有 | `SoundRecording` `soundPlay` |
| 人工 | `User Confirm` |

⚠️ **注意 MES 那一类占了六步之多**，但它们只是**几个步骤类型**，不是框架内建能力。这正好印证[第 20 条](../../tables/DECISIONS.md)「MES 不做只留接口」—— 留接口 = 留两个步骤类型（读 SN、推结果），不是做一套系统。

---

## 二、方案文件

**格式 JSON。** 理由：Go 标准库自带，不破坏[第 7、8 条](../../tables/DECISIONS.md)的零安装与纯 Go 一键三平台交叉编译。代价是不能写注释 —— 用 `_note` 字段兜。

### 骨架

```json
{
  "schema": 1,
  "name": "OpenPLC 整机 FCT",
  "limit_version": "2026-09-07-a",
  "steps": [
    {
      "id": "din-all",
      "type": "PtSession",
      "enabled": true,
      "_note": "八路数字输入，工装板逐路给 24V 激励",

      "execute_condition": "PASS",
      "retry_count": 0,
      "retry_interval_ms": 200,
      "sleep_before_ms": 0,
      "sleep_after_ms": 0,
      "timeout_ms": 20000,

      "port": "din",
      "params": { "ch": "1,2,3,4,5,6,7,8", "period": 200 },
      "frames": 5,
      "checks": [
        { "field": "v", "op": "eq", "value": "0xFF" }
      ]
    }
  ]
}
```

**`limit_version` 必须有**：产线测试指南 2.6 要求每站记录「软件 / 限值版本」。方案文件改了就要动这个字段。

**运行时从哪读**：PortTool 找 exe 旁边的 `plans/`，找不到才退回当前目录下的 `src/plans`（从仓库根跑的情况）。`$PORTTOOL/tools/build.sh tool` 每次编 PortTool 都把 `$PORTTOOL/src/plans/*.json` 拷进 `Output/bin/<平台>/plans/` —— **仓库那份是源头，`Output/` 那份是产物，会被下次构建覆盖**；产线自己新写的方案文件留在原地不动。面板只列这个目录里的方案供页头「判据来自哪份方案」选择，不编辑、不运行（[决策 102](../../tables/DECISIONS.md)）。

### 校准通道（`calibration`）

方案顶层可以带一个 `calibration` 块，列出校准的四路和各自的单位、满量程。**它不是判据**：校准只取最小二乘的 k、b，不判残差、不拦 k、b；±1 % FS 是 AI / AO 读数 / 输出测试的判据（[决策 99](../../tables/DECISIONS.md)，改了[决策 90](../../tables/DECISIONS.md) 的「精度」一行）。

```json
"calibration": {
  "temperature_c": 25,
  "channels": [
    { "channel": "AI1", "unit": "mV", "full_scale": 10000 },
    { "channel": "AI2", "unit": "mA", "full_scale": 20 },
    { "channel": "AO1", "unit": "mA", "full_scale": 20 },
    { "channel": "AO2", "unit": "mA", "full_scale": 20 }
  ]
}
```

| 字段 | 意思 |
|---|---|
| `channel` | `AI1`、`AI2`、`AO1`、`AO2` 之一，和校准值区的四路一致；不许重复 |
| `unit` | 拟合用的单位，跟这一路登记的档位走：电压档 mV、电流档 mA（[决策 134](../../tables/DECISIONS.md)）；只收这两个 |
| `full_scale` | 满量程，单位同 `unit`（电压档 10000 mV、电流档 20 mA）。最大残差按它换算成 % FS，只显示、只存档 |
| `temperature_c` | 校准时的温度，只记录不判 |

方案里没有这个块，拟合照算、照存档、四路齐了照出扇区 15 镜像，只是残差不换算成 % FS。

### 安规问卷（`safety`）

方案顶层可以带一个 `safety` 块，列出工装完整测试第 5 步安规卡片上要人逐条答「是 / 否」的题目。题目还没人给出，随附的方案里是空列表；没有这个块等于没有题目。卡片怎么用、答案进报告哪里见 [PORTTOOL-FLOW.md](PORTTOOL-FLOW.md)「C.3.4」。

```json
"safety": {
  "questions": []
}
```

| 字段 | 意思 |
|---|---|
| `questions` | 题目，一条一个字符串，原样显示在卡片上；不许空字符串、不许重复 |

### 六个通用字段的语义

| 字段 | 语义 |
|---|---|
| `execute_condition` | `PASS`（上一步通过才跑，默认）/ `FAIL`（上一步失败才跑，用于补救或收尾）/ `ALWAYS`（无论如何都跑，用于 `Deinit` 这类必须收尾的步骤） |
| `retry_count` | 判定失败后重试次数。**重试记录不覆盖原失败** —— 产线测试指南 2.6 明确要求 |
| `retry_interval_ms` | 两次尝试之间等多久 |
| `sleep_before_ms` / `sleep_after_ms` | 前后延时。继电器吸合 ≤8 ms、VREFBUF 稳定要 20 ms 这类物理等待放这里，不写进固件 |
| `timeout_ms` | 这一步的总超时。超时算 FAIL，且要和「判定失败」在报告里区分开 |

`enabled: false` = 界面上勾掉。**跳过的步骤要进报告并标明是跳过的**，不能静默消失（产线测试指南要求任何跳过都可追溯）。

### 判据（`checks`）

一条 check 判帧里的一个字段：

| 字段 | 说明 |
|---|---|
| `field` | 帧里的字段名，如 `v`、`ch1`、`miss`、`vdda`、`errors`。另有两个合成字段：`_text`（整行原文，给 `contains` 用）、`_exit`（暂未使用） |
| `op` | `range`（`min`/`max`）· `eq` · `ne` · `contains` · `count_zero`（必须为 0，用于 `miss` / `junk` / `errors`） |
| `min` / `max` / `value` | 按 `op` 取用 |
| `unit` | 只用于报告显示，不参与判定 |
| `if_present` | `true` 时帧里没有这个字段算过，有就照常判；默认缺字段判不过。只给某种固件报不出的字段用（RS485 的 `overrun`） |

**`eq` / `ne` 两边都是数字时按数值比**，所以固件打 `v=0xFF`、方案里写 `255` 也相等。都不是数字时按大小写不敏感的字符串比。

⚠️ **`ch<n>` 有的端口是复合串**（`ain` 是 `raw/mV`、`aout` 是 `asked/量化/µA`、`temp` 是 `mV/deci℃`），判据要能指到第几段。用下标形式，**下标从 0 开始**：`ain` 的 `ch1[0]` 是 raw、`ch1[1]` 是 mV。

**`peer_*`：PC 端量出来的字段。** `eth` / `usb` 的 `mode=mirror` 步骤（[PORTTOOL-FLOW.md](PORTTOOL-FLOW.md) B.9），三个数在 PC 上算，执行器在判之前把它们并进最后一帧：

| 字段 | 是什么 |
|---|---|
| `peer_sent` / `peer_echoed` | PC 发出的包数 / 原样收回的包数 |
| `peer_lost` | 发出后没收回的包数；丢包率判 0 就判它 `eq 0` |
| `peer_bad` | 收回来但内容不对的包数 |
| `peer_kbps` | 收回的有效字节折成 kbit/s |
| `peer_rtt_min_us` / `peer_rtt_avg_us` / `peer_rtt_max_us` | 每包往返时间，微秒 |

板子的帧里没有 `peer_` 开头的字段，两边不会撞名。

**另外三个合成字段**（板子的帧里没有 `_` 开头的字段）：

| 字段 | 在哪种步骤上 | 是什么 |
|---|---|---|
| `_changes_<字段>` | 标准机上的会话（`on: "ref"`，见下一节） | 判的那段时间里，这个字段在相邻两帧之间变了几次。DO 方波数翻转次数就判它，如 `_changes_ch3` |
| `value` | `UserReading` | 人填的数，原样进报告 |

⚠️ **字段不存在算失败，不算跳过。** 方案里写了固件已经不报的字段，必须当场看见 —— 静默跳过的限值就是没测过的板子。

⚠️ **`loop=ctrl` 的端口，`seq/rx/miss` 不是该端口的判据** —— 它们只说明控制口活着（见 [PORTTOOL-FLOW.md](PORTTOOL-FLOW.md) A 部分）。方案文件里给这些端口写 `miss` 判据是**假判据**，校验器应该报警。

### 在标准机上跑（`on`）

标准机是执行器的第二条板子连接（[决策 103](../../tables/DECISIONS.md)）。步骤写 `"on": "ref"` 就发给标准机，不写或写 `"dut"` 发给被测板。

| 事 | 定案 |
|---|---|
| 哪些类型能写 | `PtSession`、`PtRun`、`PtRaw`；其余类型只能是 `dut` |
| `PtRun` / `PtRaw` 写 `ref` | 照常跑，只是对着标准机 |
| `PtSession` 写 `ref` | **陪下一步跑**：执行器先在标准机上起会话、等到它第一帧，再跑紧跟着的被测板步骤，跑完才停标准机。下一步必须是 `dut` 的 `PtSession` / `PtRun` / `PtRaw` |
| 判标准机那一步 | 用被测板那一步读完之后、停端口之前标准机的最后一帧；读完后再等标准机两帧，盖住它一个采样周期的延迟 |
| 门和开关 | 两步算一对：门、`sleep_before_ms` 看标准机那一步；被测板那一步不许写 `execute_condition`，两步的 `enabled` 必须相同；重试只在被测板那一步上，标准机那一步不许写 `retry_count` |
| 一对之后的门 | 两步里有一步没过，后面 `PASS` 门的步骤就不跑 |
| 看门狗 | 标准机会话期间执行器给标准机武装 `pt.hold`、每 2 秒续期，停会话后解除 —— 和面板持续测试同一套（[PROD-CONFIG-ITEMS.md](PROD-CONFIG-ITEMS.md)「F · 安全联锁」），因为标准机的 DO 在出 24 V |
| 没接标准机 | 标准机那一步记 ERROR，陪的那一步记 SKIPPED；不会拿被测板代跑 |
| 离线校验 | `CheckAgainstCaps` 只查被测板的步骤，标准机的步骤对标准机自己的 `pt.caps` 查 |

⚠️ **CAN 接标准机时 `miss` 不能当判据**：被测板 `mode=normal` 要对端原样送回才闭环，标准机 `mode=echo` 回的是加一，所以 `miss` 一直涨；判据用被测板的 `rx_frames`（回来的帧数）。出处 `$BOOT/TestCase/porttool/porttool_can.c` 的 `can_collect()` 和 `PortTool_EchoTick()`。

### 上位机当对端（`peer`）

`PtSession` 的 `peer` 说链路另一头由这台电脑上的什么来答，执行器在这一步里起它、停它：

| 字段 | 是什么 |
|---|---|
| `tcp` | `auto`（用帧里的 `ip=`、`port=`）或 `host:port` |
| `serial` | 用面板绑过的串口适配器，方案里不写口名（[决策 73](../../tables/DECISIONS.md)） |
| `usb` | 板子自己的 CDC 口，按 USB id 找 |
| `baud` | 串口对端的波特率，0 用默认 |
| `can` | 上位机的 CANable 2.0（SLCAN，按 USB id `16D0:117E` 找），和标准机 `mode=echo` 一样回：同一标识符、同一长度、负载加一。位速率取这一步的 `params.baud`，没写用 500000 |

**对端什么时候算起来**（`$PORTTOOL/src/ptseq/peer.go:68-71`、`ptseq.go:453-470`）：每来一帧试一次打开对端，连上后这一步的帧数从 0 重新计；从这一步开始算 10 s 内对端还没起来，帧数够了也接着等（`peerGrace`）。宽限按时间不按帧数，帧停了的会话也能出结论而不是超时；10 s 盖住板子 DHCP 拿地址的 5–6 s。

⚠️ **TCP 对端「已连上」不等于板子在答**（`peer.go:158-159`、`:189-198`）：TUN 模式的 VPN 会接受到任意地址的 TCP connect，所以对端显示连上了却收到 0 字节。这种情况报告里写明「没东西回来，多半是 VPN 或代理占了默认路由」，不当成板子的 `conn=0` 故障。

---

## 三、步骤类型

和板子说话的只有三个 `Pt*` 通用类型（[第 25 条](../../tables/DECISIONS.md)）：

| 类型 | 干什么 | 专有参数 |
|---|---|---|
| `PtSession` | 起会话、采 N 帧、**判最后一帧**、停会话（失败也停） | `port` · `params` · `frames` · `checks` |
| `PtRun` | 一次性动作，跑完回命令循环，判返回的 `k=v`。⚠️ 检查的散文先来、`OK` 行后到，执行器按后者判 | `target` · `params` · `checks` |
| `PtRaw` | 敲任意 `pt.*` 命令，判应答 | `command` · `checks` |

**没有 `Init` / `Deinit` 类型**：那两个在参考架构里是「打开设备 / 关闭设备」，我们的等价物是「连串口 / 断串口」，由执行器自己管，不占步骤位。

### 四个非设备类型（2026-09-07 补齐）

| 类型 | 干什么 | 专有参数 |
|---|---|---|
| `Tool` | 起外部进程（JLINK、程控电源 CLI、工装板工具），判输出或退出码 | `tool_name` · `tool_args` · `tool_dir` · `checks` |
| `UserConfirm` | 问人。**没人可问时是 ERROR 不是 PASS** —— 一个因为「只有人能看见」而存在的步骤自己判自己通过，是最坏的结果 | `prompt` |
| `UserReading` | 让人填一个数（万用表读数这类），走 `checks` 判，字段名 `value`；报告的 `extra.value` 留原样（[决策 103](../../tables/DECISIONS.md)）。填的不是数、或没人可问，都是 ERROR | `prompt` · `unit`（只显示）· `checks` |
| `ReadSN` | 从外部拿 SN：`arg` / `stdin` / `file:<路径>` | `source` · `checks`（可校验 SN 的形状） |
| `PushResult` | 把报告交出去：`file:<路径>` / `dir:<目录>` | `sink` |

**`Tool` 没有驱动层，这是刻意的**：哪个程序、什么参数都是方案数据，所以换一台程控电源是改方案不是改程序 —— 参考架构驱动 adb 就是这么干的。

⚠️ **`dir:` 落盘的文件名带 SN 和时间戳**，所以重测的报告落在第一次旁边，**永远不会盖掉它**（产线指南 2.6：失败数据不得覆盖）。

⚠️ **`PushResult` 写出去的报告不含它自己那一步** —— 它正在跑。一份声称包含「产生自己那一步」的报告，描述的是一次还没结束的运行。

### 判哪一帧

`PtSession` 判**最后一帧**。`frames` 大于 1 的意义是「让值稳定下来」和「证明帧在持续来」，不是「每帧都判」。

采到的每一帧的原文都进报告，所以数据没丢 —— 事后要按别的规则重判，原始值都在。

---

## 四、执行语义

```
对每个 enabled 的步骤，按序：
  1. 看 execute_condition，不满足 → 记「跳过（条件不满足）」，下一步
  2. sleep_before_ms
  3. 尝试（最多 1 + retry_count 次）：
       起 timeout_ms 计时 → 执行 → 跑 checks
       通过 → 记 PASS，跳出
       失败 → 记本次尝试（含原始值），等 retry_interval_ms，再来
  4. sleep_after_ms
  5. 全部尝试都失败 → 记 FAIL
```

**三条硬规矩**：

1. **每次尝试都进报告**，包括被重试掉的那些失败。产线测试指南 2.6：「测试失败数据不得覆盖」。
2. **原始值必须记下来，不只记结论**。限值以后会改，改了要能拿旧数据重判。
3. **超时和判定失败要分开记**。超时通常是接线或治具问题（假失败），判定失败通常是板子问题 —— 混在一起，产线的失败分析就没法做。

---

## 五、报告

一次运行出一份结构化文件（CSV 给人看、JSON 给系统读），至少包含：

方案名与 `limit_version` · 工装软件版本 · 固件版本（`pt.caps` 报的）· 板子 UID（`pt.id` 报的）· 接了标准机时它的固件版本和 UID（`ref_firmware`、`ref_uid`）· SN（若有 `ReadSN` 步骤）· 起止时间 · 逐步骤：id / 类型 / 结果 / 每次尝试的原始值 / 判据本身 / 耗时。

**判据本身要进报告**，不只是「PASS」—— 否则事后拿到一份报告没法知道当时是按什么标准判的。

---

## 六、方案只在命令行跑

- 面板不再编辑和运行方案（[决策 102](../../tables/DECISIONS.md)）；`porttool run <方案> --port COMx` 照旧，`UserConfirm` 在 stdin 上问 `pass? [y/N]`，`--yes` 全部当通过
- `--ref COMy` 接标准机（两头都写 `sim` 时是两块模拟板，标准机 DO1–8 接被测板 DI1–8、标准机 DI1–8 接被测板 DO1–8 交叉接好）；`UserReading` 在 stdin 上要一个数，不是数就再问，`--yes` 不替人填数
- **不合固件的方案拒跑**（决策 77）：`CheckAgainstCaps` 报出问题就不跑，列出哪一步、为什么

## 七、还没定的

- **报告推给谁、什么格式**（`PushResult` 的 `sink`）—— 等产线那边的系统确定
- **仪器与工装板的调用形态** —— `Tool` 类型起进程是兜底方案；工装板若走串口协议，可能值得一个 `Fixture` 类型。等工装板的接口方式（硬件那边）定下来
