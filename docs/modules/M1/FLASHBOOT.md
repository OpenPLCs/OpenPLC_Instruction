# `flashboot` · bootloader 原地升级

> 按[决策 72](../../tables/DECISIONS.md) 实施：根区在扇区 15，没有根就拒绝（`T1-32` 2026-10-08 上板通过）。

**一条命令把新的 bootloader 写进扇区 0。扇区 0 只放 bootloader 代码**，根区在扇区 15，`flashboot` 不碰它。
类比 BIOS 升级：**中途不允许断电**。

## 线上长什么样

```
flashboot <size> <crc32hex> <imgsig_hex> <cert_hex> <noncesig_hex>
```

**逐字段和 `flash` 相同**，传输与 SDRAM 暂存走同一条路。四处不同：

| | `flash` | `flashboot` |
|---|---|---|
| `imgsig` 用谁验 | `cert` 里那把叶公钥 | **owner 根公钥**（`owner_slot_root()`） |
| 尺寸上限 | `IAP_APP_MAX_SIZE`（1792 KiB） | **128 KiB**（整个扇区 0） |
| 落盘目标 | `IAP_APP_ADDRESS` | **扇区 0**（`0x08000000`） |

`cert` / `noncesig` 的作用不变 —— 会话认证与防重放，和 `flash` 同一条路。

**叶证书换不掉 bootloader。** 一把发给「只准烧 app」的叶，凭同一张证书也能换掉 bootloader，
而换 bootloader 和换所有权是同一个量级的动作。

**没有根的板子拒绝 `flashboot`** —— 没有根就没有人能签这个镜像；先认领（第一次上传会自动认领），再升级。

## 擦写为什么必须在 RAM 里跑

擦扇区 0 的时候，执行擦除的代码本身住在扇区 0。所以整个擦写例程标 `.RamFunc`
（链接脚本已经把这个段收进 `.data`、启动代码已经会拷贝，**不用改脚本**），
全程关中断 —— 向量表也在扇区 0 —— 且不调 HAL，直接写 FLASH 寄存器序列，因为 HAL 在 flash 里。

代码落在 `RAM_D1`（`0x24000000`），**那里可执行** —— MPU region 0 把子区 1
（`0x20000000`–`0x3FFFFFFF`）排除在外（`SubRegionDisable = 0xC7`，见 `Core/Src/main.c` 的 `MPU_Config()`），
落回默认内存图，SRAM 在那里不是 XN。

⚙️ **链接时会多一条 `LOAD segment with RWX permissions`** —— `.RamFunc` 进了 `.data`，
那个段就同时可写可执行。这是要的效果，已在 `$TEST/tools/build_image.py`
的 `KNOWN_WARNINGS` 里按原文匹配放行。

## 断在哪会怎样

| 断点 | 板子的状态 | 怎么救 |
|---|---|---|
| 传输 / 校验 / 验签 | 一个字节没写，bootloader 照常 | 重发 |
| 擦完，写完之前 | 起不来，**所有权还在**（根区在扇区 15） | ST-Link 重烧 bootloader |
| 写完 | 正常重启进新 bootloader | —— |

⚠️ **扇区 15 不受影响** —— `STM32_Programmer_CLI -w <elf>` 只擦 ELF 占的那些扇区，
所以 ST-Link 救砖不会带走 metadata、校准值和根区。

## 根区的回收不在这里

根区写满时由扇区 15 的回收压缩，见 [扇区 15 设计说明](SECTOR-15.md)。决策 72 之前挂在 `flashboot` 上的 `owner_slot_compact()` 随之移走。

## 镜像尺寸

预算是整个扇区 0（决策 72），构建时的尺寸门禁（`ENG-01`）见 [BOOTLOADER-PROJECT-LAYOUT.md](../../build/BOOTLOADER-PROJECT-LAYOUT.md)。
