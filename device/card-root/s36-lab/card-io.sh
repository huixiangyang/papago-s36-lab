#!/bin/sh
# 原厂将存储卡导出给电脑时，扩展禁止写卡；本次启动内一旦进入 USB 模式就保持禁写。
# B、D、R 由已验证的启动脚本提供，分别指向工具、卡目录和内存目录。
s36_card_write_allowed() {
    s36_lun=/sys/devices/platform/soc/100e0000.hidwc3_0/gadget/lun0/file
    if [ -r "$s36_lun" ]; then
        s36_backing=$($B cat "$s36_lun") || return 1
        if [ -n "$s36_backing" ]; then
            : >"$R/usb-storage-seen"
            return 1
        fi
    fi
    [ ! -e "$R/usb-storage-seen" ] || return 1
    [ -d "$D" ] || return 1
    # 不在卸载后遗留的空目录、只读挂载或其他文件系统上创建诊断文件。
    $B awk '$2 == "/app/sd" && $3 == "vfat" && ("," $4 ",") ~ /,rw,/ {found=1} END {exit !found}' /proc/mounts
}
