#!/usr/bin/env python3
"""只读反汇编指定地址范围的 ARM 裸镜像，并标注 PC 相对常量。"""
import argparse
from pathlib import Path
import re
import struct

from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("binary", type=Path)
parser.add_argument("--base", required=True, type=lambda value: int(value, 0))
parser.add_argument("--start", required=True, type=lambda value: int(value, 0))
parser.add_argument("--end", required=True, type=lambda value: int(value, 0))
args = parser.parse_args()
data = args.binary.read_bytes()
if not args.base <= args.start < args.end <= args.base + len(data):
    parser.error("地址范围必须位于镜像内")

decoder = Cs(CS_ARCH_ARM, CS_MODE_ARM)
decoder.skipdata = True
for instruction in decoder.disasm(data[args.start - args.base:args.end - args.base], args.start):
    note = ""
    operand = re.fullmatch(r"([a-z0-9]+), \[pc(?:, #(-?0x[0-9a-f]+|-?\d+))?\]", instruction.op_str)
    if instruction.mnemonic.startswith("ldr") and operand:
        offset = instruction.address + 8 + (int(operand[2], 0) if operand[2] else 0) - args.base
        if 0 <= offset <= len(data) - 4:
            value = struct.unpack_from("<I", data, offset)[0]
            note = f" => {value:#x}"
            if args.base <= value < args.base + len(data):
                text = data[value - args.base:value - args.base + 512].split(b"\0", 1)[0]
                # 字符串只是辅助注释；裸镜像中的数据区也可能被误解为指令。
                if text and all(byte in (9, 10, 13) or 32 <= byte <= 126 for byte in text):
                    note += " " + repr(text.decode("ascii"))
    print(f"{instruction.address:08x}: {instruction.mnemonic:9} {instruction.op_str}{note}")
