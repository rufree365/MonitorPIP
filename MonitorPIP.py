"""하나 이상의 모니터를 재귀 화면 없이 PIP 격자로 표시한다.

예:
    python MonitorPIP.py -i 1 -f 1 -s 10
    python MonitorPIP.py -i 1,2 -f 5 -s 15

각 화면에서 좌클릭으로 영역을 드래그하면 그 영역만 표시한다.
우클릭 또는 더블클릭하면 선택 영역을 초기화한다.
"""

import argparse
import math
import sys

from mss import MSS
from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QApplication, QGridLayout, QSizePolicy, QWidget


def shot_to_image(shot) -> QImage:
    """mss의 BGRA 버퍼를 수명이 독립적인 불투명 QImage로 변환한다."""
    return QImage(
        shot.bgra,
        shot.width,
        shot.height,
        shot.width * 4,
        # X11의 mss는 alpha 바이트를 0으로 반환하므로 alpha를 무시한다.
        QImage.Format.Format_RGB32,
    ).copy()


def positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("정수를 입력해야 합니다.") from exc
    if number < 1:
        raise argparse.ArgumentTypeError("1 이상의 값을 입력해야 합니다.")
    return number


def monitor_numbers(value: str) -> list[int]:
    """'1' 또는 '1,2' 형식의 모니터 번호를 파싱한다."""
    try:
        numbers = [int(item.strip()) for item in value.split(",")]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "모니터 번호는 '1' 또는 '1,2' 형식으로 입력해야 합니다."
        ) from exc

    if not numbers or any(number < 1 for number in numbers):
        raise argparse.ArgumentTypeError("모니터 번호는 1 이상이어야 합니다.")
    if len(numbers) != len(set(numbers)):
        raise argparse.ArgumentTypeError("같은 모니터 번호를 중복 지정할 수 없습니다.")
    return numbers


def scale_percent(value: str) -> float:
    """'10'과 '10%'를 모두 10퍼센트로 해석한다."""
    raw = value.strip()
    if raw.endswith("%"):
        raw = raw[:-1].strip()
    try:
        number = float(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("백분율 숫자를 입력해야 합니다.") from exc
    if not 0 < number <= 100:
        raise argparse.ArgumentTypeError("스케일은 0 초과 100 이하이어야 합니다.")
    return number


class CapturePanel(QWidget):
    """한 모니터 영상을 그리고 마우스 영역 선택을 처리하는 패널."""

    def __init__(self, monitor_number: int, parent: QWidget | None = None):
        super().__init__(parent)
        self.monitor_number = monitor_number
        self.image: QImage | None = None
        self.crop_rect: QRect | None = None
        self.drag_start: QPoint | None = None
        self.drag_current: QPoint | None = None

        # 이미지의 sizeHint가 창의 최소 크기로 작용하지 않게 한다.
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.setMinimumSize(1, 1)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setToolTip(
            "좌클릭 드래그: 영역 확대\n우클릭/더블클릭: 전체 화면으로 복귀"
        )

    def set_image(self, image: QImage) -> None:
        self.image = image
        if self.crop_rect is not None:
            image_rect = QRect(0, 0, image.width(), image.height())
            self.crop_rect = self.crop_rect.intersected(image_rect)
            if self.crop_rect.isEmpty():
                self.crop_rect = None
        self.update()

    def _source_rect(self) -> QRect:
        if self.image is None:
            return QRect()
        if self.crop_rect is not None:
            return QRect(self.crop_rect)
        return QRect(0, 0, self.image.width(), self.image.height())

    def _image_target_rect(self) -> QRect:
        """비율을 유지해 영상이 실제로 그려지는 패널 내부 영역."""
        source = self._source_rect()
        available = self.rect()
        if source.isEmpty() or available.isEmpty():
            return QRect()

        source_ratio = source.width() / source.height()
        available_ratio = available.width() / available.height()
        if available_ratio > source_ratio:
            height = available.height()
            width = max(1, round(height * source_ratio))
        else:
            width = available.width()
            height = max(1, round(width / source_ratio))

        return QRect(
            available.x() + (available.width() - width) // 2,
            available.y() + (available.height() - height) // 2,
            width,
            height,
        )

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.black)

        source = self._source_rect()
        target = self._image_target_rect()
        if self.image is not None and not source.isEmpty() and not target.isEmpty():
            painter.drawImage(target, self.image, source)

        # 격자에서 각 영상의 모니터 번호를 알아볼 수 있게 표시한다.
        if self.width() >= 70 and self.height() >= 35:
            tag = QRect(6, 6, 76, 22)
            painter.fillRect(tag, QColor(0, 0, 0, 150))
            painter.setPen(Qt.GlobalColor.white)
            painter.drawText(tag, Qt.AlignmentFlag.AlignCenter, f"Monitor {self.monitor_number}")

        if self.drag_start is not None and self.drag_current is not None:
            selection = QRect(self.drag_start, self.drag_current).normalized()
            selection = selection.intersected(target)
            if not selection.isEmpty():
                painter.fillRect(selection, QColor(0, 255, 0, 35))
                painter.setPen(QPen(QColor(0, 255, 0), 3))
                painter.drawRect(selection.adjusted(1, 1, -1, -1))

        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self.reset_crop()
            event.accept()
            return

        point = event.position().toPoint()
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.image is not None
            and self._image_target_rect().contains(point)
        ):
            self.drag_start = point
            self.drag_current = point
            self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.drag_start is not None:
            target = self._image_target_rect()
            point = event.position().toPoint()
            self.drag_current = QPoint(
                min(max(point.x(), target.left()), target.right()),
                min(max(point.y(), target.top()), target.bottom()),
            )
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self.drag_start is None:
            super().mouseReleaseEvent(event)
            return

        target = self._image_target_rect()
        selected = QRect(self.drag_start, self.drag_current or self.drag_start).normalized()
        selected = selected.intersected(target)
        self.drag_start = None
        self.drag_current = None

        # 단순 클릭이나 지나치게 작은 드래그는 선택으로 처리하지 않는다.
        if selected.width() >= 5 and selected.height() >= 5:
            source = self._source_rect()
            left = source.x() + math.floor(
                (selected.x() - target.x()) * source.width() / target.width()
            )
            top = source.y() + math.floor(
                (selected.y() - target.y()) * source.height() / target.height()
            )
            right = source.x() + math.ceil(
                (selected.x() + selected.width() - target.x())
                * source.width()
                / target.width()
            )
            bottom = source.y() + math.ceil(
                (selected.y() + selected.height() - target.y())
                * source.height()
                / target.height()
            )
            crop = QRect(left, top, right - left, bottom - top).intersected(source)
            if crop.width() >= 2 and crop.height() >= 2:
                self.crop_rect = crop

        self.update()
        event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.reset_crop()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def reset_crop(self) -> None:
        self.crop_rect = None
        self.drag_start = None
        self.drag_current = None
        self.update()


class MonitorPIP(QWidget):
    def __init__(self, monitor_numbers_: list[int], fps: int, scale: float):
        super().__init__()

        self._sct = MSS()
        all_monitors = [dict(monitor) for monitor in self._sct.monitors[1:]]
        invalid = [number for number in monitor_numbers_ if number > len(all_monitors)]
        if invalid:
            self._sct.close()
            invalid_text = ", ".join(map(str, invalid))
            raise ValueError(
                f"모니터 {invalid_text}번을 찾을 수 없습니다. "
                f"감지된 모니터 수: {len(all_monitors)}"
            )

        self.monitor_numbers = monitor_numbers_
        self.monitors = [all_monitors[number - 1] for number in monitor_numbers_]
        self.backgrounds = [
            shot_to_image(self._sct.grab(monitor)) for monitor in self.monitors
        ]

        screens = QApplication.screens()
        self.target_screens = [
            screens[min(number - 1, len(screens) - 1)] for number in monitor_numbers_
        ]

        number_text = ",".join(map(str, monitor_numbers_))
        self.setWindowTitle(f"Monitor {number_text} PIP")
        self.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint
        )

        count = len(self.monitors)
        columns = math.ceil(math.sqrt(count))
        rows = math.ceil(count / columns)
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.panels: list[CapturePanel] = []
        for index, number in enumerate(monitor_numbers_):
            panel = CapturePanel(number, self)
            layout.addWidget(panel, index // columns, index % columns)
            self.panels.append(panel)

        screen_width = max(screen.geometry().width() for screen in self.target_screens)
        screen_height = max(screen.geometry().height() for screen in self.target_screens)
        width = max(80, round(screen_width * scale / 100.0) * columns)
        height = max(45, round(screen_height * scale / 100.0) * rows)
        self.resize(width, height)

        first_screen = self.target_screens[0].geometry()
        self.move(first_screen.x() + 30, first_screen.y() + 30)

        self._closed = False
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self.capture)
        self._timer.start(max(1, round(1000 / fps)))

    def _covered_capture_rect(self, index: int) -> QRect:
        """PIP 창과 대상 모니터가 겹치는 영역을 캡처 픽셀 좌표로 반환한다."""
        qt_monitor = self.target_screens[index].geometry()
        overlap = qt_monitor.intersected(self.frameGeometry())
        if overlap.isEmpty() or not self.isVisible():
            return QRect()

        monitor = self.monitors[index]
        scale_x = monitor["width"] / qt_monitor.width()
        scale_y = monitor["height"] / qt_monitor.height()
        left = math.floor((overlap.x() - qt_monitor.x()) * scale_x)
        top = math.floor((overlap.y() - qt_monitor.y()) * scale_y)
        right = math.ceil(
            (overlap.x() + overlap.width() - qt_monitor.x()) * scale_x
        )
        bottom = math.ceil(
            (overlap.y() + overlap.height() - qt_monitor.y()) * scale_y
        )
        rect = QRect(left, top, right - left, bottom - top)
        return rect.intersected(QRect(0, 0, monitor["width"], monitor["height"]))

    def capture(self) -> None:
        for index, (monitor, panel) in enumerate(zip(self.monitors, self.panels)):
            frame = shot_to_image(self._sct.grab(monitor))
            covered = self._covered_capture_rect(index)
            if not covered.isEmpty():
                painter = QPainter(frame)
                painter.drawImage(covered, self.backgrounds[index], covered)
                painter.end()
            panel.set_image(frame)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def release(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._timer.stop()
        self._sct.close()

    def closeEvent(self, event) -> None:
        self.release()
        super().closeEvent(event)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="선택한 모니터를 재귀 화면 없이 PIP 격자로 표시합니다."
    )
    parser.add_argument(
        "-i", "--monitor", type=monitor_numbers, required=True,
        help="캡처할 모니터 번호(예: 1 또는 1,2)",
    )
    parser.add_argument(
        "-f", "--fps", type=positive_int, default=1,
        help="초당 캡처 횟수(기본값: 1)",
    )
    parser.add_argument(
        "-s", "--scale", type=scale_percent, default=10.0,
        help="모니터 한 칸의 크기 백분율(기본값: 10, '10%%'도 허용)",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    app = QApplication(sys.argv)

    try:
        window = MonitorPIP(args.monitor, args.fps, args.scale)
    except ValueError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 2

    app.aboutToQuit.connect(window.release)
    window.show()
    window.capture()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
