#!/bin/sh
# 通过已认证的 SSH 运行，不接入公开 HTTP 接口。
set -eu
B=/dev/s36/busybox
R=/dev/s36
case "${1:-status}" in
status)
    $B id
    $B uname -a
    $B uptime
    $B free
    $B df -h / /app /app/sd /dev
    $B netstat -lnt
    # 进程参数可能含联网回调凭据，只列出进程号与程序名。
    $B ps -o pid,comm
    ;;
telnet-start)
    # Telnet 仅监听本机回环地址，明文协议不开放到局域网网络。
    # 原厂启动时回环接口可能未启用，先恢复本地地址再监听。
    $B ifconfig lo 127.0.0.1 up
    if [ -f "$R/terminal/telnet.pid" ]; then
        kill -0 "$($B cat "$R/terminal/telnet.pid")" 2>/dev/null && exit 0
    fi
    # 脱离 SSH 的控制终端，避免客户端退出时被 SIGHUP 一并终止。
    "$R/busybox" nohup "$R/busybox" setsid "$R/busybox" telnetd -F -b 127.0.0.1 -p 2323 -l /bin/sh </dev/null >"$R/terminal/telnet.log" 2>&1 &
    echo "$!" >"$R/terminal/telnet.pid"
    $B sleep 1
    kill -0 "$($B cat "$R/terminal/telnet.pid")" 2>/dev/null
    ;;
telnet-stop)
    if [ -f "$R/terminal/telnet.pid" ]; then
        kill "$($B cat "$R/terminal/telnet.pid")" 2>/dev/null || true
        $B rm -f "$R/terminal/telnet.pid"
    fi
    ;;
*) echo '用法：control.sh status|telnet-start|telnet-stop' >&2; exit 2 ;;
esac
