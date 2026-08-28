"""녹화-재생(fixture) 계층.

DTUMOS 서버 없이도 책이 빌드되도록, 엔진 호출의 응답을 파일로 녹화해 두고
오프라인에서는 그것을 돌려줍니다.

동작 규칙
---------
- 키는 요청 페이로드의 sha256 앞 12자입니다. 같은 요청 = 같은 녹화.
- 녹화가 없으면 :class:`FixtureMissing` 을 **던져 빌드를 실패시킵니다.**
  조용히 낡은 숫자를 가르치는 것보다 낫습니다.
- 목록은 ``data/fixtures/index.json`` 에 있습니다.

CLI
---
    python -m smartmob.fixtures list
    python -m smartmob.fixtures check      # 녹화본과 index.json 이 맞는지
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from smartmob.config import fixtures_dir

INDEX_NAME = "index.json"


class FixtureMissing(RuntimeError):
    """오프라인인데 이 요청의 녹화본이 없습니다."""

    def __init__(self, kind: str, key: str, payload: dict[str, Any]) -> None:
        compact = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        super().__init__(
            f"'{kind}' 요청의 녹화본이 없습니다 (key={key}).\n"
            f"  요청: {compact}\n"
            f"  DTUMOS 서버를 띄운 뒤 아래를 실행해 녹화하세요:\n"
            f"    python -m smartmob.fixtures record --kind {kind} --payload '{compact}'"
        )


def key_for(payload: dict[str, Any]) -> str:
    """요청 페이로드 → 12자 키. 키 순서에 무관합니다."""
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def load_index() -> dict[str, dict[str, Any]]:
    path = fixtures_dir() / INDEX_NAME
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_index(index: dict[str, dict[str, Any]]) -> None:
    fixtures_dir().mkdir(parents=True, exist_ok=True)
    (fixtures_dir() / INDEX_NAME).write_text(
        json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def directory_for(key: str) -> Path | None:
    """녹화본 디렉터리. 없으면 None."""
    entry = load_index().get(key)
    if entry is None:
        return None
    path = fixtures_dir() / entry["dir"]
    return path if path.exists() else None


def replay(kind: str, payload: dict[str, Any]) -> Path:
    """녹화본 디렉터리를 돌려줍니다. 없으면 FixtureMissing."""
    key = key_for(payload)
    path = directory_for(key)
    if path is None:
        raise FixtureMissing(kind, key, payload)
    return path


def record(kind: str, payload: dict[str, Any], source: Path, label: str | None = None) -> Path:
    """``source`` 디렉터리의 파일들을 녹화본으로 복사하고 index 에 등록합니다."""
    import shutil

    key = key_for(payload)
    name = label or f"{kind}_{key}"
    target = fixtures_dir() / name
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)

    index = load_index()
    index[key] = {
        "kind": kind,
        "dir": name,
        "payload": payload,
    }
    save_index(index)
    return target


def _main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="python -m smartmob.fixtures")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="녹화본 목록")
    sub.add_parser("check", help="index.json 과 실제 디렉터리가 맞는지 확인")
    args = ap.parse_args(argv)

    index = load_index()
    if args.cmd == "list":
        if not index:
            print("녹화본이 없습니다.")
            return 0
        for key, entry in sorted(index.items()):
            print(f"{key}  {entry['kind']:<16} {entry['dir']}")
        return 0

    missing = [k for k, e in index.items() if not (fixtures_dir() / e["dir"]).exists()]
    listed = {e["dir"] for e in index.values()}
    orphan = [
        p.name
        for p in fixtures_dir().glob("*")
        if p.is_dir() and p.name not in listed
    ]
    for k in missing:
        print(f"index 에는 있으나 디렉터리가 없습니다: {k} -> {index[k]['dir']}")
    for name in orphan:
        print(f"디렉터리는 있으나 index 에 없습니다: {name}")
    if not missing and not orphan:
        print(f"녹화본 {len(index)}건, 이상 없음")
    return 1 if (missing or orphan) else 0


if __name__ == "__main__":
    raise SystemExit(_main())
