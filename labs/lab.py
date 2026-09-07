"""실습 노트북에서 쓰는 작은 도우미.

빈칸을 채웠는지, 채운 값이 맞는지 그 자리에서 확인합니다.

    from lab import todo, expect

    peak = None                       # 여기를 채웁니다
    todo("가장 붐빈 시각", peak)

    expect("노드 수", graph.n_nodes, 12_566)

`labs/check.py` 가 과제를 채점한다면, 이쪽은 수업 중에 한 칸씩 맞춰 보는 용도입니다.
"""

from __future__ import annotations

from typing import Any, Callable

__all__ = ["todo", "expect", "expect_between", "banner"]

_FILLED = "[v]"
_EMPTY = "[ ]"
_WRONG = "[x]"


def banner(title: str) -> None:
    """작은 제목줄. 확인이 여러 개일 때 묶어 줍니다."""
    print(title)
    print("-" * max(24, len(title) + 4))


def todo(label: str, value: Any, fmt: Callable[[Any], str] | None = None) -> None:
    """빈칸을 채웠는지만 봅니다. 값이 ``None`` 이면 아직 안 채운 것으로 봅니다."""
    if value is None:
        print(f"{_EMPTY} {label} — 아직 채우지 않았습니다")
        return
    print(f"{_FILLED} {label} = {fmt(value) if fmt else value}")


def expect(label: str, got: Any, want: Any, tol: float = 0.0) -> None:
    """채운 값이 맞는지 봅니다. 숫자는 ``tol`` 만큼의 오차를 허용합니다."""
    if got is None:
        print(f"{_EMPTY} {label} — 아직 채우지 않았습니다")
        return

    if isinstance(got, (int, float)) and isinstance(want, (int, float)):
        ok = abs(float(got) - float(want)) <= tol
        gap = f" (기대값 {want}, 차이 {abs(float(got) - float(want)):.4g})"
    else:
        ok = got == want
        gap = f" (기대값 {want})"

    print(f"{_FILLED if ok else _WRONG} {label} = {got}" + ("" if ok else gap))


def expect_between(label: str, got: Any, low: float, high: float) -> None:
    """값이 범위 안에 있는지 봅니다. 난수가 섞여 정답이 하나가 아닐 때 씁니다."""
    if got is None:
        print(f"{_EMPTY} {label} — 아직 채우지 않았습니다")
        return
    ok = low <= float(got) <= high
    print(f"{_FILLED if ok else _WRONG} {label} = {got}" + ("" if ok else f" (기대 범위 {low}~{high})"))
