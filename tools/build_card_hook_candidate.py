#!/usr/bin/env python3
"""离线构建仅含应用分区的研究候选包；不向记录仪或存储卡写入。"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zlib

SOURCE_SHA256 = "3da7a30e60375cd56f7f927495fa014db5b89bcdbf263469aafdf06280da290e"
HEADER_SIZE = 0x4c4
APPFS_CAPACITY = 5632 * 1024
HOOK = '''
# S36 LAB: 卡上明确启用后才执行扩展，后台等待不阻塞原程序。
(
    s36_wait=0
    while [ "$s36_wait" -lt 90 ]; do
        if /bin/busybox grep -qs ' /app/sd ' /proc/mounts &&
           [ -f /app/sd/s36-lab/enable ] &&
           [ -f /app/sd/s36-lab/start.sh ]; then
            /bin/sh /app/sd/s36-lab/start.sh >/dev/null 2>&1
            break
        fi
        /bin/busybox sleep 1
        s36_wait=$((s36_wait + 1))
    done
) &
'''.encode("utf-8")


def u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def jffs_crc(data):
    # JFFS2 使用不做首尾反转的 CRC；与升级容器的 zlib CRC 不同。
    return zlib.crc32(data, 0xffffffff) ^ 0xffffffff


def read_container(data):
    assert u32(data, 0) == 0x08122515
    assert u32(data, len(data) - 4) == 0x0812251d
    assert u32(data, 12) == len(data)
    assert u32(data, 4) == zlib.crc32(data[8:-4])
    assert u32(data, 16) == 0
    count = u32(data, 0x498)
    assert 0 < count <= 10
    offsets = [u32(data, 0x494)] + [u32(data, 0x49c + i * 4) for i in range(count)]
    entries = []
    end = HEADER_SIZE
    for offset in offsets:
        assert offset == end and offset + 40 <= len(data) - 4
        name = data[offset:offset + 32].split(b"\0", 1)[0].decode("ascii")
        size, stored_size = struct.unpack_from("<II", data, offset + 32)
        assert size == stored_size and stored_size > 0
        end = offset + 40 + stored_size
        assert end <= len(data) - 4
        entries.append((name, data[offset + 40:end]))
    assert end == len(data) - 4 and entries[0][0] == "config"
    assert len({name for name, _ in entries}) == len(entries)
    return entries


def pack_container(source, config, image, version):
    header = bytearray(source[:HEADER_SIZE])
    header[0x54:0x94] = version.encode("ascii").ljust(64, b"\0")
    header[0x494:0x4c4] = b"\0" * 48
    struct.pack_into("<II", header, 0x494, HEADER_SIZE, 1)
    output = header
    for index, (name, payload) in enumerate((("config", config), ("appfs.jffs2", image))):
        if index:
            struct.pack_into("<I", output, 0x49c, len(output))
        output.extend(name.encode("ascii").ljust(32, b"\0"))
        output.extend(struct.pack("<II", len(payload), len(payload)))
        output.extend(payload)
    output.extend(struct.pack("<I", 0x0812251d))
    struct.pack_into("<I", output, 12, len(output))
    struct.pack_into("<I", output, 4, zlib.crc32(output[8:-4]))
    result = bytes(output)
    assert read_container(result) == [("config", config), ("appfs.jffs2", image)]
    # 模型、启动参数、启动命令全部沿用；包里不携带其他分区镜像。
    assert result[0x14:0x54] == source[0x14:0x54]
    assert result[0x94:0x494] == source[0x94:0x494]
    return result


def patch_bootapp(image, content):
    offset, inode_number = 0, None
    inode_nodes = []
    while offset + 12 <= len(image):
        magic, kind, length, crc = struct.unpack_from("<HHII", image, offset)
        if magic != 0x1985 or length < 12 or offset + length > len(image):
            offset += 4
            continue
        node = image[offset:offset + length]
        assert jffs_crc(node[:8]) == crc
        if kind == 0xe001 and node[40:40 + node[28]] == b"bootapp":
            assert u32(node, 12) == 1
            inode_number = u32(node, 20)
        if kind == 0xe002:
            assert jffs_crc(node[:60]) == u32(node, 64)
            assert jffs_crc(node[68:]) == u32(node, 60)
            inode_nodes.append(node)
        offset += (length + 3) & ~3
    matches = [node for node in inode_nodes if u32(node, 12) == inode_number]
    assert inode_number == 3 and len(matches) == 1
    original = matches[0]
    assert u32(original, 44) == 0
    node = bytearray(original[:68])
    struct.pack_into("<I", node, 4, 68 + len(content))
    struct.pack_into("<I", node, 8, jffs_crc(node[:8]))
    struct.pack_into("<I", node, 16, u32(original, 16) + 1)
    struct.pack_into("<I", node, 28, len(content))
    struct.pack_into("<III", node, 44, 0, len(content), len(content))
    # 使用 JFFS2 必备的无压缩节点，不引入额外解压依赖。
    node[56:60] = b"\0" * 4
    struct.pack_into("<I", node, 60, jffs_crc(content))
    struct.pack_into("<I", node, 64, jffs_crc(node[:60]))
    node.extend(content)
    node.extend(b"\xff" * (-len(node) % 4))
    assert len(image) % 4 == 0
    assert len(image) % 65536 + len(node) <= 65536
    result = image + node
    assert len(result) < APPFS_CAPACITY
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("original_bootapp", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    source = args.source.read_bytes()
    assert hashlib.sha256(source).hexdigest() == SOURCE_SHA256
    entries = dict(read_container(source))
    original = args.original_bootapp.read_bytes()
    assert original.endswith(b"./main_app &\n\n")
    modified = original + HOOK
    image = patch_bootapp(entries["appfs.jffs2"], modified)
    args.output.mkdir(parents=True, exist_ok=False)
    files = {
        "bootapp": modified,
        "appfs.jffs2": image,
        "card-hook.appfs-only.candidate": pack_container(source, entries["config"], image, "1.0.0.2.20260912"),
        "restore-stock.appfs-only.candidate": pack_container(source, entries["config"], entries["appfs.jffs2"], "1.0.0.3.20260912"),
    }
    manifest = {"status": "offline candidate, not flashed or hardware validated", "source_sha256": SOURCE_SHA256,
                "partitions_included": ["appfs.jffs2"], "config_entry_unchanged": True,
                "changed_path": "/app/bootapp", "enabled_script": "/app/sd/s36-lab/start.sh",
                "enable_marker": "/app/sd/s36-lab/enable", "appfs_capacity": APPFS_CAPACITY, "files": {}}
    for name, data in files.items():
        (args.output / name).write_bytes(data)
        manifest["files"][name] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    (args.output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
