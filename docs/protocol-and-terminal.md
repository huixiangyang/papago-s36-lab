# 终端、协议和主码流

## 维护接口

SSH 绑定局域网地址的 2222 端口，root 公钥认证；Dropbear 编译时关闭密码与 PAM 认证。客户端私钥只放维护电脑，卡上仅放客户端公钥；设备主机私钥在 `/etc/s36/ssh`，不在 SD 可下载目录。首次连接核对主机指纹。

```sh
ssh -p 2222 -i ~/.ssh/papago_s36 root@192.168.1.50
# 以下命令在记录仪的 SSH 会话内执行。
/bin/sh /dev/s36/terminal/control.sh telnet-start
/dev/s36/busybox telnet 127.0.0.1 2323
# 退出 Telnet 后关闭。
/bin/sh /dev/s36/terminal/control.sh telnet-stop
```

Telnet 默认不启动，仅监听设备回环。网络诊断在 `/dev/s36/status.txt`，终端诊断在 `/dev/s36/terminal-status.txt`；这些文件重启即失，不应定期写回 SD。

## 设备 HTTP 与视频

| 接口 | 用途 |
| --- | --- |
| `GET /?custom=1&msg_id=1`，端口 80 | 身份；核对 model 和 sn |
| `GET /?custom=1&msg_id=6`，端口 80 | 读取分辨率、麦克风等配置 |
| `GET /?custom=1&msg_id=19`，端口 80 | 存储卡可用空间 |
| `GET /cgi-bin/catalog.cgi`，端口 8081 | 独立 JSON 录像清单 |
| `GET /VIDEO/<name>` / `/EMERGENCY/<name>`，端口 8081 | 只读 MP4 下载，支持 Range |
| `rtsp://设备地址:554/livestream/1` | H.264 1024×576 取景副流 |
| `rtsp://设备地址:554/livestream/0` | 补丁启用后可用的 HEVC 4K 主流 |

原厂目录服务出现过僵尸子进程累积、空响应和 503。独立服务在 RAM 运行，UID/GID 65534，只有固定录像目录；不提供上传、删除或命令执行接口。服务只允许打包时指定的客户端电脑。原厂接口本身没有因此获得认证或加密，应放在受信局域网，不映射公网端口。

麦克风底层事件 `0x1170001b` 实测为**切换**操作，不能把重复请求当成幂等的“设为开”。要先读状态，必要时操作一次，再读回验证。

## 主码流补丁

函数 `PDT_STATEMNG_AddRtspStreams` 中虚拟地址 `0x3c16c`（文件偏移 `0x2c16c`）的一条指令从 `0x1a00002c` 改为 `0x8a00002c`，允许 type=0/1 注册，其他类型继续跳过。

启动脚本先核对固定 main_app 指纹，C 程序再核对目标进程和相邻指令。通过 ptrace 修改 RAM，读回确认并恢复进程运行；磁盘上的 main_app 没有修改。分辨率在已实测的 4KP30FPS 与 1080P30FPS 两档之间短暂切换，随后恢复，触发视频通道重建。

此操作可能短暂影响正在拍摄的分段，只作为可选研究能力。原片文件传输不需要启用它。浏览器预览和其他消费者应共用 go2rtc 的一条上游，额外直连播放器可能争抢原厂 RTSP 资源。
