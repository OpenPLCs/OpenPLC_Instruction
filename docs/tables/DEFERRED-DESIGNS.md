# 设计过但推迟的方案

这里的东西**都已经想清楚了，是主动推迟的，不是遗漏**。有人问"为什么不做 X"时看这里。

## 故障自愈

**当前行为**：`Core/Src/stm32h7xx_it.c` 的 `IT_Fault_Report()` 打印完故障报告后停在 `while (1) {}`。**不要改。**

**2026-08-12 决定**：自愈方案已设计过，但**优先级排到最后**，等其他功能全部处理完再回来做。

### 裸的自愈是不可接受的

把 `while(1)` 直接换成 `HAL_NVIC_SystemReset()` 会**同时丢掉现场证据、又没有终止条件** —— 确定性故障会变成无限复位循环，继电器反复抖动。

成立的方案必须三件事齐备：

1. **故障记录先落 SRAM4 空闲区**（`0x38000010`，仅剩 16 字节）—— 写 RAM 不会引发二次故障；下次启动再由 bootloader 在正常上下文里写进 flash 事件日志。
   ⚠️ **不要在 fault handler 里直接写 flash** —— fault 可能正好发生在写 flash 期间，二次故障就是锁死。
2. **连续故障计数**，在 `server_jump_to_app()` 跳转前最后一步清零。
3. **数到 3 就不再复位**，强制 `IAP_ALL` 停在 bootloader（CDC + 以太网全开），现场还能被 IAPTool 重刷救回。

### IWDG 兜底这条路是堵的

H7 的 IWDG 一旦启动**只有上电复位能停**，会跟着跳进用户 app，要求每个 sketch 都喂狗 —— bootloader 不能给用户 app 加这种义务。

相关：[HARDWARE-FACTS.md](../hardware/HARDWARE-FACTS.md) 的 SRAM4 no-init 机制。

## Arduino 发现声明形式

`platform.txt` 现在用的是：

```
pluggable_discovery.network_discovery.pattern.windows="{runtime.platform.path}/tools/discovery/bin/windows_amd64/network_discovery.exe"
```

官方文档对这种 `.pattern` 形式有明确警告：

> "We strongly recommend using this syntax only for development purposes and **not on released platforms**."

正式发布应改用 `pluggable_discovery.required=VENDOR:NAME` + 在 package index 里声明 `discoveryDependencies`。

（顺带确认：`.pattern` **支持传参**，官方例子 `pluggable_discovery.teensy.pattern="...\teensy_ports" -J` 就带参数。）

**未处理。**
