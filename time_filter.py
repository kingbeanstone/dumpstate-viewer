# ──────────────────────────────────────────────────────────
# 시간대 필터 입력 위젯
#   [시]:[분]:[초]  ~  [시]:[분]:[초]   (각 칸 Enter 시 콜백)
# 부분 입력 허용: 빈 칸은 parse_user_time 에서 시작=0 / 끝=최대값으로 패딩.
# ──────────────────────────────────────────────────────────
import tkinter as tk

from theme import PANEL, TEXT, TEXT_DIM, CHIP_BG, FONT


class TimeRangeFilter:
    def __init__(self, parent, p, on_enter):
        """parent: 부모 위젯, p: 픽셀 배율 함수, on_enter: Enter 시 호출할 콜백."""
        self.p = p
        self._on_enter = on_enter
        self.s_h, self.s_m, self.s_s = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.e_h, self.e_m, self.e_s = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self._build(parent)

    def _build(self, parent):
        p = self.p
        tk.Label(parent, text="시간", bg=PANEL, fg=TEXT_DIM,
                 font=(FONT, 9)).pack(side="left", padx=p((16, 6)), pady=p(10))
        self._triple(parent, self.s_h, self.s_m, self.s_s)
        tk.Label(parent, text="~", bg=PANEL, fg=TEXT_DIM,
                 font=(FONT, 10)).pack(side="left", padx=p(4))
        self._triple(parent, self.e_h, self.e_m, self.e_s)

    def _triple(self, parent, vh, vm, vs):
        p = self.p
        for i, var in enumerate((vh, vm, vs)):
            if i > 0:
                tk.Label(parent, text=":", bg=PANEL, fg=TEXT_DIM,
                         font=(FONT, 10)).pack(side="left")
            ent = tk.Entry(parent, textvariable=var, bg=CHIP_BG, fg=TEXT,
                           insertbackground=TEXT, relief="flat", justify="center",
                           font=(FONT, 10), width=3)
            ent.pack(side="left", ipady=p(4))
            ent.bind("<Return>", lambda e: self._on_enter())

    @staticmethod
    def _compose(vh, vm, vs):
        """세 칸 값을 'H:M:S' 형태 문자열로. 뒤쪽 빈 칸은 떼고, 중간 빈 칸은 0."""
        parts = [vh.get().strip(), vm.get().strip(), vs.get().strip()]
        while parts and parts[-1] == "":
            parts.pop()
        if not parts:
            return ""
        return ":".join(part or "0" for part in parts)

    def get_start(self):
        return self._compose(self.s_h, self.s_m, self.s_s)

    def get_end(self):
        return self._compose(self.e_h, self.e_m, self.e_s)
