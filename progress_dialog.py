# ──────────────────────────────────────────────────────────
# 파일 로딩 진행바 (0→100%) 모달 다이얼로그
#   별도 스레드 없이, 호출부가 단계마다 set()을 호출하면 바가 차오른다.
#   (set() 안에서 update_idletasks()로 즉시 화면 갱신)
# ──────────────────────────────────────────────────────────
import tkinter as tk
from tkinter import ttk

from theme import BG, PANEL, BORDER, ACCENT, TEXT, TEXT_DIM, CHIP_BG, FONT


class ProgressDialog:
    def __init__(self, parent, p):
        self.win = tk.Toplevel(parent)
        self.win.title("불러오는 중")
        self.win.configure(bg=BG)
        self.win.resizable(False, False)
        w, h = p(380), p(116)
        # parent 중앙에 배치
        try:
            parent.update_idletasks()
            px = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
            py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
            self.win.geometry(f"{w}x{h}+{max(px, 0)}+{max(py, 0)}")
        except Exception:
            self.win.geometry(f"{w}x{h}")
        try:
            self.win.transient(parent)
            self.win.grab_set()                 # 로딩 중 입력 차단
        except Exception:
            pass

        self._style_bar(p)

        self.title_lbl = tk.Label(self.win, text="", bg=BG, fg=TEXT,
                                  font=(FONT, 10, "bold"), anchor="w")
        self.title_lbl.pack(fill="x", padx=p(18), pady=p((16, 6)))

        self.bar = ttk.Progressbar(self.win, style="DV.Horizontal.TProgressbar",
                                   orient="horizontal", mode="determinate",
                                   maximum=100, length=w - p(36))
        self.bar.pack(padx=p(18))

        self.pct_lbl = tk.Label(self.win, text="0%", bg=BG, fg=TEXT_DIM,
                                font=(FONT, 9), anchor="e")
        self.pct_lbl.pack(fill="x", padx=p(18), pady=p((6, 0)))

        self.win.update_idletasks()

    def _style_bar(self, p):
        style = ttk.Style(self.win)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("DV.Horizontal.TProgressbar",
                        troughcolor=CHIP_BG, background=ACCENT,
                        bordercolor=BORDER, lightcolor=ACCENT, darkcolor=ACCENT,
                        thickness=p(16))

    def set(self, text, frac):
        frac = 0.0 if frac < 0 else (1.0 if frac > 1 else frac)
        self.title_lbl.config(text=f"{text}…")
        self.pct_lbl.config(text=f"{int(frac * 100)}%")
        self.bar["value"] = frac * 100
        try:
            self.win.update_idletasks()         # 바가 실제로 차오르게
        except Exception:
            pass

    def close(self):
        try:
            self.win.grab_release()
        except Exception:
            pass
        self.win.destroy()
