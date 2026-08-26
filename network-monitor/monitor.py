"""
monitor.py — live proof that nothing leaves the machine.

Reads the host's network interface byte counters and prints them on a fixed
interval. Run this on screen for your ENTIRE demo, not just as a screenshot at
the end. What you want the judges to see: every interface's external egress
counter stays flat while OCR, RAG, code execution, and doc generation all run.

For the strongest version of this proof: also show `docker network inspect`
on the sandbox container proving it has no network attached at all, and/or
physically show the machine's ethernet cable unplugged before you start.
"""

from __future__ import annotations
import time
import psutil

# Loopback and Docker's internal bridge don't count as "external" — only flag
# interfaces that could actually reach the internet.
INTERNAL_PREFIXES = ("lo", "docker0", "br-")


def snapshot() -> dict[str, dict[str, int]]:
    counters = psutil.net_io_counters(pernic=True)
    return {
        name: {"bytes_sent": c.bytes_sent, "bytes_recv": c.bytes_recv}
        for name, c in counters.items()
    }


def external_interfaces(snap: dict[str, dict[str, int]]) -> list[str]:
    return [name for name in snap if not name.startswith(INTERNAL_PREFIXES)]


def run(interval_seconds: float = 2.0):
    baseline = snapshot()
    ext = external_interfaces(baseline)
    print(f"Monitoring external interfaces: {ext or '(none found — fully isolated)'}")
    print(f"{'time':>8}  " + "  ".join(f"{name:>15}" for name in ext))

    start = time.time()
    try:
        while True:
            now = snapshot()
            elapsed = time.time() - start
            row = f"{elapsed:8.1f}  "
            for name in ext:
                sent_delta = now[name]["bytes_sent"] - baseline[name]["bytes_sent"]
                recv_delta = now[name]["bytes_recv"] - baseline[name]["bytes_recv"]
                flag = "  <-- LEAK" if (sent_delta > 0 or recv_delta > 0) else ""
                row += f"{sent_delta+recv_delta:>13}B{flag}  "
            print(row)
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    run()
