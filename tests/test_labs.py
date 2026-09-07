"""교재와 실습 노트북이 어긋나지 않는지 확인합니다.

이 파일이 막으려는 사고는 하나입니다. 장을 고치면서 노트북을 잊거나,
노트북 이름을 바꾸면서 본문의 안내를 그대로 두는 것입니다.
그렇게 되면 학생이 없는 파일을 열게 됩니다.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
KO = ROOT / "ko"
LABS = ROOT / "labs"

CHAPTERS = sorted(p for p in KO.glob("ch*.md"))
GRADED = {"ch03_dijkstra": "ch03", "ch06_raptor": "ch06", "ch11_simloop": "ch11"}


def _notebooks_in(text: str) -> list[str]:
    return re.findall(r"labs/(ch\w+)\.ipynb", text)


# --------------------------------------------------------------------------- #
# 본문 → 노트북
# --------------------------------------------------------------------------- #


def test_every_chapter_exists():
    """장이 13개(0~12장)여야 합니다. 늘리거나 줄이면 이 목록도 같이 고칩니다."""
    assert len(CHAPTERS) == 13


@pytest.mark.parametrize("chapter", CHAPTERS, ids=lambda p: p.stem)
def test_chapter_has_lab_section(chapter):
    text = chapter.read_text(encoding="utf-8")
    assert "## 이 장의 실습" in text, f"{chapter.name} 에 「이 장의 실습」 절이 없습니다"


@pytest.mark.parametrize("chapter", CHAPTERS, ids=lambda p: p.stem)
def test_chapter_points_at_its_own_notebook(chapter):
    """장 번호와 노트북 번호가 같아야 합니다."""
    referenced = set(_notebooks_in(chapter.read_text(encoding="utf-8")))
    assert referenced, f"{chapter.name} 이 어떤 노트북도 가리키지 않습니다"

    number = chapter.stem[:4]          # ch07
    assert all(nb.startswith(number) for nb in referenced), (
        f"{chapter.name} 이 다른 장의 노트북을 가리킵니다: {sorted(referenced)}"
    )


@pytest.mark.parametrize("chapter", CHAPTERS, ids=lambda p: p.stem)
def test_referenced_notebooks_exist(chapter):
    for name in _notebooks_in(chapter.read_text(encoding="utf-8")):
        assert (LABS / f"{name}.ipynb").exists(), f"{name}.ipynb 가 없습니다"


@pytest.mark.parametrize("stem,target", sorted(GRADED.items()))
def test_graded_chapters_explain_the_checker(stem, target):
    """채점받는 장은 채울 파일과 채점 명령을 본문에 적어야 합니다."""
    chapter = next(p for p in CHAPTERS if p.stem == stem)
    text = chapter.read_text(encoding="utf-8")
    assert f"labs/{stem}.py" in text
    assert f"python labs/check.py {target}" in text


# --------------------------------------------------------------------------- #
# 노트북 자체
# --------------------------------------------------------------------------- #


def _notebooks() -> list[Path]:
    return sorted(LABS.glob("*.ipynb"))


def test_one_notebook_per_chapter():
    assert len(_notebooks()) == len(CHAPTERS)


@pytest.mark.parametrize("path", _notebooks(), ids=lambda p: p.stem)
def test_notebook_is_valid_and_clean(path):
    """출력이 남은 노트북은 커밋하지 않습니다. 차이가 읽히지 않고 용량이 붑니다."""
    nb = json.loads(path.read_text(encoding="utf-8"))
    assert nb["nbformat"] == 4

    dirty = [
        i for i, cell in enumerate(nb["cells"])
        if cell["cell_type"] == "code" and (cell.get("outputs") or cell.get("execution_count"))
    ]
    assert not dirty, f"{path.name} 의 셀 {dirty} 에 실행 결과가 남아 있습니다"


@pytest.mark.parametrize("path", _notebooks(), ids=lambda p: p.stem)
def test_notebook_bootstraps_the_path(path):
    """어디서 열어도 `smartmob` 을 찾을 수 있어야 합니다."""
    source = "".join(
        "".join(cell["source"])
        for cell in json.loads(path.read_text(encoding="utf-8"))["cells"]
        if cell["cell_type"] == "code"
    )
    assert 'if (p / "smartmob").is_dir()' in source


@pytest.mark.parametrize("stem", sorted(GRADED))
def test_graded_skeleton_sits_next_to_its_notebook(stem):
    assert (LABS / f"{stem}.py").exists()
    assert (LABS / f"{stem}.ipynb").exists()


# --------------------------------------------------------------------------- #
# 안내 문서
# --------------------------------------------------------------------------- #


def test_labs_readme_lists_every_notebook():
    readme = (LABS / "README.md").read_text(encoding="utf-8")
    for path in _notebooks():
        assert f"`{path.name}`" in readme, f"labs/README.md 표에 {path.name} 이 없습니다"


def test_check_module_covers_the_graded_three():
    import sys

    sys.path.insert(0, str(LABS))
    import check

    assert set(check.CHECKS) == set(GRADED.values())
