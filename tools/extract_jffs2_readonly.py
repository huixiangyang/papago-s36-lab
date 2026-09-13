#!/usr/bin/env python3
"""提取固件文件供静态分析；链接和设备节点只记录，不创建，不执行固件。"""

import argparse
import json
from pathlib import Path
from jefferson import jffs2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    destination = args.output.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    metadata = []

    def record_link(target, link, *unused, **kwargs):
        metadata.append({"type": "symlink", "path": str(Path(link).relative_to(destination)),
                         "target": target.decode(errors="replace") if isinstance(target, bytes) else target})

    def record_device(path, mode, device=0, *unused, **kwargs):
        metadata.append({"type": "device", "path": str(Path(path).relative_to(destination)),
                         "mode": mode, "device": device})

    # 禁止镜像中的链接影响主机路径，也不赋予提取的程序执行权限。
    jffs2.os.symlink = record_link
    jffs2.os.mknod = record_device
    jffs2.os.chmod = lambda *unused, **kwargs: None
    result = jffs2.extract_jffs2(args.image.resolve(), destination, verbose=0)
    (destination / "_extraction_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
