#!/usr/bin/env python3
"""用隔离的假网络命令验证租约回调，不操作本机网络或记录仪。"""
import json
import os
from pathlib import Path
import subprocess
import tempfile


def main():
    script = Path(__file__).resolve().parent.parent / "device/card-root/s36-lab/dhcp.sh"
    with tempfile.TemporaryDirectory(prefix="s36-dhcp-check-") as directory:
        root = Path(directory)
        command_log = root / "commands.jsonl"
        fake = root / "busybox"
        fake.write_text("""#!/usr/bin/env python3
import json, os, pathlib, sys
with open(os.environ['S36_TEST_LOG'], 'a') as f: f.write(json.dumps(sys.argv[1:])+'\\n')
if sys.argv[1]=='mv': pathlib.Path(sys.argv[2]).replace(sys.argv[3])
elif sys.argv[1]=='rm':
 for name in sys.argv[2:]:
  if not name.startswith('-'): pathlib.Path(name).unlink(missing_ok=True)
""")
        fake.chmod(0o700)
        env = dict(os.environ, S36_TEST_BUSYBOX=str(fake), S36_TEST_RUNTIME=str(root),
                   S36_TEST_LOG=str(command_log), interface="wlan0", ip="192.168.1.88",
                   subnet="255.255.255.0", router="192.168.1.1")

        def run(event, **changes):
            return subprocess.run(["/bin/sh", str(script), event], env=dict(env, **changes), capture_output=True)

        assert run("bound").returncode == 0
        assert (root / "lease.ip").read_text().strip() == "192.168.1.88"
        commands = [json.loads(line) for line in command_log.read_text().splitlines()]
        assert ["ifconfig", "wlan0", "192.168.1.88", "netmask", "255.255.255.0", "up"] in commands
        assert ["ip", "route", "replace", "default", "via", "192.168.1.1", "dev", "wlan0"] in commands
        assert run("renew", ip="192.168.1.89").returncode == 0
        assert (root / "lease.ip").read_text().strip() == "192.168.1.89"
        before = command_log.read_bytes()
        assert run("bound", interface="eth0").returncode != 0
        assert run("bound", ip="192.168.1.88; touch unexpected").returncode != 0
        assert command_log.read_bytes() == before
        assert run("deconfig").returncode == 0
        assert not (root / "lease.ip").exists()
    print("通过：获取租约、续租、释放地址、拒绝其他网卡和命令注入参数。")


if __name__ == "__main__":
    main()
