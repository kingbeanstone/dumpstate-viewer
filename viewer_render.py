# ──────────────────────────────────────────────────────────
# 필터링 / 렌더링 / 검색 이동 (LogViewerApp 의 믹스인)
#   하이브리드 렌더: 숨길 줄 많으면 '보이는 줄만 재렌더'(스크롤 매끈),
#                    적으면 '전체 베이스 + elide'(즉시 토글).
#   검색: Enter=다음 매치 / Shift+Enter=이전 매치 (VSCode식, 순환).
# ──────────────────────────────────────────────────────────
import dumpstate_parser as dp
from dumpstate_config import SECTION_COMPONENTS
from theme import FONT


class RenderMixin:
    # ── 에디터 글씨 확대/축소 ─────────────────────────────
    LOG_FONT_MIN = 6
    LOG_FONT_MAX = 40
    LOG_FONT_DEFAULT = 10

    def _zoom_log(self, delta):
        """Ctrl +/- : 로그 글씨 크기를 delta 만큼 키우거나 줄인다."""
        self._set_log_font(self._log_font_size + delta)
        return "break"

    def _reset_log_font(self):
        """Ctrl+0 : 기본 글씨 크기로 복귀."""
        self._set_log_font(self.LOG_FONT_DEFAULT)
        return "break"

    def _set_log_font(self, size):
        size = max(self.LOG_FONT_MIN, min(self.LOG_FONT_MAX, size))
        if size == self._log_font_size:
            return
        self._log_font_size = size
        self.log_text.config(font=(FONT, size))
        # 폰트를 지정한 태그(굵은 글씨)도 같은 크기로 맞춘다
        self.log_text.tag_config("component", font=(FONT, size, "bold"))
        self.log_text.tag_config("section_hdr", font=(FONT, size, "bold"))
        self.result_label.config(text=f"글씨 크기 {size}pt")

    # ── 필터 적용 ────────────────────────────────────────
    def apply_filter(self):
        if not self.rows:
            return
        active_sections = {s for s, v in self.section_vars.items() if v.get()}
        active_procs = [p for p, v in self.proc_vars.items() if v.get()]
        active_comps_map = {
            sec: {c for c, v in cvars.items() if v.get()}
            for sec, cvars in self.comp_vars.items()
        }
        # 컴포넌트가 하나라도 선택되면 '그 줄만 보기' 모드 → 컴포넌트 없는 섹션 숨김
        any_comp_selected = any(active_comps_map.values())
        # 검색/시간은 입력 중 값이 아니라 Enter로 확정된 값만 사용
        keyword = self._applied_search.lower()
        start_ms = dp.parse_user_time(self._applied_tstart, is_end=False)
        end_ms = dp.parse_user_time(self._applied_tend, is_end=True)

        # 1) 각 내용행의 표시 여부 계산 (Python, 빠름)
        visible = [False] * len(self.rows)
        shown = 0
        for idx, r in enumerate(self.rows):
            if r.header:
                continue
            if dp.Dump.content_visible(r, active_sections, active_procs,
                                       active_comps_map, keyword,
                                       any_comp_selected, start_ms, end_ms):
                visible[idx] = True
                shown += 1

        # 2) 분기: 숨길 줄이 많으면 그 줄만 재렌더(숨김 0 → 스크롤 매끈),
        #    적으면 전체 베이스 위에서 elide 토글(즉시 반영)
        hidden = len(self.rows) - shown
        if hidden > self.ELIDE_HIDDEN_LIMIT:
            if shown > 4000:
                self._busy()
            self._render_subset(visible, keyword, active_procs)
        else:
            if not self.widget_full:
                if len(self.rows) > 4000:
                    self._busy()
                self._render_full()
            self._apply_elide(visible)
            self._apply_highlights(visible, keyword, active_procs)

        self._shown = shown
        self._match_idx = -1          # 결과가 바뀌었으니 매치 순회 초기화
        self.log_text.tag_remove("cur_match", "1.0", "end")
        self.result_label.config(text=f"{shown}줄")

    def _busy(self):
        self.result_label.config(text="필터 적용 중…")
        self.root.update_idletasks()

    # ── 검색/시간 Enter 처리 ─────────────────────────────
    def _on_search(self, step):
        """검색어가 바뀌었으면 재필터, 그 후 매치 이동. step=+1 다음 / -1 이전."""
        if self.search_var.get() != self._applied_search:
            self._applied_search = self.search_var.get()
            self.apply_filter()       # _match_idx = -1 로 리셋됨
        self._goto_match(step)
        return "break"

    def _on_time_enter(self):
        self._applied_tstart = self.time_filter.get_start()
        self._applied_tend = self.time_filter.get_end()
        self.apply_filter()
        return "break"

    def _goto_match(self, step):
        """현재 화면의 검색 강조(search_hl) 매치를 순환 이동. 현재 매치는 cur_match로
        강조 + 화면 스크롤. step=+1 다음 / -1 이전."""
        ranges = self.log_text.tag_ranges("search_hl")
        total = len(ranges) // 2
        if total == 0:
            self.result_label.config(text=f"{self._shown}줄  ·  매치 없음")
            return
        if self._match_idx == -1:
            self._match_idx = 0 if step > 0 else total - 1
        else:
            self._match_idx = (self._match_idx + step) % total
        s = ranges[self._match_idx * 2]
        e = ranges[self._match_idx * 2 + 1]
        self.log_text.tag_remove("cur_match", "1.0", "end")
        self.log_text.tag_add("cur_match", s, e)
        self.log_text.see(e)
        self.log_text.see(s)
        self.result_label.config(
            text=f"{self._shown}줄  ·  {self._match_idx + 1}/{total}")

    # ── 전체 행 1회 삽입 + 정적 태그 (elide 모드 전제) ─────
    def _render_full(self):
        """인식된 섹션 줄 '전체'를 Text에 삽입하고 필터 무관 정적 태그(섹션 헤더
        색, 컴포넌트 TAG 색)를 적용. 넓은 결과를 elide로 토글하기 위한 베이스."""
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        big = "".join(
            (f"════════ {r.section} ════════" if r.header else r.text) + "\n"
            for r in self.rows
        )
        self.log_text.insert("1.0", big)
        for idx, r in enumerate(self.rows):
            ln = idx + 1
            if r.header:
                self.log_text.tag_add("section_hdr", f"{ln}.0", f"{ln + 1}.0")
            elif r.section in SECTION_COMPONENTS and r.logtag:
                col = r.text.find(r.logtag)
                if col >= 0:
                    self.log_text.tag_add(
                        "component", f"{ln}.{col}", f"{ln}.{col + len(r.logtag)}")
        self.log_text.config(state="disabled")
        self.widget_full = True

    # ── 보이는 줄만 새로 삽입 (no elide → 스크롤 매끈) ─────
    def _render_subset(self, visible, keyword, active_procs):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")

        parts = []
        meta = []          # (줄번호, row)
        hdr_lines = []
        ln = 1
        prev = None
        for idx, r in enumerate(self.rows):
            if r.header or not visible[idx]:
                continue
            if r.section != prev:
                parts.append(f"════════ {r.section} ════════")
                hdr_lines.append(ln)
                ln += 1
                prev = r.section
            parts.append(r.text)
            meta.append((ln, r))
            ln += 1
        self.log_text.insert("1.0", "\n".join(parts) + ("\n" if parts else ""))

        for hl in hdr_lines:
            self.log_text.tag_add("section_hdr", f"{hl}.0", f"{hl + 1}.0")
        for ln, r in meta:
            if r.section in SECTION_COMPONENTS and r.logtag:
                col = r.text.find(r.logtag)
                if col >= 0:
                    self.log_text.tag_add(
                        "component", f"{ln}.{col}", f"{ln}.{col + len(r.logtag)}")
            if keyword:
                self._highlight_all(r.text_lower, keyword, ln, "search_hl")
            for p in active_procs:
                self._highlight_all(r.text, p, ln, "proc_hl")

        self.log_text.config(state="disabled")
        self.widget_full = False
        self.log_text.yview_moveto(0.0)

    # ── 전체 베이스 위에서 숨길 구간만 elide ───────────────
    def _apply_elide(self, visible):
        # 헤더는 그 섹션에 보이는 내용이 1개라도 있으면 표시
        shown = list(visible)
        last_header = None
        header_done = False
        for idx, r in enumerate(self.rows):
            if r.header:
                last_header = idx
                header_done = False
            elif visible[idx] and last_header is not None and not header_done:
                shown[last_header] = True
                header_done = True

        self.log_text.config(state="normal")
        self.log_text.tag_remove("hidden", "1.0", "end")
        run_start = None
        for idx in range(len(self.rows)):
            if not shown[idx]:
                if run_start is None:
                    run_start = idx
            elif run_start is not None:
                self.log_text.tag_add("hidden", f"{run_start + 1}.0", f"{idx + 1}.0")
                run_start = None
        if run_start is not None:
            self.log_text.tag_add(
                "hidden", f"{run_start + 1}.0", f"{len(self.rows) + 1}.0")
        self.log_text.config(state="disabled")

    # ── 동적 강조(검색어/프로세스) — 전체 베이스의 보이는 줄 ──
    def _apply_highlights(self, visible, keyword, active_procs):
        self.log_text.config(state="normal")
        self.log_text.tag_remove("search_hl", "1.0", "end")
        self.log_text.tag_remove("proc_hl", "1.0", "end")
        if keyword or active_procs:
            for idx, r in enumerate(self.rows):
                if r.header or not visible[idx]:
                    continue
                ln = idx + 1
                if keyword:
                    self._highlight_all(r.text_lower, keyword, ln, "search_hl")
                for p in active_procs:
                    self._highlight_all(r.text, p, ln, "proc_hl")
        self.log_text.config(state="disabled")

    def _highlight_all(self, haystack, needle, ln, tag):
        if not needle:
            return
        start = 0
        n = len(needle)
        while True:
            col = haystack.find(needle, start)
            if col < 0:
                break
            self.log_text.tag_add(tag, f"{ln}.{col}", f"{ln}.{col + n}")
            start = col + n
