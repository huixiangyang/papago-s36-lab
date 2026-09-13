#!/bin/sh
# 在原厂程序启动后接管无线接口；首次联网失败时恢复原厂热点，不修改原厂程序。
set -u
B=/bin/busybox
D=/app/sd/s36-lab
R=/dev/s36
. "$R/card-io.sh"
umask 077
phase=starting
wpa_pid=
dhcp_pid=

publish() {
    phase=$1
    {
        echo S36_STATION_V1
        echo "phase=$phase"
        $B date -u
        $B sha256sum /app/bootapp /app/bin/main_app
        echo '--- WPA STATUS ---'
        /sbin/wpa_cli -p "$R/wpa_ctrl" -i wlan0 status 2>/dev/null || true
        echo '--- ADDRESSES ---'
        $B ifconfig wlan0 2>&1
        $B route -n
        echo '--- LISTENERS ---'
        $B netstat -lnt 2>&1
        echo '--- WPA LOG ---'
        $B tail -n 35 "$R/wpa.log" 2>/dev/null || true
        echo '--- DHCP LOG ---'
        $B tail -n 25 "$R/dhcp.log" 2>/dev/null || true
    } >"$R/status.txt"
    # 诊断只留在 RAM，避免与原厂录像同时修改存储卡的 FAT。
}

restore_ap() {
    cause=$1
    [ -z "$dhcp_pid" ] || kill "$dhcp_pid" 2>/dev/null || true
    [ -z "$wpa_pid" ] || kill "$wpa_pid" 2>/dev/null || true
    $B sleep 2
    $B ifconfig wlan0 0.0.0.0 down
    $B ifconfig wlan0 192.168.42.1 netmask 255.255.255.0 up
    # 沿用反汇编确认的原厂热点启动参数和现有配置。
    $B pidof hostapd >/dev/null || /app/bin/hostapd -e /app/bin/entropy.bin -B /dev/wifi/hostapd/hostapd.conf
    $B pidof udhcpd >/dev/null || /usr/sbin/udhcpd /app/udhcpd.conf
    publish "fallback_ap:$cause"
    exit 1
}

# 原厂热点配置创建完成后再切换，避免与开机时的网络初始化竞争。
waited=0
while [ "$waited" -lt 60 ]; do
    if [ -f /dev/wifi/hostapd/hostapd.conf ] && $B pidof hostapd >/dev/null; then
        break
    fi
    $B sleep 1
    waited=$((waited + 1))
done
if [ "$waited" -ge 60 ] || [ ! -s /etc/s36/wpa_supplicant.conf ]; then
    publish preflight_failed
    exit 1
fi
[ -x /sbin/wpa_supplicant ] && [ -x /sbin/wpa_cli ] || { publish client_missing; exit 1; }
"$R/busybox" --list | $B grep -qx udhcpc || { publish dhcp_client_unavailable; exit 1; }
$B sleep 5

# 先停止原厂 DHCP 服务，再加入局域网网络，防止它向局域网网络分配地址。
$B killall hostapd udhcpd 2>/dev/null || true
waited=0
while $B pidof hostapd udhcpd >/dev/null; do
    [ "$waited" -lt 10 ] || restore_ap ap_stop_failed
    $B sleep 1
    waited=$((waited + 1))
done
$B ifconfig wlan0 0.0.0.0 down
$B ifconfig wlan0 up
$B mkdir -p "$R/wpa_ctrl"
/sbin/wpa_supplicant -i wlan0 -D nl80211 -c /etc/s36/wpa_supplicant.conf >"$R/wpa.log" 2>&1 &
wpa_pid=$!
echo "$wpa_pid" >"$R/wpa.pid"
waited=0
while [ "$waited" -lt 90 ]; do
    kill -0 "$wpa_pid" 2>/dev/null || restore_ap supplicant_exited
    if /sbin/wpa_cli -p "$R/wpa_ctrl" -i wlan0 status 2>/dev/null | $B grep -qx 'wpa_state=COMPLETED'; then
        break
    fi
    $B sleep 1
    waited=$((waited + 1))
done
[ "$waited" -lt 90 ] || restore_ap association_timeout

"$R/busybox" udhcpc -f -i wlan0 -p "$R/dhcp.pid" -s "$R/dhcp.sh" -t 5 -T 3 -n >"$R/dhcp.log" 2>&1 &
dhcp_pid=$!
waited=0
while [ "$waited" -lt 30 ] && [ ! -s "$R/lease.ip" ]; do
    kill -0 "$dhcp_pid" 2>/dev/null || restore_ap dhcp_exited
    $B sleep 1
    waited=$((waited + 1))
done
[ -s "$R/lease.ip" ] || restore_ap dhcp_timeout
publish connected

# 成功后保留续租进程，地址可从路由器租约列表或维护终端读取。
last_ip=
while kill -0 "$wpa_pid" 2>/dev/null && kill -0 "$dhcp_pid" 2>/dev/null; do
    current_ip=$($B cat "$R/lease.ip" 2>/dev/null || true)
    if [ -n "$current_ip" ] && [ "$current_ip" != "$last_ip" ]; then
        publish connected
        last_ip=$current_ip
    fi
    $B sleep 10
done
restore_ap network_process_exited
