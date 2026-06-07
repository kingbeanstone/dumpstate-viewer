import os
import tkinter as tk
from tkinter import filedialog

import dumpstate_parser as dp
from dumpstate_config import SECTIONS
from theme import (BG, PANEL, BORDER, ACCENT, TEXT, TEXT_DIM, TEXT_SEL, CHIP_BG, FONT)
from time_filter import TimeRangeFilter
from viewer_sidebar import SidebarMixin
from viewer_render import RenderMixin


class LogViewerApp(SidebarMixin, RenderMixin):
    def __init__(self, root):
        self.root = root
        self._setup_hidpi()                # 고해상도 선명도 (블러/자글거림 제거)
        s = self._ui_scale
        self.root.title("Dumpstate Log Viewer")
        self.root.configure(bg=BG)
        self.root.geometry(f"{int(1280 * s)}x{int(800 * s)}")
        self.root.minsize(int(900 * s), int(560 * s))

        self.dump = dp.Dump()
        self.rows = []                     # build_display() 결과 (위젯 줄번호 = 인덱스+1)
        self.widget_full = False           # 위젯에 전체 행이 들어있는지(elide 모드 전제)
        # 스크롤 렉은 '숨겨진 줄 수'에 비례한다. 숨길 줄이 이 값보다 많으면
        # 'elide'(스크롤 렉) 대신 '보이는 줄만 재렌더'(숨김 0 → 매끈)로 간다.
        self.ELIDE_HIDDEN_LIMIT = 3000

        self.section_vars = {}             # 섹션 -> BooleanVar
        self.comp_vars = {}                # 섹션 -> {컴포넌트 -> BooleanVar}
        self.proc_vars = {}                # 프로세스명 -> BooleanVar
        self.custom_comps = {}             # 섹션 -> [사용자 추가 컴포넌트]
        self.comp_counts = {}              # (섹션, 컴포넌트) -> 줄 수
        # 저장한 프로세스명/컴포넌트(+체크상태) 보관 파일(앱 폴더, 세션 간 유지)
        _here = os.path.dirname(os.path.abspath(__file__))
        self._proc_store_path = os.path.join(_here, "saved_processes.json")
        self._comp_store_path = os.path.join(_here, "saved_components.json")
        self.section_count_lbls = {}

        # 필터는 입력 중 값이 아니라 Enter로 '확정'된 값만 적용한다.
        self._applied_search = ""
        self._applied_tstart = ""
        self._applied_tend = ""
        self._shown = 0                    # 마지막 필터 결과 줄 수
        self._match_idx = -1               # 검색 매치 순회 인덱스 (Enter 연타용)
        self._log_font_size = 10           # 로그 글씨 크기 (Ctrl +/- 로 조절)

        self._build_ui()
        self._load_saved_processes()       # 저장해둔 프로세스명 복원
        self._build_proc_rows()

    # ── 고해상도(HiDPI) 선명도 설정 ──────────────────────
    def _setup_hidpi(self):
        """DPI 인식 환경에서 폰트/위젯을 점(point) 기준으로 스케일링해
        OS의 비트맵 확대(블러) 없이 네이티브 해상도로 또렷하게 렌더한다."""
        try:
            dpi = self.root.winfo_fpixels("1i")   # 화면 실제 DPI
        except Exception:
            dpi = 96.0
        self._ui_scale = max(1.0, dpi / 96.0)
        try:
            self.root.tk.call("tk", "scaling", dpi / 72.0)
        except Exception:
            pass

    def _p(self, v):
        """픽셀 단위 값을 화면 배율로 환산(여백/너비/높이용). int 또는 (a,b) 튜플 지원.
        폰트 point 크기와 Entry의 글자수 width 에는 쓰지 않는다."""
        s = self._ui_scale
        if isinstance(v, tuple):
            return tuple(int(round(x * s)) for x in v)
        return int(round(v * s))

    # ── UI 구성 ─────────────────────────────────────────
    def _build_ui(self):
        p = self._p
        toolbar = tk.Frame(self.root, bg=PANEL, height=p(52))
        toolbar.pack(fill="x", side="top")
        toolbar.pack_propagate(False)

        tk.Label(toolbar, text="DUMPSTATE VIEWER", bg=PANEL, fg=ACCENT,
                 font=(FONT, 13, "bold")).pack(side="left", padx=p(20), pady=p(14))

        tk.Button(toolbar, text="⊕  파일 열기", bg=ACCENT, fg=TEXT_SEL, relief="flat",
                  font=(FONT, 10, "bold"), padx=p(14), pady=p(6), cursor="hand2",
                  activebackground="#3a7ae0", activeforeground=TEXT_SEL,
                  command=self.open_file).pack(side="left", padx=p((150, 8)), pady=p(10))

        tk.Button(toolbar, text="섹션 헤더 보기", bg=CHIP_BG, fg=TEXT, relief="flat",
                  font=(FONT, 9, "bold"), padx=p(12), pady=p(6), cursor="hand2",
                  activebackground=BORDER, activeforeground=TEXT_SEL,
                  command=self.show_headers).pack(side="left", padx=p((0, 10)), pady=p(10))

        self.file_label = tk.Label(toolbar, text="파일을 열어주세요", bg=PANEL,
                                   fg=TEXT_DIM, font=(FONT, 9))
        self.file_label.pack(side="left", padx=p(4))

        # ── 좌측 사이드바 (스크롤 가능) ──
        left = tk.Frame(self.root, bg=PANEL, width=p(300))
        left.pack(fill="y", side="left")
        left.pack_propagate(False)
        tk.Frame(left, bg=BORDER, height=p(1)).pack(fill="x")

        self.sidebar_canvas = tk.Canvas(left, bg=PANEL, highlightthickness=0)
        sb_vsb = tk.Scrollbar(left, orient="vertical", command=self.sidebar_canvas.yview)
        self.sidebar_canvas.configure(yscrollcommand=sb_vsb.set)
        sb_vsb.pack(side="right", fill="y")
        self.sidebar_canvas.pack(side="left", fill="both", expand=True)

        self.sidebar = tk.Frame(self.sidebar_canvas, bg=PANEL)
        self.sidebar_win = self.sidebar_canvas.create_window(
            (0, 0), window=self.sidebar, anchor="nw")
        self.sidebar.bind("<Configure>", lambda e: self.sidebar_canvas.configure(
            scrollregion=self.sidebar_canvas.bbox("all")))
        self.sidebar_canvas.bind("<Configure>", lambda e: self.sidebar_canvas.itemconfig(
            self.sidebar_win, width=e.width))
        self.sidebar_canvas.bind("<Enter>", lambda e: self.sidebar_canvas.bind_all(
            "<MouseWheel>", self._scroll_sidebar))
        self.sidebar_canvas.bind("<Leave>", lambda e: self.sidebar_canvas.unbind_all(
            "<MouseWheel>"))

        self._build_sections_group()
        self._build_process_group()
        self._build_components_groups()

        tk.Frame(self.root, bg=BORDER, width=p(1)).pack(fill="y", side="left")

        # ── 우측 로그 영역 ──
        right = tk.Frame(self.root, bg=BG)
        right.pack(fill="both", expand=True, side="left")

        search_bar = tk.Frame(right, bg=PANEL, height=p(40))
        search_bar.pack(fill="x")
        search_bar.pack_propagate(False)
        tk.Label(search_bar, text="검색", bg=PANEL, fg=TEXT_DIM,
                 font=(FONT, 9)).pack(side="left", padx=p((14, 6)), pady=p(10))
        self.search_var = tk.StringVar()
        # Enter=적용/다음 매치, Shift+Enter=이전 매치 (VSCode식)
        search_entry = tk.Entry(search_bar, textvariable=self.search_var, bg=CHIP_BG,
                                fg=TEXT, insertbackground=TEXT, relief="flat",
                                font=(FONT, 10), width=34)
        search_entry.pack(side="left", ipady=p(4))
        search_entry.bind("<Return>", lambda e: self._on_search(1))
        search_entry.bind("<Shift-Return>", lambda e: self._on_search(-1))

        # 시간대 필터 (검색칸 오른쪽): [시]:[분]:[초] ~ [시]:[분]:[초]
        self.time_filter = TimeRangeFilter(search_bar, self._p, self._on_time_enter)

        self.result_label = tk.Label(search_bar, text="", bg=PANEL, fg=TEXT_DIM,
                                     font=(FONT, 9))
        self.result_label.pack(side="right", padx=p(14))

        tk.Frame(right, bg=BORDER, height=p(1)).pack(fill="x")

        log_frame = tk.Frame(right, bg=BG)
        log_frame.pack(fill="both", expand=True)
        vsb = tk.Scrollbar(log_frame, orient="vertical")
        vsb.pack(side="right", fill="y")
        hsb = tk.Scrollbar(log_frame, orient="horizontal")
        hsb.pack(side="bottom", fill="x")
        fs = self._log_font_size
        self.log_text = tk.Text(log_frame, bg=BG, fg=TEXT, font=(FONT, fs),
                                relief="flat", wrap="none", yscrollcommand=vsb.set,
                                xscrollcommand=hsb.set, state="disabled", cursor="arrow",
                                selectbackground=ACCENT, selectforeground=TEXT_SEL)
        self.log_text.pack(fill="both", expand=True)
        vsb.config(command=self.log_text.yview)
        hsb.config(command=self.log_text.xview)

        # 에디터 글씨 확대/축소: Ctrl +/- (키패드 포함), Ctrl+0 리셋, Ctrl+휠
        for seq in ("<Control-plus>", "<Control-equal>", "<Control-KP_Add>"):
            self.root.bind(seq, lambda e: self._zoom_log(1))
        for seq in ("<Control-minus>", "<Control-KP_Subtract>"):
            self.root.bind(seq, lambda e: self._zoom_log(-1))
        self.root.bind("<Control-0>", lambda e: self._reset_log_font())
        self.log_text.bind("<Control-MouseWheel>",
                           lambda e: self._zoom_log(1 if e.delta > 0 else -1))

        self.log_text.tag_config("component", foreground=ACCENT,
                                 font=(FONT, fs, "bold"))
        self.log_text.tag_config("proc_hl", background="#2c4a2c", foreground="#a8f0a8")
        self.log_text.tag_config("search_hl", background="#f7d94f", foreground="#000000")
        # 현재 매치(Enter로 이동 중인 단어) — 검색 강조보다 위, 주황색 강조
        self.log_text.tag_config("cur_match", background="#f7834f", foreground="#000000")
        self.log_text.tag_config("section_hdr", foreground="#f7834f",
                                 font=(FONT, fs, "bold"),
                                 spacing1=p(6), spacing3=p(2))
        self.log_text.tag_raise("search_hl")
        self.log_text.tag_raise("cur_match")
        # elide=True 인 줄은 재삽입 없이 화면에서 숨겨진다 (넓은 결과용 토글)
        self.log_text.tag_config("hidden", elide=True)
        self.log_text.tag_raise("hidden")

    # ── 파일 열기 ────────────────────────────────────────
    def open_file(self):
        path = filedialog.askopenfilename(
            title="덤프스테이트 파일 선택",
            filetypes=[("텍스트/로그", "*.txt *.log"), ("모든 파일", "*.*")])
        if not path:
            return
        self.file_label.config(text=os.path.basename(path))
        self.dump.load(path)
        self.dump.parse(SECTIONS)
        self.rows = self.dump.build_display(SECTIONS)
        self.widget_full = False
        self._update_counts()
        self._build_proc_rows()
        self.apply_filter()
        self._print_headers_to_console()


def _enable_dpi_awareness():
    """Tk 루트 생성 '전에' 프로세스를 DPI 인식으로 만들어 OS의 흐릿한
    비트맵 확대를 막는다 (Windows 전용, 다른 OS에선 조용히 무시)."""
    try:
        from ctypes import windll
        try:
            windll.shcore.SetProcessDpiAwareness(2)   # per-monitor v2
        except Exception:
            windll.user32.SetProcessDPIAware()        # 구형 폴백
    except Exception:
        pass


if __name__ == "__main__":
    _enable_dpi_awareness()
    root = tk.Tk()
    app = LogViewerApp(root)
    root.mainloop()
