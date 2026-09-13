#!/usr/bin/env python3
"""只读定位 ARM 程序中的字符串、调用和全局变量引用。"""
import argparse
import bisect
import json
from pathlib import Path
import re
import struct

from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM
from elftools.elf.elffile import ELFFile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("binary", type=Path)
parser.add_argument("--text", action="append", default=[])
parser.add_argument("--address", type=lambda s: int(s, 0), action="append", default=[])
args = parser.parse_args()
data = args.binary.read_bytes()
with args.binary.open("rb") as file:
    elf = ELFFile(file)
    sections = list(elf.iter_sections())
    text_section = elf.get_section_by_name(".text")
    exidx = elf.get_section_by_name(".ARM.exidx")
    got = elf.get_section_by_name(".got")
    starts = []
    for index in range(0, exidx["sh_size"], 8):
        value = struct.unpack_from("<I", exidx.data(), index)[0] & 0x7fffffff
        starts.append((exidx["sh_addr"] + index + value - ((1 << 31) if value & (1 << 30) else 0)) & ~1)

    def word(address):
        for section in sections:
            if section["sh_type"] != "SHT_NOBITS" and section["sh_addr"] <= address < section["sh_addr"] + section["sh_size"]:
                return struct.unpack_from("<I", data, address - section["sh_addr"] + section["sh_offset"])[0]
        return None

    targets = {address: hex(address) for address in args.address}
    for match in re.finditer(rb"[\x20-\x7e]{4,}", data):
        value = match.group().decode()
        if any(pattern.lower() in value.lower() for pattern in args.text):
            for section in sections:
                if section["sh_type"] != "SHT_NOBITS" and section["sh_offset"] <= match.start() < section["sh_offset"] + section["sh_size"]:
                    targets[match.start() - section["sh_offset"] + section["sh_addr"]] = value
                    break

    got_offsets = {}
    if got:
        for index in range(0, got["sh_size"], 4):
            target = struct.unpack_from("<I", got.data(), index)[0]
            if target in args.address:
                got_offsets[index] = target

    disassembler = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    disassembler.skipdata = True
    disassembler.detail = True
    constants = {}
    results = []
    for instruction in disassembler.disasm(text_section.data(), text_section["sh_addr"]):
        address, mnemonic, operands = instruction.address, instruction.mnemonic, instruction.op_str
        if not instruction.id:
            constants.clear()
            continue
        # 优化后的代码会把常量加载和 PC 相加隔开；追踪寄存器，遇到写入立即失效。
        old_constants = constants.copy()
        _, written = instruction.regs_access()
        for register in written:
            constants.pop(instruction.reg_name(register), None)
        target, kind = None, None
        if mnemonic in ("bl", "b") and operands.startswith("#"):
            candidate = int(operands[1:], 0)
            if candidate in args.address:
                target, kind = candidate, "direct branch"
        if mnemonic == "add":
            add = re.fullmatch(r"([a-z0-9]+), pc, ([a-z0-9]+)", operands)
            if add and add[2] in old_constants:
                candidate = (old_constants[add[2]] + address + 8) & 0xffffffff
                if candidate in targets:
                    target, kind = candidate, "PC relative"
        if mnemonic == "ldr":
            load = re.fullmatch(r"([a-z0-9]+), \[pc(?:, #(-?0x[0-9a-f]+|-?\d+))?\]", operands)
            if load:
                literal = word(address + 8 + (int(load[2], 0) if load[2] else 0))
                if literal is not None:
                    constants[load[1]] = literal
                # GOT 偏移命中只是候选，需再看后续索引加载及基址。
                if literal in got_offsets:
                    target, kind = got_offsets[literal], "possible GOT reference"
        if target is not None:
            index = bisect.bisect_right(starts, address) - 1
            results.append({"instruction": hex(address), "function": hex(starts[index]), "target": hex(target), "kind": kind, "description": targets[target]})
        if mnemonic in ("bl", "blx"):
            for register in ("r0", "r1", "r2", "r3", "ip", "lr"):
                constants.pop(register, None)
        if mnemonic in ("b", "bx", "pop"):
            constants.clear()
    print(json.dumps(results, ensure_ascii=False, indent=2))
