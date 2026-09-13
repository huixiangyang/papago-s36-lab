#!/bin/sh
# 已验证的启动入口：仅在卡上启用扩展时运行；辅助程序复制到 RAM 以适应 noexec 卡挂载。
set -u
B=/bin/busybox
D=/app/sd/s36-lab
R=/dev/s36
[ -f "$D/enable" ] || exit 0
umask 077
$B mkdir -p "$R" || exit 1
$B mkdir "$R/started" 2>/dev/null || exit 0

# 局域网网络密钥只导入设备内部私有目录，避免长期留在原厂 HTTP 可浏览的卡目录。
if [ -f "$D/wifi-import.conf" ]; then
    [ ! -L /etc/s36 ] || exit 1
    $B mkdir -p /etc/s36 || exit 1
    $B chmod 700 /etc/s36
    $B cp "$D/wifi-import.conf" /etc/s36/wpa_supplicant.conf.new || exit 1
    $B chmod 600 /etc/s36/wpa_supplicant.conf.new
    $B cmp "$D/wifi-import.conf" /etc/s36/wpa_supplicant.conf.new || exit 1
    $B mv /etc/s36/wpa_supplicant.conf.new /etc/s36/wpa_supplicant.conf || exit 1
    $B sync
    $B rm -f "$D/wifi-import.conf" "$D/._wifi-import.conf"
    $B sync
fi

for name in station.sh dhcp.sh card-io.sh; do
    $B cp "$D/$name" "$R/$name" || exit 1
done
$B cp "$D/busybox-armv7l" "$R/busybox" || exit 1
echo 'cd04052b8b6885f75f50b2a280bfcbf849d8710c8e61d369c533acf307eda064  /dev/s36/busybox' | $B sha256sum -c - >/dev/null || exit 1
$B chmod 700 "$R/busybox" "$R/dhcp.sh"
/bin/sh "$R/station.sh" >"$R/station.log" 2>&1 &

# 独立启动维护服务；失败时不影响局域网联网与原厂录像。
if [ -f "$D/terminal/enable" ] && [ -f "$D/terminal/start.sh" ]; then
    # 长期运行的脚本不能持有卡上文件，USB 存储切换需要释放文件系统。
    if $B cp "$D/terminal/start.sh" "$R/terminal-start.sh"; then
        /bin/sh "$R/terminal-start.sh" >"$R/terminal.log" 2>&1 &
    fi
fi

# 主码流独立初始化；脚本从内存执行，不长期占用卡文件。
if [ -f "$D/mainstream/enable" ] && [ -f "$D/mainstream/start.sh" ]; then
    if $B cp "$D/mainstream/start.sh" "$R/mainstream-start.sh"; then
        /bin/sh "$R/mainstream-start.sh" >"$R/mainstream.log" 2>&1 &
    fi
fi

# 录像清单和下载独立于原厂 thttpd；同样从 RAM 启动，禁止影响正常录像。
if [ -f "$D/archive/enable" ] && [ -f "$D/archive/start.sh" ]; then
    if $B cp "$D/archive/start.sh" "$R/archive-start.sh"; then
        /bin/sh "$R/archive-start.sh" >"$R/archive.log" 2>&1 &
    fi
fi
