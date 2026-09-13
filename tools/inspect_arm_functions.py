#!/usr/bin/env python3
"""只读反汇编 ARM 固件函数，标注常量字符串与导入函数。"""
import argparse
import bisect
from pathlib import Path
import re
import struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM
from elftools.elf.elffile import ELFFile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("binary", type=Path)
parser.add_argument("addresses", nargs="+", type=lambda x: int(x, 0))
args = parser.parse_args()
data = args.binary.read_bytes()
with args.binary.open("rb") as file:
    elf = ELFFile(file)
    sections = list(elf.iter_sections())
    symbols = {s["st_value"]: s.name for s in elf.get_section_by_name(".dynsym").iter_symbols() if s["st_value"]}
    relocations = elf.get_section_by_name(".rel.plt")
    imports = elf.get_section_by_name(".dynsym")
    plt = elf.get_section_by_name(".plt")
    for index, relocation in enumerate(relocations.iter_relocations()):
        symbols[plt["sh_addr"] + 20 + index * 12] = imports.get_symbol(relocation["r_info_sym"]).name

    def offset(address):
        for section in sections:
            if section["sh_type"] != "SHT_NOBITS" and section["sh_addr"] <= address < section["sh_addr"] + section["sh_size"]:
                return address - section["sh_addr"] + section["sh_offset"]

    def word(address):
        location = offset(address)
        return struct.unpack_from("<I", data, location)[0] if location is not None else 0

    def describe(address):
        location = offset(address)
        if address in symbols:
            return symbols[address]
        if location is None:
            return ""
        raw = data[location:location + 250].split(b"\0")[0]
        if len(raw) > 2 and all(c >= 32 or c in [9, 10, 13, 27] for c in raw):
            return repr(raw.decode(errors="replace"))
        return ""

    # ARM 异常展开表用于确定函数范围，不执行目标程序。
    exidx = elf.get_section_by_name(".ARM.exidx")
    starts = []
    for index in range(0, exidx["sh_size"], 8):
        value = struct.unpack_from("<I", exidx.data(), index)[0] & 0x7fffffff
        starts.append((exidx["sh_addr"] + index + value - ((1 << 31) if value & (1 << 30) else 0)) & ~1)
    disassembler = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    disassembler.skipdata = True
    for address in args.addresses:
        start_index = bisect.bisect_right(starts, address) - 1
        start, end = starts[start_index:start_index + 2]
        print(f"\nFUNCTION {start:#x}..{end:#x} {symbols.get(start, '')}")
        previous = None
        for current, size, mnemonic, operands in disassembler.disasm_lite(data[offset(start):offset(start) + end - start], start):
            note = ""
            if mnemonic == "add" and previous and previous[2] == "ldr":
                add = re.fullmatch(r"(r\d+|ip|lr), pc, \1", operands)
                if add:
                    load = re.fullmatch(re.escape(add[1]) + r", \[pc(?:, #(-?0x[0-9a-f]+|-?\d+))?\]", previous[3])
                    if load:
                        target = (word(previous[0] + 8 + (int(load[1], 0) if load[1] else 0)) + current + 8) & 0xffffffff
                        note = f" -> {target:#x} {describe(target)}"
            if mnemonic in ["bl", "blx"] and operands.startswith("#"):
                note = " -> " + symbols.get(int(operands[1:], 0), "")
            print(f"{current:08x}: {mnemonic:8} {operands}{note}")
            previous = current, size, mnemonic, operands
