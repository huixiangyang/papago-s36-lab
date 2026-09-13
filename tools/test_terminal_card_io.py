#!/usr/bin/env python3
"""在隔离目录中验证真实写卡守卫，不操作设备、系统挂载或 USB 接口。"""
import json
from pathlib import Path
import shlex
import subprocess
import tempfile


def main():
    base = Path(__file__).resolve().parent.parent / "device"
    source = (base / "card-root/s36-lab/card-io.sh").read_text()
    results = {}
    with tempfile.TemporaryDirectory(prefix="s36-card-guard-") as directory:
        root = Path(directory)
        runtime, card = root / "ram", root / "card"
        runtime.mkdir()
        card.mkdir()
        lun, mounts = root / "lun", root / "mounts"
        script = root / "card-io.sh"
        # 仅重定向外部输入路径，保持被测 shell 函数原样执行。
        script.write_text(source.replace(
            "/sys/devices/platform/soc/100e0000.hidwc3_0/gadget/lun0/file", str(lun)
        ).replace("/proc/mounts", str(mounts)))
        command = (
            f"B=/usr/bin/env; R={shlex.quote(str(runtime))}; "
            f"D={shlex.quote(str(card))}; . {shlex.quote(str(script))}; s36_card_write_allowed"
        )

        def check(name, allowed):
            result = subprocess.run(["/bin/sh", "-c", command], capture_output=True, text=True)
            assert (result.returncode == 0) == allowed, (name, result.stderr)
            results[name] = "allowed" if allowed else "blocked"

        mounts.write_text("/dev/mmcblk0p1 /app/sd vfat rw,noexec,noatime 0 0\n")
        check("normal_recording_without_usb_gadget", True)
        lun.write_text("")
        check("empty_usb_lun", True)
        lun.write_text("/dev/mmcblk0p1\n")
        check("card_exported_to_computer", False)
        lun.write_text("")
        check("usb_write_block_remains_until_reboot", False)
        (runtime / "usb-storage-seen").unlink()
        mounts.write_text("/dev/mmcblk0p1 /app/sd vfat ro,noexec 0 0\n")
        check("read_only_card", False)
        mounts.write_text("")
        check("unmounted_card_directory", False)
        mounts.write_text("/dev/root /app/sd jffs2 rw 0 0\n")
        check("unexpected_filesystem", False)
        mounts.write_text("/dev/mmcblk0p1 /app/sd vfat rw,noexec 0 0\n")
        card.rmdir()
        check("missing_extension_directory", False)
    result = {"environment": "isolated shell fixtures; not a physical USB cycle", "checks": results}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
