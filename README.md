# MonitorPIP

여러 모니터의 화면을 하나의 항상 위 PIP 창에서 실시간으로 확인하는 Python 앱입니다.
Windows, macOS, Linux에서 같은 명령줄 옵션과 UI로 실행할 수 있습니다.

## 주요 기능

- 모니터 한 대 또는 여러 대를 격자로 표시
- FPS와 최초 PIP 크기를 명령줄에서 지정
- PIP 창을 자유롭게 확대·축소
- 화면 안에서 좌클릭 드래그로 특정 영역만 확대
- 우클릭 또는 더블클릭으로 전체 화면 복귀
- PIP가 캡처 대상 화면 위에 있어도 재귀 화면이 생기지 않도록 창 영역을 시작 시점의 배경으로 복원
- Windows, macOS, Linux X11 및 Linux Wayland 지원

## 요구 사항

- Python 3.10 이상
- Windows 10/11, 최신 macOS 또는 데스크톱 Linux
- Linux Wayland: PipeWire 0.3과 XDG Desktop Portal ScreenCast 서비스

## 설치

저장소를 내려받은 뒤 가상 환경을 만들고 의존성을 설치합니다.

### Windows PowerShell

```powershell
git clone https://github.com/rufree365/MonitorPIP.git
cd MonitorPIP
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### macOS / Linux

```bash
git clone https://github.com/rufree365/MonitorPIP.git
cd MonitorPIP
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## 실행

모니터 번호는 1부터 시작합니다.

```bash
# 1번 모니터, 기본 1 FPS, 기본 10% 크기
python MonitorPIP.py -i 1

# 1번과 2번 모니터를 격자로 표시
python MonitorPIP.py -i 1,2

# 1번과 2번 모니터, 5 FPS, 모니터 한 칸당 15% 크기
python MonitorPIP.py -i 1,2 -f 5 -s 15

# % 기호도 사용 가능(셸에 따라 따옴표 권장)
python MonitorPIP.py -i 1 -s "10%"
```

### 옵션

| 옵션 | 설명 | 기본값 |
| --- | --- | --- |
| `-i`, `--monitor` | 캡처할 모니터 번호. 여러 대는 `1,2`처럼 지정 | 필수 |
| `-f`, `--fps` | 초당 캡처 횟수 | `1` |
| `-s`, `--scale` | 모니터 한 칸의 최초 크기(백분율) | `10` |
| `--backend` | `auto`, `mss`, `qt` 중 캡처 방식 선택 | `auto` |

일반적으로 `--backend`는 지정할 필요가 없습니다. `auto`는 Windows, macOS 및 Linux X11에서 `mss`를 사용하고 Linux Wayland에서는 Qt Multimedia를 사용합니다.

## 조작 방법

| 조작 | 동작 |
| --- | --- |
| 창 테두리 드래그 | PIP 창 확대·축소 |
| 화면 위 좌클릭 드래그 | 선택 영역만 확대 표시 |
| 화면 위 우클릭 | 선택 영역 초기화 |
| 화면 위 더블클릭 | 선택 영역 초기화 |
| `Esc` | 앱 종료 |

## 운영체제별 안내

### Windows

별도 설정 없이 실행됩니다. Windows 디스플레이 설정에서 서로 다른 배율을 사용하는 경우에도 각 모니터의 논리 좌표와 실제 캡처 픽셀 비율을 보정합니다.

### macOS

최초 실행 시 화면 기록 권한을 허용해야 합니다.

1. **시스템 설정 → 개인정보 보호 및 보안 → 화면 및 시스템 오디오 기록**을 엽니다.
2. Python 또는 앱을 실행한 Terminal/iTerm/IDE를 허용합니다.
3. 해당 프로그램을 완전히 종료한 뒤 다시 실행합니다.

### Linux X11

`mss` 백엔드가 자동으로 사용됩니다. 일반적인 X11 데스크톱에서는 별도 화면 선택 과정 없이 실행됩니다.

### Linux Wayland

Wayland 보안 정책상 애플리케이션이 모니터 화면을 임의로 직접 읽거나 대상 모니터를 API로 강제 선택할 수 없습니다. 앱은 Qt Multimedia와 XDG Desktop Portal/PipeWire를 사용하며, 실행 시 운영체제가 표시하는 화면 선택 창에서 캡처할 모니터를 선택해야 합니다.

`-i 1,2`를 사용하면 화면 선택 창이 순서대로 표시됩니다. 각 창에서 PIP의 Monitor 1, Monitor 2에 연결할 화면을 선택하세요. Portal 또는 PipeWire가 설치되어 있지 않으면 배포판 패키지 관리자로 다음 구성 요소를 설치해야 합니다.

- `pipewire`
- `xdg-desktop-portal`
- 데스크톱 환경용 Portal 구현체(예: `xdg-desktop-portal-gnome`, `xdg-desktop-portal-kde`, `xdg-desktop-portal-gtk`)

Wayland 화면 캡처는 Qt에서 실험적 기능으로 분류되므로 데스크톱 환경과 Portal 구현체에 따라 동작이 다를 수 있습니다. 문제가 있으면 로그인 화면에서 X11/Xorg 세션을 선택하거나 다음처럼 Qt 백엔드를 명시해 진단할 수 있습니다.

```bash
python MonitorPIP.py -i 1 --backend qt
```

관련 제한 사항은 [Qt for Python의 QScreenCapture 문서](https://doc.qt.io/qtforpython-6/PySide6/QtMultimedia/QScreenCapture.html#screen-capture-limitations)에서도 확인할 수 있습니다.

## 재귀 화면 방지 방식

앱은 PIP 창을 표시하기 전에 각 대상 모니터의 화면을 한 번 저장합니다. 이후 실시간 프레임에서 PIP 창과 대상 모니터가 겹치는 부분만 저장된 화면으로 대체합니다. 따라서 PIP 내부에 PIP가 반복되는 재귀 화면이 나타나지 않습니다.

복원 영역은 앱 시작 시점의 정지 화면입니다. PIP 창 아래에 있는 다른 창의 내용이 이후 변경되더라도 PIP가 차지하는 부분에는 시작 시점의 이미지가 표시됩니다.

## 문제 해결

- **검은 화면**: macOS 화면 기록 권한 또는 Linux Portal/PipeWire 상태를 확인하세요.
- **잘못된 모니터가 표시됨**: `-i` 번호를 바꾸어 실행하세요. Wayland에서는 OS 화면 선택 창에서 직접 선택해야 합니다.
- **CPU 사용량이 높음**: `-f` 값을 낮추거나 `-s` 값을 줄이세요.
- **자동 백엔드 문제**: `--backend mss` 또는 `--backend qt`를 명시하여 비교하세요.

