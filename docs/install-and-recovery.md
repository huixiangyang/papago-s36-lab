# 构建、安装和恢复

这份说明以已经核对的 2020 海思固件为前提。仓库不提供通用自动刷机程序。先读 [固件入口](firmware-and-history.md)：原厂 bootapp 尚未安装钩子时，SD 扩展不会自行执行。

## 在电脑准备

需要 Python 3.10+；静态分析依赖在 `requirements-analysis.txt`。构建 ARM 辅助程序需要 Zig 0.14.1、make 和解压后的 Dropbear 2026.94 源码。上游地址与已知哈希见 `upstream.json`，下载物放 `downloads/`，私有配置放 `private/`，产物放 `build/`，均已忽略。

```sh
mkdir -p downloads private
chmod 700 private
# 下载并解压上游工具后，提供实际的绝对路径。
sh tools/build_device.sh /absolute/path/to/zig \
  downloads/dropbear-2026.94 build/device
```

构建脚本复制源码到新目录，并放入本次使用的 Dropbear 选项，关闭密码认证。构建输出不必与历史二进制逐字节一致；组装器会把此次辅助程序的 SHA-256 写入启动器。**main_app 的固定指纹与补丁地址不会更改。**

从上游取得并核对 BusyBox ARMv7 静态二进制。创建专用维护密钥，私钥留在电脑。将 `examples/wifi-import.conf.example` 复制到 `private/wifi-import.conf` 并填写自己的 WPA 配置，处理 SSID、密码中的引号与反斜线转义。首次导入成功后脚本将配置移入设备内部 `/etc/s36` 并移除卡上副本；这不是对闪存残留的安全擦除。

```sh
python3 tools/assemble_card.py \
  --busybox downloads/busybox-armv7l \
  --dropbear build/device/bin/dropbearmulti \
  --public-key ~/.ssh/papago_s36.pub \
  --wifi-config private/wifi-import.conf \
  --lan-cidr 192.168.1.0/24 \
  --archive-client 192.168.1.20 \
  --output build/s36-card
```

`--archive-client` 为客户端电脑的固定或 DHCP 保留地址。当前组装器只支持私有 IPv4 /24 网段；不要照搬示例地址。已有内部 Wi-Fi 配置时可省略 `--wifi-config`。

原片传输无需启用主码流实验。如需研究，另加 `--mainstream-binary build/device/bin/s36-mainstream-memory --enable-mainstream`；启动时重建视频通道可能短暂影响录像。组装器仅生成本地目录与清单，拒绝覆盖已有产物，不操作设备。

## 通过电脑 USB 存储模式安装

1. 暂停电脑上的文件传输和预览，正常结束拍摄。连接数据线，确认系统识别的外置介质确为记录仪的卡，核对容量、分区和卷内容，不使用写死的磁盘编号。
2. 保留需要的录像并备份原扩展。若 FAT 有异常，卸载电脑上的卷后先修复文件系统；重新挂载后才复制文件。
3. 把产物 `card-root/s36-lab` 安装到卡根目录。同一扩展目录先完整备份，再替换，避免留下过期的 enable 标记或旧启动器。清单 `manifest.json` 留在电脑，用于逐文件核对。
4. 刷盘，卸载后重新挂载，逐一比较所有文件的字节数和 SHA-256。首次供电后 `wifi-import.conf` 被移除属于预期，不能用启动前清单直接判为损坏。
5. 再检查文件系统并安全推出。保留存储卡，改接充电器正常开机，**不按 OK**。核对局域网 DHCP、SSH、8081 清单、新录像生成与实际转存。

不要把安装等同于远程复制：曾经在设备 Linux 侧停止进程、卸载、修复、写入后，启动文件仍再次损坏。Linux 与 LiteOS 共享硬件，仅 Linux 卸载不证明所有写卡路径停止。本次最终采用电脑 USB 存储模式，正常运行的扩展不再向 SD 写诊断。

## 恢复与排查

- 启动脚本、二进制缺失或哈希不一致：回到 USB 存储模式，用清单检查并恢复整个扩展目录。
- 找不到局域网设备：查看路由器租约；首次关联或 DHCP 失败会尝试恢复原厂热点。不要让维护电脑盲目切换 Wi-Fi 导致远程控制断网。
- 8081 不可用而 SSH 正常：检查客户端电脑允许地址、`/dev/s36/lease.ip`、卡挂载与 `/dev/s36/archive.log`；检查是否发生过 USB 导出导致本轮归档守卫锁定。
- 卡被格式化：扩展已消失，需重新安装；内部固件钩子和私有配置并不因此恢复出厂。
- 禁用某个扩展：在 USB 维护时移除对应 enable 标记并正常重启。移除根 enable 会让 bootapp 跳过扩展。
- 原厂应用分区恢复候选仅离线生成，尚未实测刷回。没有免拆机救砖能力保证。

归档 HTTP 和原厂控制协议没有传输加密。只在受信局域网网络使用；SSH 私钥、Wi-Fi 配置和组装目录不上传公开仓库。
