#!/usr/bin/env python3
import socket
import subprocess
import time
import sys

PORT = 8081

def test_server(binary_path):
    print(f"Testing {binary_path} ... ", end="", flush=True)
    proc = subprocess.Popen([binary_path, str(PORT)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.3)

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect(('127.0.0.1', PORT))
        test_msg = b"HELLO_NETWORKS_PROJECT_123\n"
        s.sendall(test_msg)
        resp = s.recv(1024)
        s.close()
        
        if resp == test_msg:
            print("SUCCESS! (Received exact echo payload)")
            res = True
        else:
            print(f"FAILED! Expected {test_msg}, got {resp}")
            res = False
    except Exception as e:
        print(f"FAILED with error: {e}")
        res = False

    proc.kill()
    proc.wait()
    return res

def main():
    servers = [
        "bin/server_blocking",
        "bin/server_select",
        "bin/server_poll",
        "bin/server_epoll",
        "bin/server_uring"
    ]
    
    passed = 0
    total = 0
    for s in servers:
        if test_server(s):
            passed += 1
        total += 1

    print(f"\nResult: {passed}/{total} servers passed correctness verification.")

if __name__ == "__main__":
    main()
