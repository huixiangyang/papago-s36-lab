#!/usr/bin/env python3
"""在电脑本地组装 SD 扩展目录与哈希清单，不刷机、不挂载或写入物理介质。"""
import argparse
import base64
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import shutil
import tempfile

ROOT = Path(__file__).resolve().parent.parent
BUSYBOX_SHA = "cd04052b8b6885f75f50b2a280bfcbf849d8710c8e61d369c533acf307eda064"
DROPBEAR_SHA = "da15041b2a7085070ab490ac38f9874b16eb352a93d34ad9c2442c5e48a0029f"
MAINSTREAM_SHA = "1082a224e1255e84717bda261ed1278aefb6d510cb367df3512773d82a77ebe2"
MAIN_APP_SHA = "fc3c9deac86625fedb208375cd6d927d8df42bf92e4fcf2115a27cee276022df"


def arm_binary(path: Path) -> bytes:
    data = path.read_bytes()
    # ELF32、小端、ARM；避免把本机可执行文件装进记录仪。
    if len(data) < 52 or data[:6] != b"\x7fELF\x01\x01" or int.from_bytes(data[18:20], "little") != 40:
        raise ValueError(f"不是 ELF32 ARM 小端程序：{path.name}")
    return data


def checked_public_key(path: Path) -> bytes:
    data = path.read_bytes()
    lines = [line for line in data.decode().splitlines() if line.strip() and not line.startswith("#")]
    if not lines:
        raise ValueError("客户端公钥不能为空")
    for line in lines:
        fields = line.split()
        if len(fields) < 2 or fields[0] not in {"ssh-ed25519", "ssh-rsa", "ecdsa-sha2-nistp256"}:
            raise ValueError("需要 OpenSSH 公钥文件，不能使用私钥或占位内容")
        raw = base64.b64decode(fields[1], validate=True)
        length = int.from_bytes(raw[:4], "big")
        if raw[4:4 + length] != fields[0].encode() or len(raw) <= 4 + length:
            raise ValueError("公钥格式不完整")
    return data


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    if text.count(old) != 1:
        raise ValueError(f"模板版本不匹配：{path.name}")
    path.write_text(text.replace(old, new))


def assemble(args) -> dict:
    network = ipaddress.IPv4Network(args.lan_cidr)
    client = ipaddress.IPv4Address(args.archive_client)
    private_ranges = ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
    if network.prefixlen != 24 or not any(network.subnet_of(ipaddress.IPv4Network(cidr)) for cidr in private_ranges):
        raise ValueError("当前打包器只支持局域网私有 IPv4 /24 网段")
    if client not in network or client in {network.network_address, network.broadcast_address}:
        raise ValueError("客户端电脑必须是指定网段内的有效主机地址")
    output = args.output.resolve()
    if output.exists():
        raise ValueError("输出目录已存在，请使用新的本地目录")
    if output.parts[1:2] in [("Volumes",), ("dev",), ("app",)]:
        raise ValueError("只组装电脑本地目录；安装到存储卡需按文档另行操作")
    busybox = arm_binary(args.busybox)
    if hashlib.sha256(busybox).hexdigest() != BUSYBOX_SHA:
        raise ValueError("BusyBox 与已验证上游版本的 SHA-256 不匹配")
    dropbear = arm_binary(args.dropbear)
    public_key = checked_public_key(args.public_key)
    mainstream = arm_binary(args.mainstream_binary) if args.mainstream_binary else None
    if args.enable_mainstream and mainstream is None:
        raise ValueError("启用主码流需要提供对应 ARM 程序")
    wifi = args.wifi_config.read_bytes() if args.wifi_config else None
    if wifi is not None and (not wifi.strip() or any(marker in wifi for marker in [b"YOUR_WIFI", b"REPLACE_WITH"])):
        raise ValueError("Wi-Fi 配置尚未填写；不要把示例直接用于安装")

    output.parent.mkdir(parents=True, exist_ok=True)
    # 输入全部核验后才创建临时包；完整生成后原子更名，避免留下半成品。
    with tempfile.TemporaryDirectory(prefix=".s36-assemble-", dir=output.parent) as temporary:
        package = Path(temporary) / "package"
        card = package / "card-root/s36-lab"
        shutil.copytree(ROOT / "device/card-root/s36-lab", card)
        for relative, data in [("busybox-armv7l", busybox), ("terminal/dropbearmulti", dropbear),
                               ("terminal/authorized_keys", public_key)]:
            (card / relative).write_bytes(data)
        replace_once(card / "terminal/start.sh", DROPBEAR_SHA, hashlib.sha256(dropbear).hexdigest())
        if mainstream:
            (card / "mainstream/s36-mainstream-memory").write_bytes(mainstream)
            replace_once(card / "mainstream/start.sh", MAINSTREAM_SHA, hashlib.sha256(mainstream).hexdigest())
        for relative in ["enable", "terminal/enable", "archive/enable"]:
            (card / relative).touch()
        if args.enable_mainstream:
            (card / "mainstream/enable").touch()
        if wifi is not None:
            (card / "wifi-import.conf").write_bytes(wifi)
            (card / "wifi-import.conf").chmod(0o600)
        prefix = str(network.network_address).rsplit(".", 1)[0]
        old_pattern = r"^192\.168\.1\.[0-9]{1,3}$"
        pattern = "^" + re.escape(prefix) + r"\.[0-9]{1,3}$"
        for relative in ["terminal/start.sh", "mainstream/start.sh", "archive/start.sh"]:
            replace_once(card / relative, old_pattern, pattern)
        replace_once(card / "archive/start.sh", "A:192.168.1.10", f"A:{client}")
        if MAIN_APP_SHA not in (card / "mainstream/start.sh").read_text():
            raise ValueError("原厂 main_app 指纹丢失")
        files = {}
        for path in sorted(card.rglob("*")):
            if path.is_file():
                content = path.read_bytes()
                files[str(path.relative_to(package / "card-root"))] = {
                    "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(),
                }
        manifest = {"format": 1, "firmware": "S36 4K V1.15_Build20200629", "main_app_sha256": MAIN_APP_SHA,
                    "lan_cidr": str(network), "archive_client": str(client),
                    "mainstream_enabled": args.enable_mainstream, "files": files}
        (package / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        package.rename(output)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--busybox", type=Path, required=True)
    parser.add_argument("--dropbear", type=Path, required=True)
    parser.add_argument("--public-key", type=Path, required=True)
    parser.add_argument("--wifi-config", type=Path)
    parser.add_argument("--lan-cidr", required=True)
    parser.add_argument("--archive-client", required=True)
    parser.add_argument("--mainstream-binary", type=Path)
    parser.add_argument("--enable-mainstream", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = assemble(args)
    except (ValueError, OSError) as error:
        parser.exit(1, f"组装失败：{error}\n")
    # 不输出密钥、网络密码或配置文件正文。
    print(f"已组装 {len(manifest['files'])} 个文件；未连接或修改设备。请保护本地产物中的配置。")


if __name__ == "__main__":
    main()
