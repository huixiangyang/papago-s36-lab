#!/bin/sh
# 离线编译：上游源码与 Zig 由调用者明确提供，不下载或安装到设备。
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
zig=${1:?用法：build_device.sh ZIG绝对路径 DROPBEAR源码目录 新输出目录}
source=${2:?需要 Dropbear 2026.94 源码目录}
output=${3:?需要全新本地输出目录}
case "$zig" in /*) ;; *) echo 'Zig 需要绝对路径' >&2; exit 2;; esac
[ "$("$zig" version)" = 0.14.1 ] || { echo '需要 Zig 0.14.1' >&2; exit 2; }
[ -f "$source/configure" ] && [ -f "$source/src/default_options.h" ] || exit 2
grep -q '"2026.94"' "$source/src/sysoptions.h" || { echo '需要 Dropbear 2026.94' >&2; exit 2; }
[ ! -e "$output" ] || { echo '输出目录已存在' >&2; exit 2; }
mkdir -p "$output/bin" "$output/dropbear"
output=$(CDPATH= cd -- "$output" && pwd)
cp -R "$source/." "$output/dropbear/"
cp "$root/device/dropbear-localoptions.h" "$output/dropbear/localoptions.h"
cd "$output/dropbear"
export CC="$zig cc -target arm-linux-musleabihf -mcpu=cortex_a7"
export AR="$zig ar"
export RANLIB="$zig ranlib"
export CFLAGS='-Os'
export LDFLAGS='-Wl,-s'
./configure --host=arm-linux-musleabihf --enable-static --disable-zlib --disable-lastlog --disable-utmp --disable-utmpx --disable-wtmp --disable-wtmpx
make clean
make -j4 PROGRAMS='dropbear dropbearkey' MULTI=1
cp dropbearmulti "$output/bin/dropbearmulti"
"$zig" cc -target arm-linux-musleabihf -mcpu=cortex_a7 -Os -static -s \
    "$root/device/mainstream-memory-patch.c" -o "$output/bin/s36-mainstream-memory"
echo '编译完成；辅助程序指纹将在组装时写入启动脚本。'
