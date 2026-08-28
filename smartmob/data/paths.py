"""데이터 파일 위치와 내려받기.

실습 데이터는 두 곳에 있습니다.

- **저장소 안** (`data/`): 15MB 이하의 작은 것들. clone 하면 바로 있습니다.
- **외부 배포**: 큰 것들. `data/MANIFEST.toml` 에 URL 과 sha256 이 적혀 있고,
  :func:`ensure` 가 처음 쓸 때 내려받아 `data/_downloads/` 에 둡니다.

    from smartmob.data import data_path, ensure

    p = data_path("hanam/road_graph_edges.parquet")   # 저장소 안
    q = ensure("chp2_od_data.parquet")                # 필요하면 내려받기
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from smartmob.config import data_dir

MANIFEST_NAME = "MANIFEST.toml"
DOWNLOAD_SUBDIR = "_downloads"


class DataNotFound(FileNotFoundError):
    pass


def data_path(relative: str) -> Path:
    """`data/` 안의 파일 경로. 없으면 무엇을 해야 하는지 알려 줍니다."""
    p = data_dir() / relative
    if p.exists():
        return p
    downloaded = data_dir() / DOWNLOAD_SUBDIR / Path(relative).name
    if downloaded.exists():
        return downloaded
    raise DataNotFound(
        f"{p} 가 없습니다.\n"
        f"  큰 파일이면 다음으로 내려받습니다:  "
        f"python -c \"from smartmob.data import ensure; ensure('{Path(relative).name}')\""
    )


def load_manifest() -> dict[str, dict[str, str]]:
    """`data/MANIFEST.toml` 을 읽습니다. 없으면 빈 dict."""
    path = data_dir() / MANIFEST_NAME
    if not path.exists():
        return {}
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover - Python 3.10
        import tomli as tomllib  # type: ignore[no-redef]
    with path.open("rb") as fh:
        raw = tomllib.load(fh)
    return raw.get("asset", {})


def sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


def ensure(name: str, force: bool = False) -> Path:
    """MANIFEST 에 등록된 자산을 내려받아 경로를 돌려줍니다.

    이미 있고 sha256 이 맞으면 그대로 씁니다.
    """
    manifest = load_manifest()
    if name not in manifest:
        known = ", ".join(sorted(manifest)) or "(등록된 자산 없음)"
        raise DataNotFound(f"'{name}' 이 MANIFEST.toml 에 없습니다. 등록된 자산: {known}")

    entry = manifest[name]
    target = data_dir() / DOWNLOAD_SUBDIR / name
    expected = entry.get("sha256", "")

    if target.exists() and not force:
        if not expected or sha256(target) == expected:
            return target
        print(f"[smartmob] {name} 의 체크섬이 다릅니다. 다시 내려받습니다.")

    target.parent.mkdir(parents=True, exist_ok=True)
    _download(entry["url"], target)

    if expected:
        actual = sha256(target)
        if actual != expected:
            target.unlink(missing_ok=True)
            raise RuntimeError(
                f"{name} 의 sha256 이 다릅니다.\n  기대: {expected}\n  실제: {actual}"
            )
    return target


def _download(url: str, target: Path) -> None:
    import requests

    print(f"[smartmob] 내려받는 중: {url}")
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        done = 0
        tmp = target.with_suffix(target.suffix + ".part")
        with tmp.open("wb") as fh:
            for block in r.iter_content(chunk_size=1 << 20):
                fh.write(block)
                done += len(block)
                if total:
                    print(f"\r  {done / 1e6:.1f} / {total / 1e6:.1f} MB", end="")
        print()
        tmp.replace(target)
