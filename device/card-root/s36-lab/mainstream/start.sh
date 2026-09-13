#!/bin/sh
# 固定固件的主码流注册修正只作用于 RAM；原厂程序文件保持原样。
set -u
B=/dev/s36/busybox
R=/dev/s36
D=/app/sd/s36-lab/mainstream
[ -f "$D/enable" ] || exit 0
$B mkdir "$R/mainstream-started" 2>/dev/null || exit 0
$B cp "$D/s36-mainstream-memory" "$R/s36-mainstream-memory" || exit 1
$B chmod 700 "$R/s36-mainstream-memory"
echo '1082a224e1255e84717bda261ed1278aefb6d510cb367df3512773d82a77ebe2  /dev/s36/s36-mainstream-memory' | $B sha256sum -c - || exit 1
echo 'fc3c9deac86625fedb208375cd6d927d8df42bf92e4fcf2115a27cee276022df  /app/bin/main_app' | $B sha256sum -c - || exit 1
waited=0
while [ ! -s "$R/lease.ip" ] && [ "$waited" -lt 180 ]; do
 $B sleep 1
 waited=$((waited + 1))
done
[ -s "$R/lease.ip" ] || exit 1
ip=$($B cat "$R/lease.ip")
echo "$ip" | $B grep -Eq '^192\.168\.1\.[0-9]{1,3}$' || exit 1
# 原厂未启用 lo，自身访问局域网地址也需要本地回环路由。
$B ifconfig lo 127.0.0.1 up || exit 1
pid=$($B pidof main_app)
case "$pid" in ''|*[!0-9]*) exit 1;; esac
read_settings() { $B wget -T 8 --header 'Connection: close' -q -O - "http://$ip/?custom=1&msg_id=6"; }
resolution() { $B sed -n 's/.*"resolution"[[:space:]]*:[[:space:]]*"\([A-Za-z0-9]*\)".*/\1/p'; }
settings=$(read_settings) || exit 1
original=$(echo "$settings" | resolution)
# 仅对已实测的两档执行重建；未知设置保留原状，拒绝猜测设备命令。
case "$original" in
 4KP30FPS) alternate=1080P30FPS;;
 1080P30FPS) alternate=4KP30FPS;;
 *) echo unsupported_resolution; exit 1;;
esac
"$R/s36-mainstream-memory" "$pid" enable || exit 1
changed=0
finished=0
set_resolution() {
 reply=$($B wget -T 8 --header 'Connection: close' -q -O - "http://$ip/?custom=1&msg_id=8&param1=resolution&param2=$1") || return 1
 echo "$reply" | $B grep -Eq '"rval"[[:space:]]*:[[:space:]]*0([,}[:space:]])'
}
cleanup() {
 if [ "$finished" != 1 ]; then
  "$R/s36-mainstream-memory" "$pid" restore || true
  [ "$changed" != 1 ] || set_resolution "$original" || true
  echo MAINSTREAM_FAILED
 fi
}
trap cleanup 0
# 先记录恢复责任，覆盖请求已成功但应答丢失的情况。
changed=1
set_resolution "$alternate" || exit 1
$B sleep 3
set_resolution "$original" || exit 1
$B sleep 3
actual=$(read_settings | resolution)
[ "$actual" = "$original" ] || exit 1
finished=1
echo "MAINSTREAM_READY resolution=$actual pid=$pid"
