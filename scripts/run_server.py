from __future__ import annotations

import atexit
import os
import shutil
import subprocess
import sys
from pathlib import Path

import uvicorn


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
PID_FILE = DATA_DIR / "server.pid"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def write_pid() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")


def remove_pid() -> None:
    try:
        if PID_FILE.exists() and PID_FILE.read_text(encoding="utf-8").strip() == str(os.getpid()):
            PID_FILE.unlink()
    except OSError:
        pass


def tailscale_url() -> str | None:
    command = shutil.which("tailscale") or shutil.which("tailscale.exe")
    if command is None:
        return None
    try:
        result = subprocess.run(
            [command, "ip", "-4"],
            capture_output=True,
            check=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    address = result.stdout.strip().splitlines()
    return f"http://{address[0]}:8000" if address else None


def main() -> None:
    os.chdir(PROJECT_ROOT)
    write_pid()
    atexit.register(remove_pid)

    print("=" * 58)
    print(" KTX Auto Booker 서버가 실행 중입니다.")
    print(" 내 컴퓨터: http://127.0.0.1:8000")
    remote_url = tailscale_url()
    if remote_url:
        print(f" 외부 접속: {remote_url}")
    else:
        print(" 외부 접속: Tailscale 설치 후 이 창을 다시 열면 표시됩니다.")
    print(" 서버 종료는 STOP_SERVER.bat를 실행하세요.")
    print("=" * 58)

    try:
        uvicorn.run(
            "backend.app.main:app",
            host="0.0.0.0",
            port=8000,
            reload=False,
            access_log=True,
        )
    finally:
        remove_pid()


if __name__ == "__main__":
    main()
