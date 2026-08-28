"""Colab 부트스트랩.

노트북 첫 셀에서 한 번 부릅니다. Colab 이 아니면 아무것도 하지 않습니다.

    import smartmob.colab as colab
    colab.bootstrap()
"""

from __future__ import annotations

import os
import subprocess
import sys

REPO_URL = "https://github.com/jihoyeo/mobility-simulation-book"


def in_colab() -> bool:
    return "google.colab" in sys.modules or os.path.exists("/content")


def bootstrap(repo_url: str = REPO_URL, dtumos_url: str | None = None, quiet: bool = True) -> None:
    """Colab 에서 한글 폰트와 smartmob 패키지를 준비합니다.

    ``dtumos_url`` 을 주면 그 서버를 쓰고, 안 주면 녹화본으로 동작합니다.
    교내망 서버는 Colab 에서 닿지 않으므로 공개 주소(터널)를 받아 넣어야 합니다.
    """
    if not in_colab():
        print("[smartmob] Colab 이 아닙니다. 할 일이 없습니다.")
        return

    _run(["apt-get", "-qq", "install", "-y", "fonts-nanum"], quiet)
    _run(["fc-cache", "-f"], quiet)
    _clear_matplotlib_cache()

    _run([sys.executable, "-m", "pip", "install", "-q", f"git+{repo_url}"], quiet)

    if dtumos_url:
        os.environ["SMARTMOB_DTUMOS_URL"] = dtumos_url.rstrip("/")
        os.environ.pop("SMARTMOB_OFFLINE", None)
    else:
        os.environ["SMARTMOB_OFFLINE"] = "1"
        print("[smartmob] DTUMOS 주소가 없어 녹화된 결과로 동작합니다.")

    from smartmob.viz import use_korean_font

    font = use_korean_font()
    print(f"[smartmob] 준비 완료 (한글 폰트: {font}).")
    print("           그림의 한글이 깨지면 런타임을 다시 시작하세요.")


def _run(cmd: list[str], quiet: bool) -> None:
    subprocess.run(
        cmd,
        check=False,
        stdout=subprocess.DEVNULL if quiet else None,
        stderr=subprocess.DEVNULL if quiet else None,
    )


def _clear_matplotlib_cache() -> None:
    """새로 설치한 폰트를 matplotlib 이 보게 합니다."""
    try:
        import shutil

        import matplotlib

        shutil.rmtree(matplotlib.get_cachedir(), ignore_errors=True)
        from matplotlib import font_manager

        font_manager._load_fontmanager(try_read_cache=False)
    except Exception:  # noqa: BLE001 - 폰트 캐시 실패가 부트스트랩을 막지 않게
        pass
