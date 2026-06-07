# ──────────────────────────────────────────────────────────
# ANR 분석 전용 창
#   좌: 프로세스▸스레드 트리, 우: 선택한 스레드의 스택 트레이스.
#   상단에서 VM TRACES 섹션 전환(AT LAST ANR / JUST NOW).
#   부가: main 맨 위·강조, 상태별 색상, 라벨에 상태·tid, 트레이스 내 검색, 줌.
# 자체 완결형 — 메인 앱(믹스인)에 의존하지 않는다.
# ──────────────────────────────────────────────────────────
import tkinter as tk
from tkinter import ttk

from theme import (BG, PANEL, BORDER, ACCENT, ACCENT2, TEXT, TEXT_DIM, TEXT_SEL,
                   CHIP_BG, FONT, ANR_BLOCKED, ANR_WAIT, ANR_RUN, ANR_DIM)

SECTION_LABELS = {
    "VM TRACES AT LAST ANR": "AT LAST ANR",
    "VM TRACES JUST NOW": "JUST NOW",
}
FONT_MIN, FONT_MAX, FONT_DEFAULT = 6, 40, 11


def _state_color(state):
    s = (state or "").lower()
    if s in ("blocked", "monitor"):
        return ANR_BLOCKED
    if s in ("waiting", "timedwaiting", "sleeping", "wait"):
        return ANR_WAIT
    if s in ("runnable", "native"):
        return ANR_RUN
    return ANR_DIM


def _state_tag(state):
    s = (state or "").lower()
    if s in ("blocked", "monitor"):
        return "st_blocked"
    if s in ("waiting", "timedwaiting", "sleeping", "wait"):
        return "st_wait"
    if s in ("runnable", "native"):
        return "st_run"
    return "st_dim"


class AnrWindow:
    def __init__(self, parent, traces_by_section, p):
        self.p = p
        self.traces = traces_by_section            # {섹션: [AnrProcess]}
        self.sections = list(traces_by_section.keys())
        self._active_section = self.sections[0]
        self._font_size = FONT_DEFAULT
        self._match_idx = -1
        self._node_meta = {}                       # tree item -> ("thread",proc,thread)|("proc",proc,None)
        self._visible_procs = {}                   # 섹션 -> 보일 프로세스 인덱스 set (없음/None = 전체)

        self.win = tk.Toplevel(parent)
        self.win.title("ANR 분석 — VM TRACES")
        self.win.configure(bg=BG)
        try:
            sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
            w = min(p(1100), int(sw * 0.85))
            h = min(p(780), int(sh * 0.85))
        except Exception:
            w, h = p(1100), p(780)
        self.win.geometry(f"{w}x{h}")
        self.win.minsize(p(700), p(450))

        self._build_ui()
        self._update_tabs()
        self._populate_tree()
        self.win.lift()
        self.win.focus_force()

    # ── UI ──────────────────────────────────────────────
    def _build_ui(self):
        p = self.p
        top = tk.Frame(self.win, bg=PANEL, height=p(44))
        top.pack(fill="x")
        top.pack_propagate(False)

        tk.Label(top, text="SECTION", bg=PANEL, fg=TEXT_DIM,
                 font=(FONT, 9, "bold")).pack(side="left", padx=p((14, 8)), pady=p(10))
        self.tab_btns = {}
        for sec in self.sections:
            b = tk.Button(top, text=SECTION_LABELS.get(sec, sec), relief="flat",
                          cursor="hand2", font=(FONT, 9, "bold"), padx=p(10), pady=p(4),
                          activebackground=ACCENT, activeforeground=TEXT_SEL,
                          command=lambda s=sec: self._select_section(s))
            b.pack(side="left", padx=p((0, 4)), pady=p(8))
            self.tab_btns[sec] = b

        # 트레이스 내 검색 (오른쪽): Enter=다음, Shift+Enter=이전
        self.match_label = tk.Label(top, text="", bg=PANEL, fg=TEXT_DIM, font=(FONT, 9))
        self.match_label.pack(side="right", padx=p(12))
        self.search_var = tk.StringVar()
        ent = tk.Entry(top, textvariable=self.search_var, bg=CHIP_BG, fg=TEXT,
                       insertbackground=TEXT, relief="flat", font=(FONT, 10), width=26)
        ent.pack(side="right", ipady=p(4), pady=p(8))
        ent.bind("<Return>", lambda e: self._on_search(1))
        ent.bind("<Shift-Return>", lambda e: self._on_search(-1))
        tk.Label(top, text="트레이스 검색", bg=PANEL, fg=TEXT_DIM,
                 font=(FONT, 9)).pack(side="right", padx=p((0, 6)))

        tk.Frame(self.win, bg=BORDER, height=p(1)).pack(fill="x")

        body = tk.PanedWindow(self.win, orient="horizontal", bg=BORDER,
                              sashwidth=p(4), bd=0)
        body.pack(fill="both", expand=True)

        # 좌측: 프로세스▸스레드 트리
        left = tk.Frame(body, bg=PANEL)
        ctrl = tk.Frame(left, bg=PANEL)
        ctrl.pack(side="top", fill="x", padx=p(6), pady=p(6))
        tk.Button(ctrl, text="프로세스 선택", bg=CHIP_BG, fg=TEXT, relief="flat",
                  font=(FONT, 9, "bold"), padx=p(10), pady=p(4), cursor="hand2",
                  activebackground=ACCENT, activeforeground=TEXT_SEL,
                  command=self._open_proc_picker).pack(side="left")
        self.pick_lbl = tk.Label(ctrl, text="", bg=PANEL, fg=TEXT_DIM, font=(FONT, 8))
        self.pick_lbl.pack(side="left", padx=p((8, 0)))

        self._style_tree()
        tvsb = tk.Scrollbar(left, orient="vertical")
        tvsb.pack(side="right", fill="y")
        self.tree = ttk.Treeview(left, style="ANR.Treeview", show="tree",
                                 yscrollcommand=tvsb.set, selectmode="browse")
        self.tree.pack(side="left", fill="both", expand=True)
        tvsb.config(command=self.tree.yview)
        self.tree.column("#0", width=p(330), stretch=True)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._on_select())
        self.tree.tag_configure("st_blocked", foreground=ANR_BLOCKED)
        self.tree.tag_configure("st_wait", foreground=ANR_WAIT)
        self.tree.tag_configure("st_run", foreground=ANR_RUN)
        self.tree.tag_configure("st_dim", foreground=ANR_DIM)
        self.tree.tag_configure("proc", foreground=ACCENT2, font=(FONT, 10, "bold"))
        self.tree.tag_configure("main_th", font=(FONT, 10, "bold"))
        body.add(left, width=p(340), minsize=p(200))

        # 우측: 스택 트레이스
        right = tk.Frame(body, bg=BG)
        rvsb = tk.Scrollbar(right, orient="vertical")
        rvsb.pack(side="right", fill="y")
        rhsb = tk.Scrollbar(right, orient="horizontal")
        rhsb.pack(side="bottom", fill="x")
        self.trace = tk.Text(right, bg=BG, fg=TEXT, font=(FONT, self._font_size),
                             relief="flat", wrap="none", state="disabled", cursor="arrow",
                             yscrollcommand=rvsb.set, xscrollcommand=rhsb.set,
                             selectbackground=ACCENT, selectforeground=TEXT_SEL)
        self.trace.pack(fill="both", expand=True)
        rvsb.config(command=self.trace.yview)
        rhsb.config(command=self.trace.xview)
        self.trace.tag_config("hdr", font=(FONT, self._font_size, "bold"))
        self.trace.tag_config("search_hl", background="#f7d94f", foreground="#000000")
        self.trace.tag_config("cur_match", background="#f7834f", foreground="#000000")
        self.trace.tag_raise("cur_match")
        body.add(right, minsize=p(300))

        # 줌: Ctrl +/-(키패드 포함), Ctrl+0, Ctrl+휠
        for seq in ("<Control-plus>", "<Control-equal>", "<Control-KP_Add>"):
            self.win.bind(seq, lambda e: self._zoom(1))
        for seq in ("<Control-minus>", "<Control-KP_Subtract>"):
            self.win.bind(seq, lambda e: self._zoom(-1))
        self.win.bind("<Control-0>", lambda e: self._zoom_reset())
        self.trace.bind("<Control-MouseWheel>",
                        lambda e: self._zoom(1 if e.delta > 0 else -1))

    def _style_tree(self):
        style = ttk.Style(self.win)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("ANR.Treeview", background=PANEL, fieldbackground=PANEL,
                        foreground=TEXT, borderwidth=0, font=(FONT, 10),
                        rowheight=self.p(22))
        style.map("ANR.Treeview",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", TEXT_SEL)])

    # ── 섹션 탭 ──────────────────────────────────────────
    def _select_section(self, sec):
        if sec == self._active_section:
            return
        self._active_section = sec
        self._update_tabs()
        self._populate_tree()

    def _update_tabs(self):
        for sec, b in self.tab_btns.items():
            if sec == self._active_section:
                b.config(bg=ACCENT, fg=TEXT_SEL)
            else:
                b.config(bg=CHIP_BG, fg=TEXT_DIM)

    # ── 트리 채우기 ──────────────────────────────────────
    def _populate_tree(self):
        self.tree.delete(*self.tree.get_children())
        self._node_meta = {}
        procs = self.traces.get(self._active_section, [])
        vis = self._visible_procs.get(self._active_section)   # None = 전체
        shown = 0
        for i, proc in enumerate(procs):
            if vis is not None and i not in vis:
                continue
            shown += 1
            label = f"{proc.name}   (pid {proc.pid}, {len(proc.threads)} threads)"
            pitem = self.tree.insert("", "end", text=label, open=False, tags=("proc",))
            self._node_meta[pitem] = ("proc", proc, None)
            # main 스레드를 맨 위로(나머지는 원래 순서 유지 — stable sort)
            for t in sorted(proc.threads, key=lambda th: th.name != "main"):
                lbl = f"tid={t.tid}    {t.state}    {t.name}"
                tags = [_state_tag(t.state)]
                if t.name == "main":
                    tags.append("main_th")
                item = self.tree.insert(pitem, "end", text=lbl, tags=tuple(tags))
                self._node_meta[item] = ("thread", proc, t)
        self.pick_lbl.config(text=f"표시 {shown}/{len(procs)}")
        self._show_hint(shown)                 # 선택 없음 → 우측 안내

    def _show_hint(self, shown):
        if shown:
            msg = "  왼쪽에서 프로세스를 펼쳐(▸) 스레드를 선택하세요."
        else:
            msg = "  '프로세스 선택' 버튼으로 표시할 프로세스를 고르세요."
        self._show_lines(["", msg], header=False, state=None)

    # ── 표시할 프로세스 선택 모달 ────────────────────────
    def _open_proc_picker(self):
        p = self.p
        sec = self._active_section
        procs = self.traces.get(sec, [])
        dlg = tk.Toplevel(self.win)
        dlg.title("프로세스 선택")
        dlg.configure(bg=BG)
        dlg.transient(self.win)
        try:
            dlg.grab_set()
        except Exception:
            pass
        w, h = p(460), p(420)
        try:
            px = self.win.winfo_rootx() + (self.win.winfo_width() - w) // 2
            py = self.win.winfo_rooty() + (self.win.winfo_height() - h) // 2
            dlg.geometry(f"{w}x{h}+{max(px, 0)}+{max(py, 0)}")
        except Exception:
            dlg.geometry(f"{w}x{h}")

        tk.Label(dlg, text="표시할 프로세스 선택 (복수 선택 가능)", bg=BG, fg=TEXT,
                 font=(FONT, 10, "bold"), anchor="w").pack(
            fill="x", padx=p(14), pady=p((14, 6)))

        frame = tk.Frame(dlg, bg=BG)
        frame.pack(fill="both", expand=True, padx=p(14))
        lvsb = tk.Scrollbar(frame, orient="vertical")
        lvsb.pack(side="right", fill="y")
        lb = tk.Listbox(frame, selectmode="multiple", bg=PANEL, fg=TEXT,
                        font=(FONT, 9), relief="flat", activestyle="none",
                        selectbackground=ACCENT, selectforeground=TEXT_SEL,
                        highlightthickness=0, yscrollcommand=lvsb.set)
        lb.pack(side="left", fill="both", expand=True)
        lvsb.config(command=lb.yview)
        for proc in procs:
            lb.insert("end",
                      f"pid {proc.pid}  |  스레드 {len(proc.threads)}개  |  {proc.name}")
        # 열 때는 모두 선택 해제 상태(매번 새로 고름)

        btns = tk.Frame(dlg, bg=BG)
        btns.pack(fill="x", padx=p(14), pady=p(12))

        def apply():
            self._visible_procs[sec] = set(lb.curselection())
            dlg.destroy()
            self._populate_tree()

        tk.Button(btns, text="선택", bg=ACCENT, fg=TEXT_SEL, relief="flat",
                  font=(FONT, 9, "bold"), padx=p(16), pady=p(5), cursor="hand2",
                  activebackground="#3a7ae0", command=apply).pack(side="right")
        tk.Button(btns, text="취소", bg=CHIP_BG, fg=TEXT, relief="flat",
                  font=(FONT, 9, "bold"), padx=p(16), pady=p(5), cursor="hand2",
                  activebackground=BORDER, command=dlg.destroy).pack(
            side="right", padx=p((0, 6)))

    def _on_select(self):
        sel = self.tree.selection()
        if not sel:
            return
        meta = self._node_meta.get(sel[0])
        if not meta:
            return
        kind, proc, thread = meta
        if kind == "thread":
            self._show_lines(thread.lines, header=True, state=thread.state)
        else:
            self._show_lines(proc.header_lines, header=False, state=None)

    # ── 트레이스 표시 ────────────────────────────────────
    def _show_lines(self, lines, header, state):
        self.trace.config(state="normal")
        self.trace.delete("1.0", "end")
        self.trace.insert("1.0", "\n".join(lines) + ("\n" if lines else ""))
        if header and lines:                   # 첫 줄(스레드 헤더)을 상태 색·굵게
            self.trace.tag_config("hdr", foreground=_state_color(state),
                                  font=(FONT, self._font_size, "bold"))
            self.trace.tag_add("hdr", "1.0", "2.0")
        self.trace.config(state="disabled")
        self.trace.yview_moveto(0.0)
        self._reapply_search()                 # 다른 스레드로 바뀌어도 검색어 유지

    # ── 트레이스 내 검색 ─────────────────────────────────
    def _on_search(self, step):
        self._highlight_search(self.search_var.get())
        self._goto_match(step)
        return "break"

    def _reapply_search(self):
        kw = self.search_var.get()
        self.trace.tag_remove("cur_match", "1.0", "end")
        self._match_idx = -1
        if kw:
            self._highlight_search(kw)
        else:
            self.trace.tag_remove("search_hl", "1.0", "end")
            self.match_label.config(text="")

    def _highlight_search(self, kw):
        self.trace.tag_remove("search_hl", "1.0", "end")
        self.trace.tag_remove("cur_match", "1.0", "end")
        self._match_idx = -1
        if not kw:
            self.match_label.config(text="")
            return
        n = len(kw)
        start = "1.0"
        while True:
            pos = self.trace.search(kw, start, stopindex="end", nocase=True)
            if not pos:
                break
            end = f"{pos}+{n}c"
            self.trace.tag_add("search_hl", pos, end)
            start = end

    def _goto_match(self, step):
        ranges = self.trace.tag_ranges("search_hl")
        total = len(ranges) // 2
        if total == 0:
            self.match_label.config(text="매치 없음" if self.search_var.get() else "")
            return
        if self._match_idx == -1:
            self._match_idx = 0 if step > 0 else total - 1
        else:
            self._match_idx = (self._match_idx + step) % total
        s = ranges[self._match_idx * 2]
        e = ranges[self._match_idx * 2 + 1]
        self.trace.tag_remove("cur_match", "1.0", "end")
        self.trace.tag_add("cur_match", s, e)
        self.trace.see(e)
        self.trace.see(s)
        self.match_label.config(text=f"{self._match_idx + 1}/{total}")

    # ── 줌 ──────────────────────────────────────────────
    def _zoom(self, delta):
        self._set_font(self._font_size + delta)
        return "break"

    def _zoom_reset(self):
        self._set_font(FONT_DEFAULT)
        return "break"

    def _set_font(self, size):
        size = max(FONT_MIN, min(FONT_MAX, size))
        if size == self._font_size:
            return
        self._font_size = size
        self.trace.config(font=(FONT, size))
        self.trace.tag_config("hdr", font=(FONT, size, "bold"))
