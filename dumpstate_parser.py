# ──────────────────────────────────────────────────────────
# 덤프스테이트 파싱 로직 (tkinter 의존 없음 → 단독 테스트 가능)
# ──────────────────────────────────────────────────────────
import re

# logcat threadtime 한 줄에서 우선순위 레벨 뒤의 TAG 추출
#  예) "06-06 12:34:56.789  1234  5678 I ActivityManager: msg"  -> "ActivityManager"
#      "06-06 12:34:56.789  1000  1234 5678 I  GOS: msg" (uid 포함)  -> "GOS"
LOGCAT_TAG_RE = re.compile(r"\s[VDIWEF]\s+(.+?)\s*:\s")

# 줄 맨 앞의 타임스탬프(선택적 MM-DD) 뒤 HH:MM:SS(.mmm) 추출
TIME_RE = re.compile(r"^\s*(?:\d{2}-\d{2}\s+)?(\d{1,2}):(\d{2}):(\d{2})(?:\.(\d{1,3}))?")
# 사용자 입력 시간 (H, H:M, H:M:S, H:M:S.mmm 등 부분 허용)
USER_TIME_RE = re.compile(r"^\s*(\d{1,2})(?::(\d{1,2}))?(?::(\d{1,2}))?(?:\.(\d{1,3}))?\s*$")


def _to_ms(h, m, s, ms):
    return ((h * 60 + m) * 60 + s) * 1000 + ms


def parse_line_time(line):
    """줄 맨 앞 타임스탬프를 '자정 이후 ms'로 반환. 없으면 None."""
    m = TIME_RE.match(line)
    if not m:
        return None
    ms = int(m.group(4).ljust(3, "0")) if m.group(4) else 0
    return _to_ms(int(m.group(1)), int(m.group(2)), int(m.group(3)), ms)


def parse_user_time(text, is_end):
    """사용자가 입력한 시간을 ms로. 부분 입력은 시작이면 0, 끝이면 최대값으로 패딩.
    빈칸/형식오류는 None(=제한 없음)."""
    if not text or not text.strip():
        return None
    m = USER_TIME_RE.match(text)
    if not m:
        return None
    fill = (59, 59, 999) if is_end else (0, 0, 0)
    h = int(m.group(1))
    mi = int(m.group(2)) if m.group(2) is not None else fill[0]
    se = int(m.group(3)) if m.group(3) is not None else fill[1]
    ms = int(m.group(4).ljust(3, "0")) if m.group(4) is not None else fill[2]
    return _to_ms(h, mi, se, ms)


# 진짜 섹션 헤더: 대시 정확히 6개 + 공백 + 이름  (+ 선택적 꼬리 대시)
#   매칭됨 : "------ SYSTEM LOG (logcat -d) ------",  "------ PROCESS TIMES"
#   제외됨 : "---------SurfaceFlinger Effects---------"  (대시 뒤 공백 없음)
#            "--------- beginning of system"           (대시 7개 이상)
HEADER_RE = re.compile(r"^------\s+(.+?)(?:\s+-{3,})?\s*$")


def _header_inner(line):
    """진짜 헤더면 '이름 (...)' 부분 문자열, 아니면 None."""
    m = HEADER_RE.match(line.strip())
    return m.group(1).strip() if m else None


def section_name_from_header(line):
    """'------ NAME (...) ------' 형태면 NAME 반환, 헤더가 아니면 None."""
    inner = _header_inner(line)
    if not inner or "was the duration of" in inner:
        return None
    return inner.split("(")[0].strip()


def is_section_end(line):
    """'------ X.Xs was the duration of 'NAME' ------' 같은 섹션 종료라인이면 True."""
    inner = _header_inner(line)
    return bool(inner) and "was the duration of" in inner


def normalize(name):
    return re.sub(r"\s+", " ", name.upper()).strip()


def match_section(name, sections):
    """추출된 헤더명을 알려진 섹션명과 '정확히' 매칭."""
    norm = normalize(name)
    for sec in sections:
        if norm == normalize(sec):
            return sec
    return None


def logcat_tag(line):
    m = LOGCAT_TAG_RE.search(line)
    return m.group(1).strip() if m else None


def tag_matches(tag, comps):
    """태그의 '첫 콜론 앞 부분'이 선택된 컴포넌트와 일치하면 True.
    - 'SurfaceComposerClient'      -> 'SurfaceComposerClient' 매칭
    - 'SDHMS:battery'(서브태그)     -> 'SDHMS' 매칭
    - 'LayerHistory'               -> 'Layer' 에 안 걸림 (첫 부분이 LayerHistory)
    """
    return tag.split(":", 1)[0] in comps


class Row:
    """화면에 표시되는 한 줄(헤더 줄 또는 내용 줄)."""
    __slots__ = ("section", "header", "text", "text_lower", "logtag", "tms")

    def __init__(self, section, header, text="", text_lower="", logtag=None, tms=None):
        self.section = section
        self.header = header
        self.text = text
        self.text_lower = text_lower
        self.logtag = logtag
        self.tms = tms          # 타임스탬프(자정 이후 ms), 없으면 None


class Dump:
    """덤프 파일 1개를 로드/파싱해서 줄별 섹션 정보를 보관."""

    def __init__(self):
        self.lines = []            # 원본 줄 전체
        self.line_sections = []    # 각 줄이 속한 섹션명(미인식/없으면 None)
        self.discovered = []       # 파일에서 발견된 모든 헤더 (raw_name, matched|None) - 중복 제거, 순서 유지

    def load(self, path):
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            self.lines = f.readlines()

    def parse(self, sections, progress=None):
        self.line_sections = []
        self.discovered = []
        seen = set()
        current = None
        total = len(self.lines)
        step = max(1, total // 200)        # 진행 콜백 ~200회로 제한
        for i, line in enumerate(self.lines):
            name = section_name_from_header(line)
            if name is not None:
                current = match_section(name, sections)
                if name not in seen:
                    seen.add(name)
                    self.discovered.append((name, current))
            elif is_section_end(line):
                current = None  # 섹션 종료라인에서만 리셋
            # 그 외(대시로 시작하지만 헤더가 아닌 줄 등)는 current 유지
            self.line_sections.append(current)
            if progress and i % step == 0:
                progress(i, total)
        if progress and total:
            progress(total, total)

    def section_counts(self, sections):
        counts = {s: 0 for s in sections}
        for sec in self.line_sections:
            if sec in counts:
                counts[sec] += 1
        return counts

    def component_counts(self, section, components):
        counts = {c: 0 for c in components}
        for line, sec in zip(self.lines, self.line_sections):
            if sec != section:
                continue
            tag = logcat_tag(line)
            if tag is None:
                continue
            seg = tag.split(":", 1)[0]   # 첫 콜론 앞 부분 (필터 규칙과 동일)
            if seg in counts:
                counts[seg] += 1
        return counts

    def process_count(self, name):
        """인식된 섹션 안에서 name 을 포함하는 줄 수."""
        return sum(1 for line, sec in zip(self.lines, self.line_sections)
                   if sec is not None and name in line)

    def section_lines(self, name):
        """주어진 섹션에 속한 원본 줄들을 순서대로 반환."""
        return [line for line, sec in zip(self.lines, self.line_sections)
                if sec == name]

    def build_display(self, sections, progress=None):
        """화면 표시용 행 리스트를 1회 생성(파일 순서).

        반환: Row 리스트. 인식된 섹션 줄만 포함하며, 섹션이 시작될 때마다
        합성 헤더 행(Row.header=True)을 끼운다. 내용 행에는 text/text_lower/
        logtag(=logcat_tag 캐시)를 미리 담아 토글 때 재계산을 피한다.
        """
        rows = []
        prev_sec = None
        total = len(self.lines)
        step = max(1, total // 200)        # 진행 콜백 ~200회로 제한
        for i, (line, sec) in enumerate(zip(self.lines, self.line_sections)):
            if progress and i % step == 0:
                progress(i, total)
            if sec is None:
                continue
            if sec != prev_sec:
                rows.append(Row(section=sec, header=True))
                prev_sec = sec
            text = line.rstrip("\n")
            rows.append(Row(section=sec, header=False, text=text,
                            text_lower=text.lower(), logtag=logcat_tag(line),
                            tms=parse_line_time(line)))
        if progress and total:
            progress(total, total)
        return rows

    @staticmethod
    def content_visible(row, active_sections, active_procs,
                        active_comps_map, keyword_lower, any_comp_selected=False,
                        start_ms=None, end_ms=None):
        """내용 행 하나가 현재 필터 조건에서 보여야 하는지 판정.

        active_sections   : 체크된 섹션 set
        active_procs      : 체크된 프로세스명 list (OR, 비면 제한 없음)
        active_comps_map  : {섹션: 체크된 컴포넌트 set}
        keyword_lower     : 검색어(소문자), 비면 제한 없음
        any_comp_selected : 어느 섹션에서든 컴포넌트가 하나라도 선택됐는지.
            True면 '컴포넌트 선택 = 그 줄만 보기' 모드 → 선택된 컴포넌트가 없는
            섹션(예: DUMPSYS CRITICAL)은 통째로 숨기고, 컴포넌트가 있는 섹션은
            그 컴포넌트와 정확히 일치하는 줄만 보인다.
        """
        if row.section not in active_sections:
            return False
        if active_procs and not any(p in row.text for p in active_procs):
            return False
        if any_comp_selected:
            active_comps = active_comps_map.get(row.section)
            if not active_comps:
                return False   # 선택된 컴포넌트가 없는 섹션 → 숨김
            if not row.logtag or not tag_matches(row.logtag, active_comps):
                return False
        if keyword_lower and keyword_lower not in row.text_lower:
            return False
        if start_ms is not None or end_ms is not None:
            if row.tms is None:                       # 타임스탬프 없는 줄은 숨김
                return False
            if start_ms is not None and row.tms < start_ms:
                return False
            if end_ms is not None and row.tms > end_ms:
                return False
        return True


# ──────────────────────────────────────────────────────────
# VM TRACES (ANR) 파싱 — ART/Dalvik 스레드 덤프를 프로세스▸스레드 구조로
# ──────────────────────────────────────────────────────────
#  "----- pid 12345 at 2024-... -----"  프로세스 시작
#  "Cmd line: com.example.app"          프로세스 이름
#  "DALVIK THREADS (N):"                스레드 목록 시작
#  '"main" prio=5 tid=1 Native'         스레드 헤더(열 0의 따옴표)
#    | group=... / native: ... / at ...  들여쓴 메타·스택 프레임
#  "----- end 12345 -----"              프로세스 끝
PROC_START_RE = re.compile(r"^-----\s+pid\s+(\d+)\s+at\s+(.+?)\s+-----\s*$")
PROC_END_RE = re.compile(r"^-----\s+end\s+(\d+)\s+-----\s*$")
CMDLINE_RE = re.compile(r"^Cmd line:\s*(.+)$")
THREAD_RE = re.compile(r'^"(?P<name>.*)"\s+(?P<rest>\S.*)$')
THREAD_TID_RE = re.compile(r"\btid=(\d+)\b")


class AnrThread:
    __slots__ = ("name", "tid", "state", "lines")

    def __init__(self, name, tid, state, lines):
        self.name = name
        self.tid = tid
        self.state = state
        self.lines = lines      # 헤더 + 메타 + 스택 프레임 전체(표시용)


class AnrProcess:
    __slots__ = ("pid", "name", "header_lines", "threads")

    def __init__(self, pid, name, header_lines, threads):
        self.pid = pid
        self.name = name                # Cmd line (없으면 "pid N")
        self.header_lines = header_lines  # DALVIK THREADS 이전 정보(빌드/클래스로더 등)
        self.threads = threads


def parse_anr_traces(lines):
    """VM TRACES 섹션 줄들을 AnrProcess 리스트로 파싱."""
    procs = []
    cur_proc = None
    cur_thread = None
    for raw in lines:
        line = raw.rstrip("\n")

        m = PROC_START_RE.match(line)
        if m:
            cur_proc = AnrProcess(pid=m.group(1), name=None,
                                  header_lines=[line], threads=[])
            procs.append(cur_proc)
            cur_thread = None
            continue

        if cur_proc is None:
            continue                    # 첫 pid 라인 전(섹션 헤더/전문)은 무시

        if PROC_END_RE.match(line):
            cur_thread = None
            continue

        th = THREAD_RE.match(line)
        if th:                          # 열 0의 따옴표 → 스레드 헤더
            rest = th.group("rest")
            tidm = THREAD_TID_RE.search(rest)
            toks = rest.split()
            cur_thread = AnrThread(
                name=th.group("name"),
                tid=(tidm.group(1) if tidm else ""),
                state=(toks[-1] if toks else ""),
                lines=[line])
            cur_proc.threads.append(cur_thread)
            continue

        if cur_thread is not None:
            cur_thread.lines.append(line)
        else:                           # 스레드 시작 전 줄 → 프로세스 헤더
            cur_proc.header_lines.append(line)
            cm = CMDLINE_RE.match(line)
            if cm and cur_proc.name is None:
                cur_proc.name = cm.group(1).strip()

    # 정리: 이름 폴백 + 스레드별 끝쪽 빈 줄 제거
    for p in procs:
        if not p.name:
            p.name = f"pid {p.pid}"
        for t in p.threads:
            while t.lines and not t.lines[-1].strip():
                t.lines.pop()
    return procs
