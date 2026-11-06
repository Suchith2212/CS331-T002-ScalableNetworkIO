#!/usr/bin/env python3
"""
Functional Echo Verification Test through the NEW C load generator (Deliverable 4).
Tests 'PING_ECHO_PAYLOAD_1234567890\n' against all 10 servers.
Verifies errors == 0 and req_s > 0.
"""
import os
import sys
import time
import socket
import subprocess
import signal
import re

PORT = 8095
SERVERS = [
    "server_blocking",
    "server_select",
    "server_poll",
    "server_epoll",
    "epoll_lt_server",
    "epoll_et_server",
    "epoll_lt_lean_server",
    "server_uring",
    "io_uring_opt_server",
    "reference_server"
]

def is_port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(('127.0.0.1', port)) == 0

def wait_for_server(port, timeout=3.0):
    start = time.time()
    while time.time() - start < timeout:
        if is_port_open(port):
            return True
        time.sleep(0.05)
    return False

def test_server(server_name):
    bin_path = os.path.join("bin", server_name)
    server_proc = subprocess.Popen(
        ["taskset", "-c", "0", bin_path, str(PORT)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    if not wait_for_server(PORT):
        server_proc.kill()
        return False, "Failed to start server"

    time.sleep(0.2)

    # Run new loadgen with 5 connections, 2 threads, 1s duration
    client_cmd = [
        "bin/loadgen",
        "--host", "127.0.0.1",
        "--port", str(PORT),
        "--conns", "10",
        "--active", "10",
        "--threads", "2",
        "--duration", "1",
        "--warmup", "0.5",
        "--cores", "1,2"
    ]

    p = subprocess.Popen(client_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, stderr = p.communicate()

    server_proc.send_signal(signal.SIGINT)
    try:
        server_proc.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        server_proc.kill()
        server_proc.wait()

    m_err = re.search(r'errors=(\d+)', stdout)
    m_req = re.search(r'req_s=([0-9.]+)', stdout)

    if m_err and m_req:
        errs = int(m_err.group(1))
        reqs = float(m_req.group(1))
        if errs == 0 and reqs > 0:
            return True, f"SUCCESS ({reqs:.1f} req/s, 0 errors)"
        else:
            return False, f"FAILED (errors={errs}, reqs={reqs})"
    return False, f"FAILED to parse output: {stdout.strip()}"

def main():
    os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    print("================================================================================")
    print("DELIVERABLE 4: Functional Verification Test through the NEW C Load Generator")
    print("================================================================================")
    all_passed = True
    for server in SERVERS:
        ok, msg = test_server(server)
        print(f"[{'PASS' if ok else 'FAIL'}] {server:<24} : {msg}")
        if not ok:
            all_passed = False
        time.sleep(0.3)

    print("--------------------------------------------------------------------------------")
    if all_passed:
        print("ALL 10 SERVERS PASSED FUNCTIONAL ECHO VERIFICATION WITH THE NEW LOAD GENERATOR!")
    else:
        print("SOME SERVERS FAILED VERIFICATION!")
        sys.exit(1)

if __name__ == "__main__":
    main()
