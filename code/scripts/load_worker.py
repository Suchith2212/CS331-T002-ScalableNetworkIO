#!/usr/bin/env python3
import sys
import time
import socket
import asyncio

async def worker(port, stop_event, stats):
    payload = b"PING_ECHO_PAYLOAD_1234567890\n"
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection('127.0.0.1', port), timeout=3.0
        )
        sock = writer.get_extra_info('socket')
        if sock:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except Exception:
        return

    req_count = 0
    while not stop_event.is_set():
        try:
            writer.write(payload)
            await writer.drain()
            data = await reader.read(1024)
            if not data:
                break
            req_count += 1
        except Exception:
            break

    try:
        writer.close()
        await writer.wait_closed()
    except Exception:
        pass

    stats["total"] += req_count

async def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    num_conns = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    duration = int(sys.argv[3]) if len(sys.argv) > 3 else 10

    stop_event = asyncio.Event()
    stats = {"total": 0}

    tasks = [
        asyncio.create_task(worker(port, stop_event, stats))
        for _ in range(num_conns)
    ]

    await asyncio.sleep(duration)
    stop_event.set()
    await asyncio.gather(*tasks, return_exceptions=True)

    print(stats["total"])

if __name__ == "__main__":
    asyncio.run(main())
