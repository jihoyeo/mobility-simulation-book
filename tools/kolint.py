#!/usr/bin/env python3
"""kolint — 교재 원고의 한국어 문체 검사기.

docs/STYLE.md 의 규칙 중 정규식으로 잡을 수 있는 것만 검사한다.
템플릿 반복(L7), 내용 없는 공정 서술(L8), 이식성 시험(S0)은 잡지 못한다.
**린터 통과는 잘 쓴 글이라는 뜻이 아니다.**

사용법:
    python tools/kolint.py ko/ intro.md
    python tools/kolint.py ko/ch01_why.md --summary
    python tools/kolint.py ko/ --baseline .kolint-baseline.json
    python tools/kolint.py ko/ --write-baseline .kolint-baseline.json

억제:
    <!-- kolint: disable=KO005,KO016 -->   다음 한 줄에만 적용
    <!-- kolint: disable-file=KO016 -->    파일 전체

표준 라이브러리만 사용한다.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ERROR, WARN, INFO = "error", "warn", "info"


@dataclass
class Finding:
    path: str
    line: int
    col: int
    level: str
    rule: str
    message: str

    @property
    def fingerprint(self) -> str:
        norm = re.sub(r"\s+", " ", self.message).strip()
        return f"{self.path}|{self.rule}|{norm}"

    def render(self) -> str:
        return f"{self.path}:{self.line}:{self.col}: {self.level:<5} [{self.rule}] {self.message}"


# --------------------------------------------------------------------------- #
# 마스킹 — 코드/링크/인용을 검사 대상에서 뺀다. 오프셋은 보존한다.
# --------------------------------------------------------------------------- #

_LANG_FENCE = re.compile(
    r"^([ \t]*)(```+|~~~+)[ \t]*([^\s{`]*)[^\n]*\n.*?^\1\2[ \t]*$",
    re.S | re.M,
)
_INLINE_CODE = re.compile(r"`[^`\n]+`")
_LINK_TARGET = re.compile(r"\]\([^)\n]*\)")
_BARE_URL = re.compile(r"https?://\S+")
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.S)
_BLOCKQUOTE = re.compile(r"^[ \t]*>.*$", re.M)
_DIRECTIVE_OPTS = re.compile(r"^[ \t]*:[a-zA-Z_-]+:.*$", re.M)


def _blank(match: re.Match) -> str:
    """매치를 같은 길이의 공백으로 바꾼다(줄바꿈은 유지)."""
    return "".join("\n" if ch == "\n" else " " for ch in match.group(0))


def mask(text: str) -> str:
    """산문이 아닌 부분을 지운다. 단, ```{note} 같은 MyST 디렉티브 본문은 남긴다."""

    def fence_repl(m: re.Match) -> str:
        info = m.group(3)
        if info.startswith("{"):  # ```{note} … 는 산문이므로 남긴다
            return m.group(0)
        return _blank(m)

    text = _FRONTMATTER.sub(_blank, text)
    text = _HTML_COMMENT.sub(_blank, text)
    text = _LANG_FENCE.sub(fence_repl, text)
    text = _INLINE_CODE.sub(_blank, text)
    text = _LINK_TARGET.sub(_blank, text)
    text = _BARE_URL.sub(_blank, text)
    text = _BLOCKQUOTE.sub(_blank, text)  # 인용은 원문이므로 검사하지 않는다
    text = _DIRECTIVE_OPTS.sub(_blank, text)
    return text


# --------------------------------------------------------------------------- #
# 규칙 정의
# --------------------------------------------------------------------------- #

# S1 — 합니다체가 아닌 종결
RE_PLAIN_ENDING = re.compile(r"(?<![가-힣])[가-힣]+(?<![니시])다(?=\s*[.!?]|\s*$)", re.M)
RE_PLAIN_PROPOSE = re.compile(r"(?<![가-힣])(?:[가-힣]*(?:해|아|어)\s?보자|하자|살펴보자)(?=\s*[.!?]|\s*$)", re.M)

# S3-L3 — 격상 어휘
ELEVATED = [
    "혁신적", "패러다임", "핵심 메시지", "게임 체인저", "무궁무진", "획기적",
    "시급", "대두", "부각", "중추적", "선도적", "새로운 지평", "각광",
]
RE_ELEVATED = re.compile("|".join(map(re.escape, ELEVATED)))

# S3-L5 — 근거 없는 예측
RE_PREDICTION = re.compile(
    r"(?:것으로|것이라)\s*(?:예상|전망|기대)|자리(?:를\s*)?잡을\s*것|이미\s*입증|널리\s*알려져"
)

# S3-L4 — 빈 마무리 문장
RE_EMPTY_CLOSER = re.compile(
    r"(?:수\s*있을\s*것입니다|다가갈\s*수\s*있습니다|중요합니다|필요합니다"
    r"|해야\s*합니다|고려해야\s*합니다|기대됩니다|요구됩니다)\s*[.!?]?\s*$"
)

# S4 — 강조
RE_BOLD = re.compile(r"\*\*(.+?)\*\*", re.S)
RE_UNDERLINE = re.compile(r"</?u>")

# S2.2 — 관형격 의 3연속
RE_THREE_UI = re.compile(r"\S+의\s+\S+의\s+\S+의")

# S2.3 — 접속·수식 부사
ADVERBS = [
    "또한", "더욱이", "나아가", "아울러", "이를 통해", "이러한 점에서", "종합적으로",
    "매우", "굉장히", "대단히", "상당히", "폭넓게", "효과적으로", "적극적으로",
    "다양한", "여러가지", "각종", "풍부한", "심도 있는",
]
RE_ADVERB = re.compile("|".join(map(re.escape, ADVERBS)))

# S2.4 — 문단 첫 어절 반복
RE_PARA_HEAD = re.compile(r"^(이러한|이는|이를|이와 같은)")

# S2.5 — 번역투
TRANSLATIONESE = ["되어진", "에 있어서", "로 하여금", "가지고 있다", "을 통해서", "를 통해서"]
RE_TRANSLATIONESE = re.compile("|".join(map(re.escape, TRANSLATIONESE)))

# S4 — admonition
RE_ADMONITION = re.compile(r"```+\{(\w+)\}|^:::+\{(\w+)\}", re.M)
BANNED_ADMONITIONS = {"important", "caution", "danger", "attention", "error", "hint"}
ALLOWED_ADMONITIONS = {"note", "tip", "warning", "admonition"}

# S7 — 오탈자·미완성
RE_TYPO = re.compile(r"및및|횟수수|도작지점|상요|~~~|TODO|TBD|FIXME|placeholder|\bXXX\b")

# S7 — raw HTML 레이아웃
RE_RAW_HTML = re.compile(r"<div\s+style=|<p\s+style=|<table\s+align=|<td>|<span\s+style=")

# S3-L6 — 대칭 장단점
RE_PROS = re.compile(r"\*\*장점\*\*")
RE_CONS = re.compile(r"\*\*단점\*\*")

# S8 — 출처 없는 수치
RE_NUMBER_CLAIM = re.compile(r"\d+\s*(?:%|배|퍼센트|만\s*명|억)")

# S7 — 그림
RE_IMAGE_DIRECTIVE = re.compile(r"```+\{image\}|^:::+\{image\}", re.M)
RE_FIGURE_NAME = re.compile(r"^\s*:name:\s*(\S+)\s*$", re.M)
RE_REF = re.compile(r"\{ref\}`([^`]+)`|\]\(#([^)]+)\)|\{numref\}`([^`]+)`")

SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _line_col(text: str, pos: int) -> tuple[int, int]:
    line = text.count("\n", 0, pos) + 1
    col = pos - (text.rfind("\n", 0, pos) + 1) + 1
    return line, col


# --------------------------------------------------------------------------- #
# 검사 본체
# --------------------------------------------------------------------------- #


def check_text(path: str, raw: str, line_offset_map=None) -> list[Finding]:
    """raw 는 마스킹 전 원문. line_offset_map 은 노트북용 (내부줄 -> 파일줄) 함수."""
    out: list[Finding] = []
    text = mask(raw)

    def emit(pos: int, level: str, rule: str, msg: str) -> None:
        line, col = _line_col(raw, pos)
        if line_offset_map is not None:
            line = line_offset_map(line)
        out.append(Finding(path, line, col, level, rule, msg))

    # KO001 — 합니다체가 아닌 종결
    for m in RE_PLAIN_ENDING.finditer(text):
        emit(m.start(), ERROR, "KO001", f"합니다체가 아닌 종결 '{m.group(0)}' — S1")
    for m in RE_PLAIN_PROPOSE.finditer(text):
        emit(m.start(), ERROR, "KO001", f"합니다체가 아닌 청유 '{m.group(0)}' — S1")

    # KO002 — 격상 어휘
    for m in RE_ELEVATED.finditer(text):
        emit(m.start(), ERROR, "KO002", f"격상 어휘 '{m.group(0)}' — S3-L3")

    # KO003 — 근거 없는 예측
    for m in RE_PREDICTION.finditer(text):
        emit(m.start(), ERROR, "KO003", f"근거 없는 예측 '{m.group(0).strip()}' — S3-L5")

    # KO004 — 빈 마무리 문장 (문단 단위)
    for para_start, para in _paragraphs(text):
        sents = [s for _, s in _sentences(para)]
        if not sents:
            continue
        last = sents[-1]
        if RE_EMPTY_CLOSER.search(last) and not re.search(r"[0-9`A-Za-z]", last):
            emit(para_start + para.rfind(last), WARN, "KO004",
                 f"빈 마무리 문장 — 삭제 검토: \"{last[:40]}\" — S3-L4")

    # KO005/KO006 — 볼드 예산
    body_len = max(len(re.sub(r"\s", "", text)), 1)
    bolds = list(RE_BOLD.finditer(text))
    budget = body_len * 3 / 1000
    if len(bolds) > budget:
        emit(bolds[0].start(), WARN, "KO005",
             f"볼드 {len(bolds)}개 / 본문 {body_len}자 "
             f"(1000자당 {len(bolds) * 1000 / body_len:.1f}개, 예산 3.0) — S4")
    for m in bolds:
        inner = m.group(1).strip()
        if len(inner) > 12:
            emit(m.start(), ERROR, "KO006", f"볼드 내부 {len(inner)}자 (12자 초과): \"{inner[:30]}\" — S4")

    # KO007 — 밑줄
    for m in RE_UNDERLINE.finditer(text):
        emit(m.start(), ERROR, "KO007", "<u> 는 쓰지 않는다 — S4")

    # KO008 — 문장 길이
    for para_start, para in _paragraphs(text):
        for offset, body in _sentences(para):
            n = len(body)
            if n > 120:
                emit(para_start + offset, ERROR, "KO008",
                     f"문장 {n}자 (120자 초과): \"{body[:35]}…\" — S2.1")
            elif n > 85:
                emit(para_start + offset, WARN, "KO008",
                     f"문장 {n}자 (85자 초과): \"{body[:35]}…\" — S2.1")

    # KO009 — 의 3연속
    for m in RE_THREE_UI.finditer(text):
        emit(m.start(), WARN, "KO009", f"관형격 '의' 3연속: \"{m.group(0)}\" — S2.2")

    # KO010 — 부사 밀도
    advs = list(RE_ADVERB.finditer(text))
    if len(advs) > body_len * 6 / 1000:
        emit(advs[0].start(), WARN, "KO010",
             f"접속·수식 부사 {len(advs)}개 / 본문 {body_len}자 (예산 6.0/1000자) — S2.3")

    # KO011 — 문단 첫 어절 반복
    streak, streak_start = 0, 0
    for para_start, para in _paragraphs(text):
        if RE_PARA_HEAD.match(para.strip()):
            if streak == 0:
                streak_start = para_start
            streak += 1
            if streak == 3:
                emit(streak_start, WARN, "KO011", "'이러한/이는/이를' 로 시작하는 문단 3연속 — S2.4")
        else:
            streak = 0

    # KO012 — 번역투
    for m in RE_TRANSLATIONESE.finditer(text):
        emit(m.start(), WARN, "KO012", f"번역투 '{m.group(0)}' — S2.5")

    # KO013/KO014 — admonition
    adms = [(m.start(), (m.group(1) or m.group(2)).lower()) for m in RE_ADMONITION.finditer(text)]
    n_sections = len(re.findall(r"^##\s", text, re.M)) or 1
    if len(adms) > n_sections:
        emit(adms[0][0], WARN, "KO013",
             f"admonition {len(adms)}개 / `##` 절 {n_sections}개 (절당 1개) — S4")
    for pos, name in adms:
        if name in BANNED_ADMONITIONS:
            emit(pos, ERROR, "KO014", f"금지 admonition '{{{name}}}' — note/tip/warning 만 쓴다 — S4")
        elif name not in ALLOWED_ADMONITIONS:
            emit(pos, WARN, "KO014", f"목록에 없는 admonition '{{{name}}}' — S4")

    # KO015 — 오탈자·미완성
    for m in RE_TYPO.finditer(raw):  # 코드 안의 TODO 도 잡는다
        emit(m.start(), ERROR, "KO015", f"오탈자 또는 미완성 표시 '{m.group(0)}' — S7")

    # KO016 — raw HTML 레이아웃
    for m in RE_RAW_HTML.finditer(raw):
        emit(m.start(), ERROR, "KO016", f"raw HTML 레이아웃 '{m.group(0)}' — S7")

    # KO017 — 대칭 장단점
    if RE_PROS.search(text) and RE_CONS.search(text):
        emit(RE_PROS.search(text).start(), WARN, "KO017",
             "대칭 장단점 불릿 — '언제 쓰는가 / 무엇이 막히는가' 로 다시 쓴다 — S3-L6")

    # KO018 — 출처 없는 수치
    for para_start, para in _paragraphs(text):
        if RE_NUMBER_CLAIM.search(para) and "{cite" not in para and "](http" not in raw:
            m = RE_NUMBER_CLAIM.search(para)
            emit(para_start + m.start(), INFO, "KO018",
                 f"출처 없는 수치 '{m.group(0)}' — 인용을 달거나 문장을 지운다 — S8")

    # KO019 — {image} 사용
    for m in RE_IMAGE_DIRECTIVE.finditer(raw):
        emit(m.start(), ERROR, "KO019", "{image} 대신 {figure} + :name: 을 쓴다 — S7")

    # KO020 — 참조 없는 그림
    refs = {g for m in RE_REF.finditer(raw) for g in m.groups() if g}
    for m in RE_FIGURE_NAME.finditer(raw):
        name = m.group(1)
        if name not in refs:
            emit(m.start(), WARN, "KO020", f"본문에서 참조하지 않는 그림 ':name: {name}' — S7")

    return out


def _paragraphs(text: str):
    pos = 0
    for chunk in re.split(r"\n\s*\n", text):
        yield pos, chunk
        pos += len(chunk) + 2


_LIST_MARKER = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+")
_SKIP_LINE = re.compile(r"^\s*(?:\||#|>|:[a-zA-Z_-]+:|```|~~~|<)")


def _sentences(block: str):
    """문단을 문장 단위로 자릅니다. ``(문단 내 오프셋, 문장)`` 을 냅니다.

    표의 행, 헤딩, 디렉티브 줄은 산문이 아니므로 건너뜁니다. 목록 항목은
    마커를 떼고 각각을 독립된 문장으로 봅니다. 이렇게 하지 않으면 표 하나가
    통째로 '한 문장 190자'로 잡힙니다.
    """
    line_start = 0
    for line in block.split("\n"):
        if not _SKIP_LINE.match(line) and line.strip():
            stripped = _LIST_MARKER.sub("", line)
            lead = len(line) - len(stripped)
            cursor = 0
            for sent in SENT_SPLIT.split(stripped):
                body = sent.strip()
                if body:
                    at = stripped.find(body, cursor)
                    yield line_start + lead + max(at, 0), body
                    cursor = max(at, 0) + len(body)
        line_start += len(line) + 1


# --------------------------------------------------------------------------- #
# 파일 읽기
# --------------------------------------------------------------------------- #

RE_DISABLE = re.compile(r"<!--\s*kolint:\s*disable=([A-Z0-9,\s]+?)\s*-->")
RE_DISABLE_FILE = re.compile(r"<!--\s*kolint:\s*disable-file=([A-Z0-9,\s]+?)\s*-->")


def _suppressions(raw: str) -> tuple[set[str], dict[int, set[str]]]:
    file_rules: set[str] = set()
    for m in RE_DISABLE_FILE.finditer(raw):
        file_rules |= {r.strip() for r in m.group(1).split(",") if r.strip()}
    line_rules: dict[int, set[str]] = {}
    for m in RE_DISABLE.finditer(raw):
        line = raw.count("\n", 0, m.start()) + 1
        rules = {r.strip() for r in m.group(1).split(",") if r.strip()}
        for offset in (1, 2):  # 다음 줄 또는 다음다음 줄(빈 줄 하나 허용)
            line_rules.setdefault(line + offset, set()).update(rules)
    return file_rules, line_rules


def check_markdown(path: Path) -> list[Finding]:
    raw = path.read_text(encoding="utf-8")
    findings = check_text(str(path).replace("\\", "/"), raw)
    return _apply_suppressions(raw, findings)


def check_notebook(path: Path) -> list[Finding]:
    raw = path.read_text(encoding="utf-8")
    nb = json.loads(raw)
    findings: list[Finding] = []
    search_from = 0
    for cell in nb.get("cells", []):
        if cell.get("cell_type") != "markdown":
            continue
        lines = cell.get("source", [])
        source = "".join(lines)
        if not source.strip():
            continue
        # 셀의 각 줄이 원본 JSON 몇 번째 줄에 있는지 찾는다(순차 탐색이라 단조 증가).
        json_lines: list[int] = []
        cursor = search_from
        for line in lines:
            # .ipynb 는 유니코드를 그대로 담기도 하고 \uXXXX 로 이스케이프하기도 한다. 둘 다 시도한다.
            pos, needle = -1, ""
            for ensure_ascii in (False, True):
                cand = json.dumps(line, ensure_ascii=ensure_ascii)[1:-1]
                if not cand:
                    continue
                found = raw.find(cand, cursor)
                if found != -1:
                    pos, needle = found, cand
                    break
            if pos == -1:
                json_lines.append(json_lines[-1] if json_lines else 1)
            else:
                json_lines.append(raw.count("\n", 0, pos) + 1)
                cursor = pos + len(needle)
        search_from = cursor

        def mapper(inner_line: int, _jl=json_lines) -> int:
            idx = min(max(inner_line - 1, 0), len(_jl) - 1)
            return _jl[idx]

        findings += check_text(str(path).replace("\\", "/"), source, mapper)
    return _apply_suppressions(raw, findings)


def _apply_suppressions(raw: str, findings: list[Finding]) -> list[Finding]:
    file_rules, line_rules = _suppressions(raw)
    kept = []
    for f in findings:
        if f.rule in file_rules:
            continue
        if f.rule in line_rules.get(f.line, set()):
            continue
        kept.append(f)
    return kept


def collect(targets: list[str]) -> list[Path]:
    paths: list[Path] = []
    for t in targets:
        p = Path(t)
        if p.is_dir():
            paths += sorted(p.rglob("*.md")) + sorted(p.rglob("*.ipynb"))
        elif p.suffix in {".md", ".ipynb"}:
            paths.append(p)
    return [p for p in paths if ".ipynb_checkpoints" not in p.parts]


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="교재 원고 한국어 문체 검사기")
    ap.add_argument("targets", nargs="+", help="검사할 파일 또는 디렉터리")
    ap.add_argument("--summary", action="store_true", help="파일별 요약표만 출력")
    ap.add_argument("--baseline", help="기존 위반 스냅샷 (여기 있는 것은 무시)")
    ap.add_argument("--write-baseline", help="현재 위반을 스냅샷으로 저장")
    ap.add_argument("--level", choices=[ERROR, WARN, INFO], default=INFO,
                    help="이 수준 이상만 출력 (기본 info)")
    args = ap.parse_args(argv)

    findings: list[Finding] = []
    files = collect(args.targets)
    for p in files:
        try:
            findings += check_notebook(p) if p.suffix == ".ipynb" else check_markdown(p)
        except Exception as exc:  # noqa: BLE001 — 한 파일 실패가 전체를 막지 않게
            print(f"{p}: 읽기 실패 — {exc}", file=sys.stderr)

    if args.write_baseline:
        Path(args.write_baseline).write_text(
            json.dumps(sorted(f.fingerprint for f in findings), ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        print(f"baseline 저장: {args.write_baseline} ({len(findings)}건)")
        return 0

    if args.baseline and Path(args.baseline).exists():
        known = set(json.loads(Path(args.baseline).read_text(encoding="utf-8")))
        findings = [f for f in findings if f.fingerprint not in known]

    order = {ERROR: 0, WARN: 1, INFO: 2}
    findings = [f for f in findings if order[f.level] <= order[args.level]]
    findings.sort(key=lambda f: (f.path, f.line, f.col))

    if args.summary:
        _print_summary(files, findings)
    else:
        for f in findings:
            print(f.render())

    n_err = sum(1 for f in findings if f.level == ERROR)
    n_warn = sum(1 for f in findings if f.level == WARN)
    print(f"\n{len(files)}개 파일, error {n_err}건, warn {n_warn}건")
    return 1 if n_err else 0


def _print_summary(files: list[Path], findings: list[Finding]) -> None:
    by_file: dict[str, list[Finding]] = {}
    for f in findings:
        by_file.setdefault(f.path, []).append(f)
    print(f"{'파일':<34}{'error':>7}{'warn':>7}{'info':>7}  주요 규칙")
    print("-" * 82)
    for p in files:
        key = str(p).replace("\\", "/")
        fs = by_file.get(key, [])
        counts = {lv: sum(1 for f in fs if f.level == lv) for lv in (ERROR, WARN, INFO)}
        top: dict[str, int] = {}
        for f in fs:
            top[f.rule] = top.get(f.rule, 0) + 1
        top_s = ", ".join(f"{r}×{n}" for r, n in sorted(top.items(), key=lambda x: -x[1])[:3])
        print(f"{key:<34}{counts[ERROR]:>7}{counts[WARN]:>7}{counts[INFO]:>7}  {top_s}")


if __name__ == "__main__":
    raise SystemExit(main())
