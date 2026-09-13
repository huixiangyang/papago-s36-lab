#!/bin/sh
# 独立单线程 HTTP 服务避开原厂目录服务的子进程泄漏；仅允许打包时指定的电脑读取。
set -eu
B=/dev/s36/busybox
D=/app/sd/s36-lab/archive
R=/dev/s36
A=/dev/s36-archive
. "$R/card-io.sh"
umask 077
[ -f "$D/enable" ] || exit 0
$B mkdir "$R/archive-started" 2>/dev/null || exit 0
$B mkdir -p "$A/www/cgi-bin"
$B cp "$B" "$A/busybox"
$B cp "$D/catalog.cgi" "$A/www/cgi-bin/catalog.cgi"
$B chmod 755 "$A" "$A/www" "$A/www/cgi-bin" "$A/busybox" "$A/www/cgi-bin/catalog.cgi"
$B ln -s /app/sd/PAPAGO/VIDEO "$A/www/VIDEO"
$B ln -s /app/sd/PAPAGO/EMERGENCY "$A/www/EMERGENCY"
printf 'A:192.168.1.10\nD:*\n' >"$A/httpd.conf"
$B chmod 644 "$A/httpd.conf"
server_pid=
last_ip=
stop_server() {
    [ -z "$server_pid" ] || { kill "$server_pid" 2>/dev/null || true; wait "$server_pid" 2>/dev/null || true; }
    server_pid=
}
trap 'stop_server' EXIT
trap 'exit 0' INT TERM
while :; do
    # 卸载卡是维护过程，不等于禁用扩展；保留守护进程等待重新挂载。
    if $B awk '$2 == "/app/sd" && $3 == "vfat" {found=1} END {exit !found}' /proc/mounts && [ ! -f "$D/enable" ]; then
        break
    fi
    current_ip=$($B cat "$R/lease.ip" 2>/dev/null || true)
    echo "$current_ip" | $B grep -Eq '^192\.168\.1\.[0-9]{1,3}$' || current_ip=
    s36_card_write_allowed || current_ip=
    if [ -n "$server_pid" ] && ! kill -0 "$server_pid" 2>/dev/null; then
        wait "$server_pid" 2>/dev/null || true
        server_pid=
        last_ip=
    fi
    if [ "$current_ip" != "$last_ip" ]; then
        stop_server
        if [ -n "$current_ip" ]; then
            # 以无特权用户提供静态录像与固定 CGI，文件写入接口不存在。
            "$A/busybox" httpd -f -p "$current_ip:8081" -u 65534:65534 -h "$A/www" -c "$A/httpd.conf" &
            server_pid=$!
            echo "ARCHIVE_STARTED address=$current_ip:8081 pid=$server_pid"
        fi
        last_ip=$current_ip
    fi
    $B sleep 5
done
