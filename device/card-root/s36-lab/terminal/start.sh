#!/bin/sh
# 密钥维护入口与录像进程独立；仅在局域网网络取址后开放 SSH。
set -u
B=/dev/s36/busybox
D=/app/sd/s36-lab/terminal
R=/dev/s36
T=$R/terminal
P=/etc/s36/ssh
A=/root/.ssh
. "$R/card-io.sh"
umask 077
report() {
    {
        echo S36_TERMINAL_V3
        echo "phase=$1"
        $B date -u
        $B netstat -lnt 2>/dev/null
        $B free
        # 只记录认证所需的元数据，绝不输出密码散列或私钥。
        $B stat -c '%n uid=%u gid=%g mode=%a' / /etc /etc/s36 "$P" /root "$A" "$A/authorized_keys" 2>/dev/null
        $B awk -F: '$1 == "root" {print "account=" $1 " uid=" $3 " gid=" $4 " home=" $6 " shell=" $7}' /etc/passwd
        [ ! -f "$A/authorized_keys" ] || $B sha256sum "$A/authorized_keys"
        for log in "$R/terminal.log" "$T/keygen.log" "$T/ssh.log"; do
            [ ! -f "$log" ] || $B tail -n 15 "$log"
        done
    } >"$R/terminal-status.txt"
    # 诊断只留在 RAM；SSH 登录不能触发写卡，与原厂录像争用 FAT。
}
trap 'report "finished:$?"' 0
[ -f "$D/enable" ] || exit 0
$B mkdir "$R/terminal-started" 2>/dev/null || exit 0
$B mkdir -p "$T" || exit 1
$B cp "$D/dropbearmulti" "$T/dropbearmulti" || exit 1
echo 'da15041b2a7085070ab490ac38f9874b16eb352a93d34ad9c2442c5e48a0029f  /dev/s36/terminal/dropbearmulti' | $B sha256sum -c - >/dev/null || exit 1
$B chmod 700 "$T/dropbearmulti"
$B ln -s dropbearmulti "$T/dropbear"
$B ln -s dropbearmulti "$T/dropbearkey"

# 私有主机密钥留在内部文件系统；卡上只存放客户端公钥。
[ ! -L /etc/s36 ] && [ ! -L "$P" ] && [ ! -L /root ] && [ ! -L "$A" ] || exit 1
$B mkdir -p "$P" "$A" || exit 1
# 原厂 /etc 和 /root 属于 UID 999。公钥放回 root 家目录，
# 仅修正家目录及私有子目录，避免改变整个原厂 /etc 的所有权。
$B chown 0:0 /root "$A" "$P" || exit 1
$B chmod 700 /root "$A" "$P" || exit 1
[ -s "$D/authorized_keys" ] || exit 1
$B cp "$D/authorized_keys" "$A/authorized_keys.new" || exit 1
$B chown 0:0 "$A/authorized_keys.new" || exit 1
$B chmod 600 "$A/authorized_keys.new" || exit 1
$B mv "$A/authorized_keys.new" "$A/authorized_keys" || exit 1
$B rm -f "$P/authorized_keys"
report waiting_for_network

waited=0
while [ "$waited" -lt 180 ]; do
    [ -s "$R/lease.ip" ] && break
    $B sleep 1
    waited=$((waited + 1))
done
[ -s "$R/lease.ip" ] || exit 1
if [ ! -s "$P/host_ed25519" ]; then
    report creating_host_key
    "$T/dropbearkey" -t ed25519 -f "$P/host_ed25519.new" >"$T/keygen.log" 2>&1 || exit 1
    $B chmod 600 "$P/host_ed25519.new"
    $B mv "$P/host_ed25519.new" "$P/host_ed25519" || exit 1
    $B sync
fi
"$T/dropbearkey" -y -f "$P/host_ed25519" >"$T/host-public.txt" 2>&1


# devpts 只挂载在内存；没有伪终端时仍保留 SSH 单命令诊断能力。
$B mkdir -p /dev/pts
$B grep -q ' /dev/pts devpts ' /proc/mounts || $B mount -t devpts devpts /dev/pts -o mode=620,ptmxmode=666
[ -c /dev/ptmx ] || $B mknod /dev/ptmx c 5 2
$B cp "$D/control.sh" "$T/control.sh"
$B chmod 700 "$T/control.sh"

# 地址变化时重新绑定，绝不监听默认热点或所有接口。
last_ip=
server_pid=
failures=0
log_signature=
while :; do
    # 卸载卡是维护过程，不等于禁用扩展；保留守护进程等待重新挂载。
    if $B awk '$2 == "/app/sd" && $3 == "vfat" {found=1} END {exit !found}' /proc/mounts && [ ! -f "$D/enable" ]; then
        break
    fi
    current_ip=$($B cat "$R/lease.ip" 2>/dev/null || true)
    echo "$current_ip" | $B grep -Eq '^192\.168\.1\.[0-9]{1,3}$' || current_ip=
    if [ -n "$server_pid" ] && ! kill -0 "$server_pid" 2>/dev/null; then
        failures=$((failures + 1))
        [ "$failures" -lt 3 ] || exit 1
        last_ip=
        server_pid=
    fi
    if [ "$current_ip" != "$last_ip" ]; then
        [ -z "$server_pid" ] || kill "$server_pid" 2>/dev/null || true
        server_pid=
        if [ -n "$current_ip" ]; then
            "$T/dropbear" -F -E -D "$A" -r "$P/host_ed25519" -p "$current_ip:2222" -P "$T/ssh.pid" -I 1800 -K 30 -T 3 >>"$T/ssh.log" 2>&1 &
            server_pid=$!
        fi
        last_ip=$current_ip
        $B sleep 1
        report "ssh_started:$current_ip"
    fi
    # 登录事件发生后才刷新内存诊断，可通过 SSH 读取认证失败原因。
    current_signature=$($B cksum "$T/ssh.log" 2>/dev/null || true)
    if [ "$current_signature" != "$log_signature" ]; then
        report "ssh_running:$current_ip"
        log_signature=$current_signature
    fi
    $B sleep 5
done
[ -z "$server_pid" ] || kill "$server_pid" 2>/dev/null || true
