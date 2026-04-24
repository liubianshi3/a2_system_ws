#!/usr/bin/env python3

import argparse
import ipaddress
import json
import shutil
import socket
import subprocess
import sys


def run(command):
    return subprocess.run(command, capture_output=True, text=True, check=False)


def list_interfaces():
    ip_bin = shutil.which("ip")
    if ip_bin is None:
        return []
    result = run([ip_bin, "-j", "addr", "show"])
    if result.returncode != 0:
        return []
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return []


def looks_physical(name):
    allowed = ("en", "eth", "enx")
    blocked = ("lo", "docker", "br-", "veth", "virbr", "wl", "tun", "tap", "tailscale", "Meta")
    return name.startswith(allowed) and not any(name.startswith(prefix) for prefix in blocked)


def probe_tcp(ip, port, timeout):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        return sock.connect_ex((ip, port)) == 0
    finally:
        sock.close()


def same_subnet(addr, prefixlen, target_ip):
    try:
        network = ipaddress.ip_network(f"{addr}/{prefixlen}", strict=False)
        return ipaddress.ip_address(target_ip) in network
    except ValueError:
        return False


def main():
    parser = argparse.ArgumentParser(description="MID360 host-side connectivity check.")
    parser.add_argument("--target-ip", default="192.168.124.20")
    parser.add_argument("--target-port", type=int, default=56100)
    parser.add_argument("--timeout", type=float, default=1.0)
    parser.add_argument("--interface", default="")
    args = parser.parse_args()

    interfaces = list_interfaces()
    candidates = []
    for item in interfaces:
        name = item.get("ifname", "")
        state = item.get("operstate", "")
        if not looks_physical(name):
            continue
        if state not in ("UP", "UNKNOWN"):
            continue
        ipv4 = [
            (entry.get("local", ""), entry.get("prefixlen", 24))
            for entry in item.get("addr_info", [])
            if entry.get("family") == "inet"
        ]
        candidates.append((name, ipv4))

    selected = args.interface or (candidates[0][0] if candidates else "")
    print("=== MID360 Link Check ===")
    print(f"target_ip    : {args.target_ip}")
    print(f"target_port  : {args.target_port}")
    print(f"interface    : {selected or '<auto-none>'}")
    print("candidates   :")
    same_subnet_candidates = []
    for name, addrs in candidates:
        if not addrs:
            print(f"  - {name}: <no ipv4>")
            continue
        rendered = []
        for addr, prefixlen in addrs:
            in_same_subnet = same_subnet(addr, prefixlen, args.target_ip)
            rendered.append(f"{addr}/{prefixlen}{' [same-subnet]' if in_same_subnet else ''}")
            if in_same_subnet:
                same_subnet_candidates.append(name)
        print(f"  - {name}: {', '.join(rendered)}")

    if same_subnet_candidates:
        deduped = []
        for item in same_subnet_candidates:
            if item not in deduped:
                deduped.append(item)
        print(f"recommended  : {', '.join(deduped)}")
    else:
        print("recommended  : no interface currently appears to share the target subnet")

    ping_bin = shutil.which("ping")
    ping_ok = False
    if ping_bin is not None:
        ping_result = run([ping_bin, "-c", "1", "-W", str(int(max(args.timeout, 1.0))), args.target_ip])
        ping_ok = ping_result.returncode == 0
        print(f"ping         : {'ok' if ping_ok else 'failed'}")
    else:
        print("ping         : skipped (`ping` not found)")

    tcp_ok = probe_tcp(args.target_ip, args.target_port, args.timeout)
    print(f"tcp_probe    : {'open' if tcp_ok else 'closed/unreachable'}")
    print("note         : MID360 data is typically UDP. A failed TCP probe does not prove the lidar is offline.")

    if selected == "":
        print("result       : failed (no candidate interface found)")
        return 2
    if not ping_ok and not tcp_ok:
        print("result       : warning (host network path not confirmed)")
        return 1
    print("result       : ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
