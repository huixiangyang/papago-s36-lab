#!/usr/bin/env python3
"""隔离验证组装流程：仅用模拟 ARM 文件，不连接设备或写物理介质。"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import assemble_card as target


def main():
    with tempfile.TemporaryDirectory(prefix="s36-package-test-") as temporary:
        root = Path(temporary)
        elf = bytearray(64)
        elf[:6] = b"\x7fELF\x01\x01"
        elf[18:20] = (40).to_bytes(2, "little")
        binary = root / "arm"
        binary.write_bytes(elf)
        key = root / "client.pub"
        kind = b"ssh-ed25519"
        payload = len(kind).to_bytes(4, "big") + kind + (32).to_bytes(4, "big") + bytes(range(32))
        key.write_text("ssh-ed25519 " + base64.b64encode(payload).decode() + " fixture-only\n")
        args = argparse.Namespace(lan_cidr="192.168.10.0/24", archive_client="192.168.10.20",
                                  output=root / "result", busybox=binary, dropbear=binary, public_key=key,
                                  mainstream_binary=binary, enable_mainstream=False, wifi_config=None)
        def rejects():
            try:
                target.assemble(args)
            except ValueError:
                return
            raise AssertionError("应拒绝不合格输入")
        rejects()  # 错误 BusyBox 指纹不能创建可安装目录。
        assert not args.output.exists()
        with patch.object(target, "BUSYBOX_SHA", hashlib.sha256(elf).hexdigest()):
            manifest = target.assemble(args)
            card = args.output / "card-root/s36-lab"
            assert not (card / "mainstream/enable").exists()
            assert not (card / "wifi-import.conf").exists()
            assert "A:192.168.10.20" in (card / "archive/start.sh").read_text()
            assert r"^192\.168\.10\." in (card / "terminal/start.sh").read_text()
            assert target.MAIN_APP_SHA in (card / "mainstream/start.sh").read_text()
            for name, entry in manifest["files"].items():
                data = (args.output / "card-root" / name).read_bytes()
                assert len(data) == entry["bytes"] and hashlib.sha256(data).hexdigest() == entry["sha256"]
            assert json.loads((args.output / "manifest.json").read_text()) == manifest
            rejects()  # 不覆盖已有包。
            args.output = root / "outside"
            args.archive_client = "192.168.11.20"
            rejects()
            assert not args.output.exists()
            args.archive_client = "192.168.10.20"
            key.write_text("-----BEGIN OPENSSH PRIVATE KEY-----\n")
            rejects()
            assert not args.output.exists()
    print("通过：版本指纹、地址隔离、默认关闭主码流、完整清单、不覆盖和私钥误用拒绝。")


if __name__ == "__main__":
    main()
