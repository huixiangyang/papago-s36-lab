# 硬件与资源分区

核验对象：2020 年海思版 PAPAGO S36 4K，固件 `S36 4K V1.15_Build20200629`，Hi3559V200。设备标签供电为 5 V / 1.5 A。以下结果来自这台实机，不外推到所有 S36。

Linux 为 4.9.37 ARMv7。通过 `/dev/virt-tty/a7` 取得的真实终端响应为 Huawei LiteOS V200R002C00B063 / 3.0.7，构建日期 2020-06-29。媒体启动日志包含 IMX317 初始化信息。

Linux 的启动参数是 `mem=96M`，`MemTotal=90656 KiB`，约 88.53 MiB；CPU 的 possible、present、online 均只列 CPU 0。LiteOS 列出 26 个任务，包含 ISP、视频、音频与 IPC；其堆统计约 21 MiB，已用 3 MiB、空闲 18 MiB。结合芯片架构与 IPC 状态，符合两核分别运行 Linux、LiteOS 的分工。

| 物理地址范围（首尾包含） | MiB | 含义 |
| --- | ---: | --- |
| `0x80000000–0x81ffffff` | 32 | LiteOS 运行数据、IPC 等，子区未完全细分 |
| `0x82000000–0x87ffffff` | 96 | Linux System RAM |
| `0x88000000–0x984fffff` | 261 | 原厂模块配置的 map_mmz 映射区 |
| `0x98500000–0x9f7fffff` | 115 | 运行中的通用媒体内存池 |
| `0x9f800000–0x9fffffff` | 8 | HIGO 显示池 |
| 合计 | **512** | 固件布局与 512 MiB 一致 |

Linux 的内存统计不包含 LiteOS 与专用媒体缓冲，因此不能据此判断虚标。这里没有对全部物理内存做容量或地址别名压测，也没有测量 CPU 实际频率。

查询 LiteOS 时使用一个读写文件描述符打开虚拟终端，以回车 `\r` 提交命令并及时关闭。已成功的查询为 `uname -a`、`free -m`、`task`；更广泛的命令集合尚未验证，不应当作普通 Linux shell 使用。
