from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class MatchResult:
    confidence: float
    center_x: int
    center_y: int


class TemplateMatcher:
    """일반 UI 버튼용 보조 탐지기. CAPTCHA/보안 인증에는 사용하지 않습니다."""

    @staticmethod
    def find(screenshot: bytes, template_path: Path, threshold: float = 0.92) -> MatchResult | None:
        import cv2
        import numpy as np

        if not template_path.exists():
            return None
        screen = cv2.imdecode(np.frombuffer(screenshot, dtype=np.uint8), cv2.IMREAD_COLOR)
        template = cv2.imread(str(template_path), cv2.IMREAD_COLOR)
        if screen is None or template is None:
            return None
        height, width = template.shape[:2]
        if height > screen.shape[0] or width > screen.shape[1]:
            return None
        scores = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        _, confidence, _, top_left = cv2.minMaxLoc(scores)
        if confidence < threshold:
            return None
        return MatchResult(
            confidence=float(confidence),
            center_x=top_left[0] + width // 2,
            center_y=top_left[1] + height // 2,
        )
