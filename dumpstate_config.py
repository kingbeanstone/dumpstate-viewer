# ──────────────────────────────────────────────────────────
# 덤프스테이트 뷰어 설정
# 새 섹션 / 컴포넌트를 추가하려면 이 파일만 수정하면 된다.
# ──────────────────────────────────────────────────────────

# 필터링할 섹션 (덤프스테이트 "------ SECTION (...) ------" 헤더 기준, 정확히 일치).
# 실제 파일의 헤더명과 글자가 정확히 같아야 인식된다.
# (UI의 "섹션 헤더 보기" 버튼으로 파일에 실제로 있는 헤더명을 확인할 수 있다.)
SECTIONS = [
    "DUMPSYS CRITICAL",
    "SYSTEM LOG",
    "EVENT LOG",
    "STORAGED IO INFO",
    "BLOCKED PROCESS WAIT-CHANNELS",
    "PROCESS TIMES",
    "CHECKIN PROCSTATS",
    "VM TRACES JUST NOW",
    "VM TRACES AT LAST ANR",
]

# 섹션별 컴포넌트(logcat TAG) 목록.
# 여기에 없는 섹션은 컴포넌트 필터가 적용되지 않는다(섹션/프로세스 필터만 동작).
SECTION_COMPONENTS = {
    "SYSTEM LOG": [
        "SurfaceFlinger",
        "RenderEngine",
        "BLASTSyncEngine",
        "Layer",
        "VRI[MainActivity]",
        "WindowManager",
        "InputDispatcher",
        "ActivityManager",
        "ActivityTaskManager",
        "GOS",
        "SDHMS",
        "SurfaceComposerClient",
        "InsetsController",
        "InsetsSourceProvider",
        "InsetsSourceConsumer",
        "ImeTracker",
        "ActivityThread",
        "GraphicsStatsService",
        "UsageStatsService",
        "FreecessHandler",
        "PerProcessNandswap",
    ],
    "EVENT LOG": [
        "am_proc_start",
        "am_proc_died",
        "am_proc_bound",
        "am_pss",
        "am_anr",
        "am_crash",
        "am_kill",
        "am_low_memory",
        "am_activity_launch_time",
        "am_activity_fully_drawn_time",
        "am_focused_stack",
        "am_focused_window",
        "wm_on_resume_called",
        "wm_on_paused_called",
        "wm_on_stop_called",
        "notification_enqueue",
        "notification_cancel",
        "power_screen_state",
        "battery_level",
        "sysui_view_visibility",
        "sysui_count",
        "jank_cuj_events_begin_request",
    ],
}
