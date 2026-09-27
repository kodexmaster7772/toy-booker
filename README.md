# KTX Auto Booker Server

Cursor 없이 실행하는 Windows용 개인 KTX 예약 보조 서버입니다.

현재 버전: **1.1.1**

- 프론트엔드와 백엔드를 `http://127.0.0.1:8000` 하나로 통합
- Node.js와 5173 서버는 실행할 필요 없음
- Windows 자동 시작 기능 없음
- 사용자가 `START_SERVER.bat` / `STOP_SERVER.bat`로 직접 제어
- Tailscale 설치 시 집 밖에서도 안전하게 접속 가능
- CAPTCHA·본인인증·결제는 자동 우회하지 않으며 사용자가 직접 처리

## 처음 한 번만

압축을 푼 뒤 `INSTALL_ONCE.bat`를 더블클릭합니다. Python 패키지와 자동화용 Chromium을
설치하므로 인터넷 연결이 필요하고 몇 분 걸릴 수 있습니다.

Python 3.11 또는 3.12가 없다면 먼저 설치해야 합니다.

## 평소 사용법

| 원하는 작업 | 실행 파일 |
|---|---|
| 서버 열기 | `START_SERVER.bat` |
| 서버 닫기 | `STOP_SERVER.bat` |
| 화면만 다시 열기 | `OPEN_SERVER.bat` |
| 최신 버전으로 업데이트 | `UPDATE.bat` |
| 실제 코레일 모드 | `MODE_REAL_KORAIL.bat` |
| 안전한 데모 모드 | `MODE_DEMO.bat` |

서버가 열린 뒤 접속 주소는 다음과 같습니다.

```text
http://127.0.0.1:8000
```

검은 서버 창은 실행 상태와 로그를 보여줍니다. 창을 직접 닫아도 되지만,
정상적인 종료는 `STOP_SERVER.bat`를 사용하는 것을 권장합니다.

## 업데이트

새 버전이 올라오면 `UPDATE.bat`을 더블클릭합니다. 실행 중인 서버를 안전하게
종료하고, GitHub의 최신 정식 버전을 검증한 뒤 설치하고 서버를 다시 엽니다.

- `.env`, 예약 기록 DB, 코레일 로그인 프로필은 그대로 보존됩니다.
- 업데이트 직전 프로그램은 `data/update-backups`에 백업됩니다.
- 다운로드나 설치가 실패하면 직전 버전으로 자동 복구됩니다.
- 백업은 디스크 사용량을 줄이기 위해 최근 3개만 보관합니다.

소스 코드와 최신 배포본: <https://github.com/kodexmaster7772/toy-booker>

## 권장 실행 순서

1. `INSTALL_ONCE.bat` 실행
2. `MODE_DEMO.bat` 실행
3. `START_SERVER.bat` 실행
4. 데모 예약 성공 확인
5. `STOP_SERVER.bat` 실행
6. `MODE_REAL_KORAIL.bat` 실행
7. `START_SERVER.bat` 실행
8. 설정 화면에서 코레일 계정 저장
9. 재시도 간격을 20초 이상으로 설정
10. 예약하기 화면에서 조건을 입력하고 예약 시작

## 실제 코레일 예약 흐름

실제 모드에서는 다음 순서로 동작합니다.

1. 코레일 로그인 화면을 열고 저장된 계정으로 로그인
2. 새 코레일 승차권 사이트에서 출발역과 도착역 선택
3. 날짜 달력과 출발 시간 선택
4. 열차 조회 결과에서 일반실·특실 조건에 맞는 예매 버튼 탐색
5. 좌석이 없으면 설정된 간격 후 재조회
6. 좌석을 확보하면 브라우저를 그대로 열어두고 알림 표시
7. 사용자가 코레일 화면에서 예약 상태를 확인하고 직접 결제

계정을 저장하지 않은 경우에는 열린 코레일 브라우저에서 5분 안에 직접 로그인할 수 있습니다.
CAPTCHA, 본인인증, 결제는 사용자가 직접 처리해야 합니다.

실제 모드는 컴퓨터에 설치된 정식 Chrome을 우선 사용하고 별도의
`data/korail-browser-profile`에 로그인 쿠키를 보관합니다. 코레일의
`통신 중 에러` 안내가 한 번 나타나면 자동으로 확인 후 새로고침합니다.

코레일은 과도한 매크로 조회를 제한할 수 있습니다. 실제 모드는 설정값이 더 짧더라도
최소 20초 간격으로 조회하며, 개인 승차권 예약 보조 용도로만 사용하세요.

## 집 밖에서 접속

공유기 포트포워딩은 사용하지 않는 것을 권장합니다.

1. 서버 PC와 휴대폰에 Tailscale 설치
2. 두 기기에서 같은 계정으로 로그인
3. PC에서 `START_SERVER.bat` 실행
4. 검은 서버 창에 표시되는 `외부 접속` 주소를 휴대폰 브라우저에서 열기

주소 예시:

```text
http://100.x.x.x:8000
```

서버 PC가 꺼져 있거나 `STOP_SERVER.bat`로 서버를 닫은 상태에서는 외부에서도 접속되지 않습니다.

## 폴더 구조

```text
START_SERVER.bat              수동 서버 시작
STOP_SERVER.bat               수동 서버 종료
UPDATE.bat                    최신 버전 설치 및 자동 복구
INSTALL_ONCE.bat              최초 설치
MODE_REAL_KORAIL.bat          실제 브라우저 모드 전환
MODE_DEMO.bat                 데모 모드 전환
frontend/dist/                완성된 한국어 화면
backend/app/                  FastAPI API와 예약 엔진
backend/selectors/korail.json 코레일 화면 선택자
data/                         SQLite DB와 실행 PID
```

## 개발자용 검증

```powershell
python -m pytest -q
```

프론트엔드를 수정할 때만 Node.js가 필요합니다.

```powershell
cd frontend
npm.cmd install
npm.cmd run build
```
