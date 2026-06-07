# ──────────────────────────────────────────────────────────
# 작은 JSON 영속화 헬퍼 (저장 파일 읽기/쓰기 공통 처리)
#   프로세스/컴포넌트 등 "세션 간 유지" 상태를 같은 방식으로 저장한다.
# ──────────────────────────────────────────────────────────
import json


def read_json(path, default=None):
    """JSON 파일을 읽어 반환. 없거나 깨졌으면 default."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError, OSError):
        return default


def write_json(path, data):
    """data 를 들여쓰기 JSON 으로 저장. 실패해도 조용히 무시(반환 False)."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False
