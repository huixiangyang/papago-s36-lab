# PAPAGO S36 Lab

2020 年海思版 PAPAGO S36 4K 的设备研究与扩展源码：无线客户端联网、维护终端、只读录像传输，以及固定固件的主码流实验。

适用对象为 **Hi3559V200 / S36 4K V1.15_Build20200629**。同名设备可能采用不同芯片，所有固件指纹与补丁地址只针对本次核验版本。

## 能力与边界

| 功能 | 结果 |
| --- | --- |
| 无线联网 | 从原厂热点切换为 Wi-Fi 客户端，以 DHCP 获取地址，首次连接失败尝试恢复热点 |
| 维护终端 | 公钥认证的 root SSH，端口 2222，支持 PTY；按需回环 Telnet，默认关闭 |
| 文件传输 | 只读 HTTP 8081，固定录像目录、JSON 清单及 Range 下载，限制指定客户端地址 |
| 视频通道 | 原厂 H.264 1024×576 副码流；可选 RAM 补丁使 HEVC 3840×2160 主码流可用 |
| 启动扩展 | bootapp 钩子触发 SD 脚本，辅助程序与运行诊断放在 RAM |

主码流长样本约 16 fps，**没有验证稳定 4K 30 fps**。原始 MP4 文件与实时预览通道应分别评估。main_app 文件保持原厂内容，主码流指令修正仅作用于 RAM。

## 文档

- [硬件与资源分区](docs/hardware.md)
- [固件入口与研究经过](docs/firmware-and-history.md)
- [构建、安装和恢复](docs/install-and-recovery.md)
- [终端、协议和主码流](docs/protocol-and-terminal.md)
- [验证范围](docs/validation.md)

## 目录

| 路径 | 内容 |
| --- | --- |
| `device/card-root/s36-lab/` | 设备扩展脚本模板 |
| `device/mainstream-memory-patch.c` | 固定版本的 ptrace 主码流补丁 |
| `device/dropbear-localoptions.h` | Dropbear 编译选项 |
| `tools/` | 离线固件分析、辅助程序构建、扩展组装与隔离检查 |
| `examples/` | 通用网络及 SSH 配置示例 |
| `upstream.json` | 上游来源、版本及校验指纹 |

打包器默认不启用主码流实验，按本地构建产物生成辅助程序哈希；原厂 main_app 指纹固定不变。没有安装 bootapp 钩子的原厂设备，单复制 SD 文件不会生效。

```sh
python3 tools/test_station_dhcp.py
python3 tools/test_terminal_card_io.py
python3 tools/test_assemble_card.py
```

这些检查仅操作隔离目录，不连接设备、不更改电脑网络、不写入物理存储卡。

自有代码及文档采用 [MIT 许可证](LICENSE)。第三方组件来源和许可证见 [NOTICE.md](NOTICE.md)。仓库不分发厂商固件、设备密钥或实际录像。
