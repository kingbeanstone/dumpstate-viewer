# ──────────────────────────────────────────────────────────
# 좌측 사이드바 + 진단 팝업 (LogViewerApp 의 믹스인)
#   섹션/프로세스/컴포넌트 체크박스 빌드, 카운트 갱신, 헤더 보기.
# self.* (sidebar, _p, dump, *_vars, *_count_lbls, apply_filter ...) 를 사용한다.
# ──────────────────────────────────────────────────────────
import tkinter as tk

from theme import (BG, PANEL, BORDER, ACCENT, ACCENT2, TEXT, TEXT_DIM,
                   TEXT_SEL, CHIP_BG, FONT)
from dumpstate_config import SECTIONS, SECTION_COMPONENTS
from storage import read_json, write_json


class SidebarMixin:
    # ── 그룹: 섹션 ──────────────────────────────────────
    def _build_sections_group(self):
        self._group_header("SECTIONS",
                           on_cmd=lambda: self._set_all(self.section_vars, True),
                           off_cmd=lambda: self._set_all(self.section_vars, False))
        for sec in SECTIONS:
            var = tk.BooleanVar(value=True)
            self.section_vars[sec] = var
            self.section_count_lbls[sec] = self._checkbox_row(sec, var)

    # ── 그룹: 프로세스명 ─────────────────────────────────
    def _build_process_group(self):
        p = self._p
        self._divider()
        self._group_header("PROCESS NAMES")
        add_row = tk.Frame(self.sidebar, bg=PANEL)
        add_row.pack(fill="x", padx=p(12), pady=p((0, 6)))
        self.proc_entry_var = tk.StringVar()
        ent = tk.Entry(add_row, textvariable=self.proc_entry_var, bg=CHIP_BG, fg=TEXT,
                       insertbackground=TEXT, relief="flat", font=(FONT, 9))
        ent.pack(side="left", fill="x", expand=True, ipady=p(3))
        ent.bind("<Return>", lambda e: self._add_process())
        tk.Button(add_row, text="＋", bg=ACCENT, fg=TEXT_SEL, relief="flat",
                  font=(FONT, 10, "bold"), padx=p(8), cursor="hand2",
                  activebackground="#3a7ae0", command=self._add_process).pack(
            side="left", padx=p((4, 0)))
        self.proc_list_frame = tk.Frame(self.sidebar, bg=PANEL)
        self.proc_list_frame.pack(fill="x")

    # ── 그룹: 섹션별 컴포넌트 (탭으로 섹션 전환) ──────────
    def _build_components_groups(self):
        p = self._p
        self._load_saved_components()      # 사용자 추가 컴포넌트 + 체크상태 복원
        # 모든 섹션의 컴포넌트 BooleanVar 를 미리 만든다(보이는 탭과 무관하게 필터 동작)
        for section in SECTION_COMPONENTS:
            self.comp_vars[section] = {}
            checked = self._saved_checked.get(section, set())
            for comp in self._comp_list(section):
                self.comp_vars[section][comp] = tk.BooleanVar(value=comp in checked)

        keys = list(SECTION_COMPONENTS.keys())
        if not keys:
            return
        self._comp_active = keys[0]

        self._divider()
        self._group_header("COMPONENTS",
                           on_cmd=lambda: self._set_all_comps(True),
                           off_cmd=lambda: self._set_all_comps(False))

        # 섹션 전환 탭 (누르면 그 섹션의 컴포넌트 리스트로 바뀜)
        tabbar = tk.Frame(self.sidebar, bg=PANEL)
        tabbar.pack(fill="x", padx=p(12), pady=p((0, 6)))
        self.comp_tab_btns = {}
        for sec in keys:
            b = tk.Button(tabbar, text=sec, relief="flat", cursor="hand2",
                          font=(FONT, 8, "bold"), padx=p(8), pady=p(3),
                          activebackground=ACCENT, activeforeground=TEXT_SEL,
                          command=lambda s=sec: self._select_comp_section(s))
            b.pack(side="left", padx=p((0, 4)))
            self.comp_tab_btns[sec] = b

        # 컴포넌트 추가 입력칸 (현재 선택된 탭의 섹션에 추가됨)
        add_row = tk.Frame(self.sidebar, bg=PANEL)
        add_row.pack(fill="x", padx=p(12), pady=p((0, 4)))
        self.comp_entry_var = tk.StringVar()
        ent = tk.Entry(add_row, textvariable=self.comp_entry_var, bg=CHIP_BG, fg=TEXT,
                       insertbackground=TEXT, relief="flat", font=(FONT, 9))
        ent.pack(side="left", fill="x", expand=True, ipady=p(3))
        ent.bind("<Return>", lambda e: self._add_component())
        tk.Button(add_row, text="＋", bg=ACCENT, fg=TEXT_SEL, relief="flat",
                  font=(FONT, 10, "bold"), padx=p(8), cursor="hand2",
                  activebackground="#3a7ae0", command=self._add_component).pack(
            side="left", padx=p((4, 0)))
        tk.Label(self.sidebar, text="아무것도 체크 안하면 전체 표시", bg=PANEL,
                 fg=TEXT_DIM, font=(FONT, 7), anchor="w").pack(
            fill="x", padx=p(12), pady=p((0, 4)))

        # 선택된 섹션의 컴포넌트 체크박스가 그려지는 패널
        self.comp_panel = tk.Frame(self.sidebar, bg=PANEL)
        self.comp_panel.pack(fill="x")
        self._render_comp_panel()

    def _comp_list(self, section):
        """섹션의 컴포넌트 = 설정값 + 사용자 추가(중복 제거, 추가분은 뒤에)."""
        base = list(SECTION_COMPONENTS.get(section, []))
        for c in self.custom_comps.get(section, []):
            if c not in base:
                base.append(c)
        return base

    def _select_comp_section(self, sec):
        """탭 클릭 → 그 섹션의 컴포넌트 리스트로 전환."""
        if sec == self._comp_active:
            return
        self._comp_active = sec
        self._render_comp_panel()

    def _render_comp_panel(self):
        """현재 선택된 섹션의 컴포넌트 체크박스 목록을 다시 그린다."""
        p = self._p
        for w in self.comp_panel.winfo_children():
            w.destroy()
        sec = self._comp_active
        custom = set(self.custom_comps.get(sec, []))
        for comp in self._comp_list(sec):
            var = self.comp_vars[sec][comp]
            row = tk.Frame(self.comp_panel, bg=PANEL)
            row.pack(fill="x", padx=p(8), pady=p(2))
            tk.Checkbutton(row, text=comp, variable=var, bg=PANEL, fg=TEXT,
                           selectcolor=CHIP_BG, activebackground=PANEL,
                           activeforeground=TEXT_SEL, font=(FONT, 9),
                           anchor="w", relief="flat",
                           command=self._on_comp_toggle).pack(
                side="left", fill="x", expand=True)
            cnt = self.comp_counts.get((sec, comp))
            tk.Label(row, text="" if cnt is None else str(cnt), bg=PANEL,
                     fg=TEXT_DIM, font=(FONT, 8)).pack(side="right", padx=p((2, 2)))
            if comp in custom:        # 사용자 추가 컴포넌트만 삭제(✕) 가능
                tk.Button(row, text="✕", bg=PANEL, fg=ACCENT2, relief="flat",
                          font=(FONT, 8), cursor="hand2", activebackground=PANEL,
                          activeforeground="#ff6b6b",
                          command=lambda c=comp: self._remove_component(c)).pack(
                    side="right")
        self._update_comp_tabs()

    def _update_comp_tabs(self):
        for sec, b in self.comp_tab_btns.items():
            if sec == self._comp_active:
                b.config(bg=ACCENT, fg=TEXT_SEL)
            else:
                b.config(bg=CHIP_BG, fg=TEXT_DIM)

    def _set_all_comps(self, value):
        for v in self.comp_vars[self._comp_active].values():
            v.set(value)
        self._save_components()
        self.apply_filter()

    def _on_comp_toggle(self):
        self._save_components()
        self.apply_filter()

    def _add_component(self):
        name = self.comp_entry_var.get().strip()
        self.comp_entry_var.set("")
        sec = self._comp_active
        if not name or name in self.comp_vars.get(sec, {}):
            return
        self.custom_comps.setdefault(sec, []).append(name)
        self.comp_vars[sec][name] = tk.BooleanVar(value=False)
        if self.dump.lines:           # 새 컴포넌트의 줄 수 계산
            cc = self.dump.component_counts(sec, [name])
            self.comp_counts[(sec, name)] = cc.get(name, 0)
        self._save_components()
        self._render_comp_panel()
        self.apply_filter()

    def _remove_component(self, name):
        sec = self._comp_active
        lst = self.custom_comps.get(sec, [])
        if name in lst:
            lst.remove(name)
        self.comp_vars.get(sec, {}).pop(name, None)
        self.comp_counts.pop((sec, name), None)
        self._save_components()
        self._render_comp_panel()
        self.apply_filter()

    # ── 컴포넌트 저장/복원 (세션 간 유지) ─────────────────
    def _load_saved_components(self):
        self.custom_comps = {}
        self._saved_checked = {}
        data = read_json(self._comp_store_path, {})
        if not isinstance(data, dict):
            return
        for section, entry in data.items():
            if isinstance(entry, dict):
                self.custom_comps[section] = list(entry.get("custom", []))
                self._saved_checked[section] = set(entry.get("checked", []))

    def _save_components(self):
        data = {}
        for section in SECTION_COMPONENTS:
            checked = [c for c, v in self.comp_vars.get(section, {}).items() if v.get()]
            custom = list(self.custom_comps.get(section, []))
            if checked or custom:
                data[section] = {"custom": custom, "checked": checked}
        write_json(self._comp_store_path, data)

    # ── 공통 UI 헬퍼 ────────────────────────────────────
    def _group_header(self, title, on_cmd=None, off_cmd=None):
        p = self._p
        hdr = tk.Frame(self.sidebar, bg=PANEL)
        hdr.pack(fill="x", padx=p(12), pady=p((14, 6)))
        tk.Label(hdr, text=title, bg=PANEL, fg=TEXT_DIM,
                 font=(FONT, 10, "bold")).pack(side="left")
        if off_cmd:
            tk.Button(hdr, text="OFF", bg=CHIP_BG, fg=TEXT, relief="flat",
                      font=(FONT, 9), padx=p(6), cursor="hand2",
                      command=off_cmd).pack(side="right")
        if on_cmd:
            tk.Button(hdr, text="ON", bg=CHIP_BG, fg=TEXT, relief="flat",
                      font=(FONT, 9), padx=p(6), cursor="hand2",
                      command=on_cmd).pack(side="right", padx=p((0, 4)))

    def _checkbox_row(self, name, var):
        p = self._p
        row = tk.Frame(self.sidebar, bg=PANEL)
        row.pack(fill="x", padx=p(8), pady=p(2))
        tk.Checkbutton(row, text=name, variable=var, bg=PANEL, fg=TEXT,
                       selectcolor=CHIP_BG, activebackground=PANEL,
                       activeforeground=TEXT_SEL, font=(FONT, 9),
                       anchor="w", relief="flat", command=self.apply_filter).pack(
            side="left", fill="x", expand=True)
        cnt = tk.Label(row, text="", bg=PANEL, fg=TEXT_DIM, font=(FONT, 8))
        cnt.pack(side="right", padx=p((2, 4)))
        return cnt

    def _divider(self):
        tk.Frame(self.sidebar, bg=BORDER, height=self._p(1)).pack(
            fill="x", pady=self._p((10, 0)))

    def _set_all(self, var_dict, value):
        for v in var_dict.values():
            v.set(value)
        self.apply_filter()

    def _scroll_sidebar(self, event):
        self.sidebar_canvas.yview_scroll(int(-event.delta / 120), "units")

    # ── 프로세스명 저장/복원 (세션 간 유지) ───────────────
    def _load_saved_processes(self):
        """앱 폴더의 JSON에서 프로세스명+체크상태를 읽어 proc_vars 복원."""
        data = read_json(self._proc_store_path, {})
        # 구버전 호환: 리스트면 전부 체크된 것으로 취급
        if isinstance(data, list):
            data = {name: True for name in data}
        if not isinstance(data, dict):
            return
        for name, checked in data.items():
            if name and name not in self.proc_vars:
                self.proc_vars[name] = tk.BooleanVar(value=bool(checked))

    def _save_processes(self):
        """현재 프로세스명+체크상태를 JSON에 기록."""
        write_json(self._proc_store_path,
                   {name: var.get() for name, var in self.proc_vars.items()})

    def _on_proc_toggle(self):
        """체크박스 토글 시 상태를 저장하고 필터 재적용."""
        self._save_processes()
        self.apply_filter()

    # ── 프로세스명 추가/삭제 ─────────────────────────────
    def _add_process(self):
        name = self.proc_entry_var.get().strip()
        self.proc_entry_var.set("")
        if not name or name in self.proc_vars:
            return
        self.proc_vars[name] = tk.BooleanVar(value=True)
        self._save_processes()
        self._build_proc_rows()
        self.apply_filter()

    def _remove_process(self, name):
        self.proc_vars.pop(name, None)
        self._save_processes()
        self._build_proc_rows()
        self.apply_filter()

    def _build_proc_rows(self):
        p = self._p
        for w in self.proc_list_frame.winfo_children():
            w.destroy()
        for name, var in self.proc_vars.items():
            row = tk.Frame(self.proc_list_frame, bg=PANEL)
            row.pack(fill="x", padx=p(8), pady=p(2))
            tk.Checkbutton(row, text=name, variable=var, bg=PANEL, fg=TEXT,
                           selectcolor=CHIP_BG, activebackground=PANEL,
                           activeforeground=TEXT_SEL, font=(FONT, 9),
                           anchor="w", relief="flat",
                           command=self._on_proc_toggle).pack(
                side="left", fill="x", expand=True)
            cnt = str(self.dump.process_count(name)) if self.dump.lines else ""
            tk.Label(row, text=cnt, bg=PANEL, fg=TEXT_DIM,
                     font=(FONT, 8)).pack(side="right", padx=p((2, 2)))
            tk.Button(row, text="✕", bg=PANEL, fg=ACCENT2, relief="flat",
                      font=(FONT, 8), cursor="hand2", activebackground=PANEL,
                      activeforeground="#ff6b6b",
                      command=lambda n=name: self._remove_process(n)).pack(side="right")

    # ── 카운트 갱신 ─────────────────────────────────────
    def _update_counts(self):
        sc = self.dump.section_counts(SECTIONS)
        for sec, lbl in self.section_count_lbls.items():
            lbl.config(text=str(sc.get(sec, 0)))
        self.comp_counts = {}
        for section in SECTION_COMPONENTS:
            comps = self._comp_list(section)
            cc = self.dump.component_counts(section, comps)
            for comp in comps:
                self.comp_counts[(section, comp)] = cc.get(comp, 0)
        self._render_comp_panel()       # 보이는 탭의 카운트 갱신

    # ── 섹션 헤더 진단 ──────────────────────────────────
    def _print_headers_to_console(self):
        print("\n=== 파일에서 발견된 섹션 헤더 ===")
        for raw, matched in self.dump.discovered:
            mark = f"-> {matched}" if matched else "(미인식)"
            print(f"  {raw!r:50} {mark}")
        print("================================\n")

    def show_headers(self):
        p = self._p
        win = tk.Toplevel(self.root)
        win.title("발견된 섹션 헤더")
        win.configure(bg=BG)
        win.geometry(f"{p(640)}x{p(520)}")
        tk.Label(win, text="파일에 실제로 있는 섹션 헤더 목록", bg=BG, fg=ACCENT,
                 font=(FONT, 11, "bold")).pack(anchor="w", padx=p(14), pady=p((12, 2)))
        tk.Label(win, text="파란색 = 인식됨 / 회색 = 미인식.  필터하려면 이 이름을 "
                           "dumpstate_config.py 의 SECTIONS 에 그대로 넣으면 된다.",
                 bg=BG, fg=TEXT_DIM, font=(FONT, 8),
                 justify="left", wraplength=p(600)).pack(anchor="w", padx=p(14),
                                                         pady=p((0, 8)))

        frame = tk.Frame(win, bg=BG)
        frame.pack(fill="both", expand=True, padx=p(14), pady=p((0, 12)))
        vsb = tk.Scrollbar(frame, orient="vertical")
        vsb.pack(side="right", fill="y")
        txt = tk.Text(frame, bg=PANEL, fg=TEXT, font=(FONT, 10), relief="flat",
                      wrap="none", yscrollcommand=vsb.set)
        txt.pack(fill="both", expand=True)
        vsb.config(command=txt.yview)
        txt.tag_config("ok", foreground=ACCENT)
        txt.tag_config("no", foreground=TEXT_DIM)

        if not self.dump.discovered:
            txt.insert("end", "(파일을 먼저 열어주세요)\n", "no")
        for raw, matched in self.dump.discovered:
            mark = "[인식]" if matched else "[   ]"
            txt.insert("end", f"{mark} {raw}\n", "ok" if matched else "no")
        txt.config(state="disabled")
