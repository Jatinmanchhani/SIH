"""
sandbox.py — runs model-generated code safely, with no network access.

Two backends, same interface:
  - DockerSandbox: what you actually use on deployment. `--network none` is the
    load-bearing flag — it's what makes "code execution in a sandbox" also part
    of your air-gap proof, not just a feature.
  - SubprocessSandbox: a fallback for environments without a Docker daemon
    available (like this one). Same timeout/output-capture contract, weaker
    isolation — use it for development, not for your actual demo.
"""

from __future__ import annotations
import subprocess
import tempfile
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExecutionResult:
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool
    backend: str


class DockerSandbox:
    """
    Requires a Docker daemon on the host. This is what your demo should actually run.
    """

    def __init__(self, image: str = "python:3.11-slim", timeout_seconds: int = 15,
                 memory_limit: str = "512m", cpu_limit: str = "1.0"):
        self.image = image
        self.timeout_seconds = timeout_seconds
        self.memory_limit = memory_limit
        self.cpu_limit = cpu_limit

    def run_python(self, code: str) -> ExecutionResult:
        with tempfile.TemporaryDirectory() as tmp:
            script_path = Path(tmp) / "script.py"
            script_path.write_text(code)

            cmd = [
                "docker", "run", "--rm",
                "--network", "none",                 # <-- the actual air-gap enforcement
                "--memory", self.memory_limit,
                "--cpus", self.cpu_limit,
                "--read-only",
                "-v", f"{tmp}:/workspace:ro",
                "-w", "/workspace",
                self.image,
                "python", "script.py",
            ]
            try:
                proc = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=self.timeout_seconds
                )
                return ExecutionResult(
                    stdout=proc.stdout, stderr=proc.stderr,
                    exit_code=proc.returncode, timed_out=False, backend="docker",
                )
            except subprocess.TimeoutExpired:
                return ExecutionResult(
                    stdout="", stderr="Execution timed out", exit_code=-1,
                    timed_out=True, backend="docker",
                )


class SubprocessSandbox:
    """
    Fallback with no Docker dependency — runs in a throwaway temp directory with a
    hard timeout. Weaker isolation than Docker (shares the host network and kernel),
    so it's clearly labeled: development / this-sandbox use only, not your demo.
    """

    def __init__(self, timeout_seconds: int = 15):
        self.timeout_seconds = timeout_seconds

    def run_python(self, code: str) -> ExecutionResult:
        tmp = tempfile.mkdtemp(prefix="agent_sandbox_")
        try:
            script_path = Path(tmp) / "script.py"
            script_path.write_text(code)
            try:
                proc = subprocess.run(
                    ["python3", str(script_path)],
                    capture_output=True, text=True,
                    timeout=self.timeout_seconds, cwd=tmp,
                )
                return ExecutionResult(
                    stdout=proc.stdout, stderr=proc.stderr,
                    exit_code=proc.returncode, timed_out=False, backend="subprocess",
                )
            except subprocess.TimeoutExpired:
                return ExecutionResult(
                    stdout="", stderr="Execution timed out", exit_code=-1,
                    timed_out=True, backend="subprocess",
                )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


def get_sandbox(prefer_docker: bool = True):
    """Picks DockerSandbox if a daemon is reachable, else falls back with a clear warning."""
    if prefer_docker:
        try:
            subprocess.run(["docker", "info"], capture_output=True, timeout=3, check=True)
            return DockerSandbox()
        except Exception:
            print("[sandbox] No Docker daemon found — falling back to SubprocessSandbox. "
                  "Use DockerSandbox for your actual demo to keep the network-none guarantee.")
    return SubprocessSandbox()


if __name__ == "__main__":
    sandbox = get_sandbox()
    result = sandbox.run_python(
        "print('BOM total check:')\n"
        "items = [('bolt', 4, 12.5), ('gasket', 2, 8.0)]\n"
        "total = sum(qty * price for _, qty, price in items)\n"
        "print(f'Total: {total}')"
    )
    print(f"[backend={result.backend}] exit={result.exit_code}")
    print("stdout:", result.stdout)
    if result.stderr:
        print("stderr:", result.stderr)
