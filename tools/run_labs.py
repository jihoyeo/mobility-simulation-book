#!/usr/bin/env python3
"""실습 노트북을 전부 실행해 봅니다.

    python tools/run_labs.py                 # labs/ 의 노트북 전부
    python tools/run_labs.py ch03 ch11       # 이름에 그 글자가 든 것만

빈칸이 비어 있어도 끝까지 돌아야 합니다. 학생이 처음 열었을 때 오류가 나면 안 되기 때문입니다.
그래서 실습 노트북은 빈칸을 `None` 으로 두고 `lab.todo()` 로 확인만 합니다.

실행 결과는 저장하지 않습니다. 저장소에는 출력이 비워진 노트북만 둡니다.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LABS = ROOT / "labs"
TIMEOUT_SEC = 900


def run(path: Path) -> tuple[bool, str]:
    import nbformat
    from nbclient import NotebookClient
    from nbclient.exceptions import CellExecutionError

    nb = nbformat.read(path, as_version=4)
    client = NotebookClient(
        nb,
        timeout=TIMEOUT_SEC,
        kernel_name="python3",
        resources={"metadata": {"path": str(LABS)}},
    )
    try:
        client.execute()
    except CellExecutionError as exc:
        return False, str(exc).strip().splitlines()[-1]
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"
    return True, ""


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    os.environ.setdefault("SMARTMOB_OFFLINE", "1")
    os.environ.setdefault("MPLBACKEND", "Agg")

    books = sorted(LABS.glob("*.ipynb"))
    if argv:
        books = [p for p in books if any(a in p.stem for a in argv)]
    if not books:
        print("실행할 노트북이 없습니다.")
        return 1

    failures = []
    for path in books:
        started = time.perf_counter()
        ok, detail = run(path)
        elapsed = time.perf_counter() - started
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] {path.name:28s} {elapsed:6.1f}s")
        if not ok:
            print(f"       {detail}")
            failures.append(path.name)

    print()
    print(f"{len(books) - len(failures)}/{len(books)} 통과")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
