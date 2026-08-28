"""matplotlib 한글 폰트.

윈도우는 맑은 고딕, macOS 는 애플 고딕, 리눅스(CI·Colab)는 나눔고딕을 씁니다.
한글 폰트를 쓰면 마이너스 부호가 네모로 깨지므로 `axes.unicode_minus` 도 끕니다.

    from smartmob.viz import use_korean_font
    use_korean_font()
"""

from __future__ import annotations

CANDIDATES = (
    "Malgun Gothic",      # Windows
    "AppleGothic",        # macOS
    "NanumGothic",        # Linux / Colab (apt install fonts-nanum)
    "NanumBarunGothic",
    "Noto Sans CJK KR",
    "Noto Sans KR",
)

_applied: str | None = None


def available_korean_fonts() -> list[str]:
    from matplotlib import font_manager

    installed = {f.name for f in font_manager.fontManager.ttflist}
    return [name for name in CANDIDATES if name in installed]


def use_korean_font(name: str | None = None, verbose: bool = False) -> str | None:
    """쓸 수 있는 한글 폰트를 골라 적용하고 이름을 돌려줍니다.

    하나도 없으면 경고만 하고 ``None`` 을 돌려줍니다. 그림은 그려지되 한글이 깨집니다.
    """
    global _applied
    import matplotlib

    matplotlib.rcParams["axes.unicode_minus"] = False

    picked = name or next(iter(available_korean_fonts()), None)
    if picked is None:
        print(
            "[smartmob] 한글 폰트를 찾지 못했습니다. 그림의 한글이 네모로 나옵니다.\n"
            "           Colab/Ubuntu: !apt-get install -y fonts-nanum  후 런타임 재시작"
        )
        return None

    matplotlib.rcParams["font.family"] = picked
    _applied = picked
    if verbose:
        print(f"[smartmob] 한글 폰트: {picked}")
    return picked


def applied_font() -> str | None:
    return _applied
