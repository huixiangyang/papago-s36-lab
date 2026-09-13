#!/usr/bin/env python3
"""只在新本地目录提取固定版本 OTA 容器，不执行程序或写入设备。"""
import argparse
import hashlib
from pathlib import Path

from build_card_hook_candidate import SOURCE_SHA256, read_container


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    data = args.source.read_bytes()
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA256:
        parser.error("原厂 OTA SHA-256 不匹配")
    entries = read_container(data)
    for name, _ in entries:
        if name in {"", ".", ".."} or Path(name).name != name or "\\" in name:
            parser.error("容器文件名无效")
    args.output.mkdir(parents=True, exist_ok=False)
    for name, payload in entries:
        (args.output / name).write_bytes(payload)
    print(f"已提取 {len(entries)} 个条目；仅供离线分析。")


if __name__ == "__main__":
    main()
