#!/bin/sh
# udhcpc 回调：只操作记录仪 wlan0；租约续期同样更新地址，不写 DNS 或其他系统文件。
set -u
B=${S36_TEST_BUSYBOX:-/bin/busybox}
R=${S36_TEST_RUNTIME:-/dev/s36}
[ "${interface:-}" = wlan0 ] || exit 1
valid_ip() {
    case "$1" in ''|*[!0-9.]*) return 1;; esac
}
case "${1:-}" in
    deconfig)
        "$B" ifconfig wlan0 0.0.0.0
        "$B" rm -f "$R/lease.ip"
        ;;
    bound|renew)
        valid_ip "${ip:-}" && valid_ip "${subnet:-}" || exit 1
        "$B" ifconfig wlan0 "$ip" netmask "$subnet" up || exit 1
        # DHCP 提供的参数按数据处理，绝不作为 shell 代码执行。
        for gw in ${router:-}; do
            valid_ip "$gw" || continue
            "$B" ip route replace default via "$gw" dev wlan0 || exit 1
            break
        done
        echo "$ip" >"$R/lease.ip.new"
        "$B" mv "$R/lease.ip.new" "$R/lease.ip"
        ;;
esac
