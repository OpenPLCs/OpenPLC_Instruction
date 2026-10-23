# 改这个 CubeIDE 工程的硬规矩

只对 bootloader 仓库成立。

## CubeMX 生成区不能手工改

代码必须写在 `/* USER CODE BEGIN *** */` … `/* USER CODE END *** */` 之间，否则从 `.ioc` 重新生成时会被 CubeMX 删掉。

重新生成会删掉块外的手写代码（出过 `SystemClock_Config();` 和四个 naked fault handler 被删的事）。

**USER CODE 块之外的东西，不要自己改 —— 报给用户，由他去改 `.ioc`。** 手工改生成区只是"这次能用"，下次重新生成全废；**只有 `.ioc` 才是单一事实源**。发现需要改动时，说清楚"哪个文件、哪一项、应该是什么值"。

**`.ioc` 本身也不要手改，在 CubeMX 界面里点** —— 引脚编号、`Mcu.PinsNb`、`RCC.IPParameters` 写错时 CubeMX 静默丢弃，只有界面那条路会被工具校验。

找不到合适的 USER CODE 块，就把代码挪到 CubeMX 不生成的文件（如 `IAPServer/`）。CubeMX 自己会生成的调用（`MX_*_Init()`、`SCB_EnableICache()`）留在原位不要搬。

### 已经通过 `.ioc` 固化的

- `USBD_LPM_ENABLED` —— `.ioc` 里 `USB_DEVICE.USBD_LPM_ENABLED-CDC_FS=0`。否则设备对主机声称支持 USB 2.0 LPM，而 `USBD_LL_Init()` 里 `lpm_enable = DISABLE` 并没开它。
- CRS 跟 USB SOF 校准 HSI48、LSE 驱动 `MEDIUMLOW`（[决策 157](../tables/DECISIONS.md)）—— `.ioc` 里 `VP_RCC_USB.Mode=USB_FS`（界面 RCC → CRS SYNC 选 `USB_FS`）、`RCC.LSE_Drive_Capability=RCC_LSEDRIVE_MEDIUMLOW`。

### 重新生成后仍须复查（不在 USER CODE 块内）

- `.ioc` 里 PG9 的信号类型（见 [../hardware/HARDWARE-FACTS.md](../hardware/HARDWARE-FACTS.md)）
- `STM32H743IIKX_FLASH.ld` 的 `FLASH LENGTH` 是 **128K**，整个扇区 0 —— 根区在扇区 15（决策 72），扇区 0 里没有别的东西。上限不能再大：`0x08020000` 起是 app
- **`.cproject` 里链接脚本那个选项的值必须是 `${workspace_loc:/${ProjName}/${PLC_LD_SCRIPT}}`，不是某个写死的 `.ld` 文件名** —— 见下一节
- RTC 仍走 LSE（[决策 36](../tables/DECISIONS.md)）：`Core/Src/rtc.c` 的 `HAL_RTC_MspInit()` 里是 `RCC_RTCCLKSOURCE_LSE`，`Core/Src/main.c` 的 `SystemClock_Config()` 里有 `RCC_OSCILLATORTYPE_LSE` 和 `LSEState = RCC_LSE_ON`；上电到出 banner 不应有 5 秒停顿 —— 有就是 LSE 没起振，见 [HARDWARE-FACTS.md](../hardware/HARDWARE-FACTS.md)「RTC 走 LSE」

## 两份链接脚本，选哪份由环境变量决定

**bootloader 和工装镜像的 FLASH 区大小不一样**，因为约束不一样：

| 镜像 | 脚本 | FLASH | 为什么 |
|---|---|---|---|
| bootloader | `STM32H743IIKX_FLASH.ld` | **128K** | 上面 0x08020000 起是 app，不能被盖 |
| 工装 | `STM32H743IIKX_FLASH_PORTTOOL.ld` | **2048K** | ST-Link 整片烧、不走 IAP，上面那两件东西一件都不存在 |

**机制**：`.cproject` 里那个选项的值是 `${workspace_loc:/${ProjName}/${PLC_LD_SCRIPT}}`，变量的**工程默认值是 bootloader 那份**，写在 `.settings/org.eclipse.cdt.core.prefs` 里。工装构建靠 headless 的 `-E PLC_LD_SCRIPT=…` 临时换掉：

```
stm32cubeidec.exe … -D PORTTOOL_ENABLE=1 -E PLC_LD_SCRIPT=STM32H743IIKX_FLASH_PORTTOOL.ld -build …
```

**和 `PORTTOOL_ENABLE` 同一个原则**（[DECISIONS.md 第 14 条](../tables/DECISIONS.md)）：**只活在要它的那一次构建里，不写进工程文件**。所以随手编一次、或者在 IDE 里点一下构建，出来的都还是 bootloader。

⚠️ **在 IDE 里怎么点都编不出工装镜像，这是用户 2026-09-10 要的形状，不要去「修」它。** 工装镜像只有一条路：`$PORTTOOL` 里的 `start.sh fixture`（决策 76）。它把 `$BOOT` 的源码拷进临时目录再编，镜像留在 `$PORTTOOL/Output/fixture/`，不碰 `$BOOT/Debug/` 和 IDE 的 workspace（决策 86）。

### 让 CubeMX 不改写这个选项，做不到

它按芯片型号自己生成默认名，不读 `.cproject` 里 ST 那份 `||` 分隔的记录，`.ioc` 里也没有这个字段（2026-09-10 重新生成验过）。只能改完再修回来；改坏了藏不住 —— 工装镜像装不进 128K，链接器当场 `region 'FLASH' overflowed`，`build_image.py` 另有一道核对链接器命令行的检查。

### 生成后自动修回来

`.ioc` 的 `ProjectManager.UAScriptAfterPath` 指向 `tools/restore_ld_script.bat`，CubeMX 每次生成完自动跑它，把那一行改回 `${PLC_LD_SCRIPT}`（2026-09-24 实测，重新生成后 `P17` 直接是绿的）。

⚠️ **自动修靠的是「CubeMX 写完 `.cproject` 之后才跑脚本」这个顺序，而顺序由 ST 决定** ——
哪天变了会静默失效，所以静态检查 **`P17`** 不能省：它直接查 `.cproject` 里那一行是不是变量。

⚠️ **重新生成后必查这两处**（`P17` 只盯第 1 条）：

1. 那个选项的值有没有被 CubeMX 改回写死的 `STM32H743IIKX_FLASH.ld`。⚠️ **`.cproject` 里 ST 自己那个 `||` 分隔的大字符串（`com.st.stm32cube.ide.common.services.build.inputs…`）里仍然写着 bootloader 那份文件名** —— 那是 ST 用来回写的记录，所以这一处**被改回去的概率不低**。改回去的表现不是报错，是**工装镜像忽然又受 128K 限制**。
2. `.settings/org.eclipse.cdt.core.prefs` 还在不在、默认值还是不是 bootloader 那份。**这个文件没了，`${PLC_LD_SCRIPT}` 会展开成空**，链接器拿不到 `-T`，只报 `ld returned 1 exit status`。`.gitignore` 单独放行了这一个文件（只有这一个变量），`.settings/` 其余照旧忽略。

**两处都由 `build_image.py` 自动兜着**：它在构建日志里核对链接器实际拿到的是哪一份，拿错了当场判失败 —— 因为拿错是静默的（工装拿到 bootloader 那份只是「装不下」，而 bootloader 拿到工装那份会**烧穿 app 区**）。

四个 fault handler 已经做到重新生成安全：在 PD 块里把 CubeMX 生成的版本改名让路，在 USER CODE 1 里定义真正的 naked 版本。
