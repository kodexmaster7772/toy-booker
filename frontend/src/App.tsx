import { FormEvent, ReactNode, useEffect, useMemo, useRef, useState } from "react";
import {
  Bell,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  CircleAlert,
  Clock3,
  Download,
  FileText,
  HelpCircle,
  Info,
  List,
  LoaderCircle,
  Menu,
  RefreshCw,
  Save,
  Settings as SettingsIcon,
  Square,
  TrainFront,
  Trash2,
  X,
  XCircle,
} from "lucide-react";
import { api, connectEvents } from "./api";
import type {
  ApiEvent,
  AppSettings,
  BookingPayload,
  LogEntry,
  PageKey,
  Reservation,
  ReservationStatus,
  StatusResponse,
} from "./types";

const DEFAULT_SETTINGS: AppSettings = {
  autoPayment: false,
  cancellationDetection: true,
  retryCount: 10,
  retryInterval: 20,
  browserNotification: true,
  soundNotification: true,
  emailNotification: false,
  credentialsConfigured: false,
  automationMode: "mock",
};

const IDLE_STATUS: StatusResponse = {
  state: "IDLE",
  label: "대기중",
  attemptCount: 0,
};

const NAV_ITEMS: Array<{ key: PageKey; label: string; icon: typeof TrainFront }> = [
  { key: "booking", label: "예약하기", icon: TrainFront },
  { key: "reservations", label: "예약현황", icon: List },
  { key: "settings", label: "설정", icon: SettingsIcon },
  { key: "logs", label: "로그", icon: FileText },
];

const ACTIVE_STATES = new Set<ReservationStatus>([
  "QUEUED",
  "STARTING",
  "LOGIN",
  "SEARCHING",
  "WAITING",
  "SEAT_FOUND",
  "RESERVING",
]);

function dateAfter(days: number): string {
  const value = new Date();
  value.setDate(value.getDate() + days);
  return value.toISOString().slice(0, 10);
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(`${value}T00:00:00`));
}

function formatTimestamp(value: string): string {
  return new Intl.DateTimeFormat("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

function statusMeta(status: ReservationStatus) {
  if (status === "RESERVED") return { label: "확정", tone: "success", icon: CheckCircle2 };
  if (status === "FAILED") return { label: "실패", tone: "danger", icon: XCircle };
  if (status === "STOPPED") return { label: "중지", tone: "muted", icon: Square };
  if (status === "USER_ACTION_REQUIRED") {
    return { label: "확인 필요", tone: "warning", icon: CircleAlert };
  }
  return { label: "대기중", tone: "warning", icon: Clock3 };
}

function StatusBadge({ status }: { status: ReservationStatus }) {
  const meta = statusMeta(status);
  const Icon = meta.icon;
  return (
    <span className={`badge badge-${meta.tone}`}>
      <Icon size={13} /> {meta.label}
    </span>
  );
}

function LevelBadge({ level }: { level: LogEntry["level"] }) {
  const labels = { INFO: "정보", WARNING: "경고", ERROR: "오류", SUCCESS: "성공" };
  return <span className={`badge badge-${level.toLowerCase()}`}>{labels[level]}</span>;
}

function Toggle({
  checked,
  onChange,
  disabled = false,
  label,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  label: string;
}) {
  return (
    <button
      type="button"
      className={`toggle ${checked ? "toggle-on" : ""}`}
      onClick={() => !disabled && onChange(!checked)}
      disabled={disabled}
      aria-label={label}
      aria-pressed={checked}
    >
      <span />
    </button>
  );
}

function Sidebar({
  page,
  onPage,
  open,
  onClose,
}: {
  page: PageKey;
  onPage: (value: PageKey) => void;
  open: boolean;
  onClose: () => void;
}) {
  return (
    <>
      <aside className={`sidebar ${open ? "sidebar-open" : ""}`}>
        <div className="brand">
          <TrainFront size={22} />
          <span>KTX AUTO<br />BOOKER</span>
          <button className="icon-button sidebar-close" onClick={onClose} aria-label="메뉴 닫기">
            <X size={20} />
          </button>
        </div>
        <nav>
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.key}
                className={page === item.key ? "nav-active" : ""}
                onClick={() => {
                  onPage(item.key);
                  onClose();
                }}
              >
                <Icon size={19} /> {item.label}
              </button>
            );
          })}
        </nav>
      </aside>
      {open && <button className="scrim" onClick={onClose} aria-label="메뉴 닫기" />}
    </>
  );
}

function BookingPage({
  status,
  logs,
  busy,
  onStart,
  onStop,
}: {
  status: StatusResponse;
  logs: LogEntry[];
  busy: boolean;
  onStart: (payload: BookingPayload) => Promise<void>;
  onStop: () => Promise<void>;
}) {
  const [form, setForm] = useState<BookingPayload>({
    departure: "익산",
    arrival: "서울",
    date: dateAfter(7),
    startTime: "06:00",
    endTime: "12:00",
    seatType: "GENERAL",
    includeFirstClass: false,
    allowStanding: false,
    detectCancellation: true,
  });

  const running = status.state !== "IDLE" && ACTIVE_STATES.has(status.state as ReservationStatus);
  const stations = ["서울", "용산", "광명", "수원", "천안아산", "대전", "익산", "광주송정", "동대구", "울산", "부산"];
  const timeSlots = [
    ["00:00", "06:00", "새벽 (00:00-06:00)"],
    ["06:00", "12:00", "오전 (06:00-12:00)"],
    ["12:00", "18:00", "오후 (12:00-18:00)"],
    ["18:00", "23:59", "저녁 (18:00-24:00)"],
  ];
  const selectedSlot = `${form.startTime}|${form.endTime}`;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    await onStart(form);
  };

  return (
    <section className="booking-layout">
      <form className="panel booking-form" onSubmit={submit}>
        <h2>예약 정보</h2>
        <label>
          <span>출발역</span>
          <div className="select-wrap">
            <select value={form.departure} onChange={(e) => setForm({ ...form, departure: e.target.value })}>
              {stations.map((station) => <option key={station}>{station}</option>)}
            </select>
            <ChevronDown size={16} />
          </div>
        </label>
        <label>
          <span>도착역</span>
          <div className="select-wrap">
            <select value={form.arrival} onChange={(e) => setForm({ ...form, arrival: e.target.value })}>
              {stations.map((station) => <option key={station}>{station}</option>)}
            </select>
            <ChevronDown size={16} />
          </div>
        </label>
        <label>
          <span>날짜</span>
          <div className="input-icon-wrap">
            <CalendarDays size={17} />
            <input
              type="date"
              min={new Date().toISOString().slice(0, 10)}
              value={form.date}
              onChange={(e) => setForm({ ...form, date: e.target.value })}
              required
            />
          </div>
        </label>
        <label>
          <span>시간대</span>
          <div className="select-wrap">
            <select
              value={selectedSlot}
              onChange={(e) => {
                const [startTime, endTime] = e.target.value.split("|");
                setForm({ ...form, startTime, endTime });
              }}
            >
              {timeSlots.map(([start, end, label]) => (
                <option key={start} value={`${start}|${end}`}>{label}</option>
              ))}
            </select>
            <ChevronDown size={16} />
          </div>
        </label>
        <label>
          <span>좌석</span>
          <div className="select-wrap">
            <select value={form.seatType} onChange={(e) => setForm({ ...form, seatType: e.target.value as "GENERAL" | "FIRST" })}>
              <option value="GENERAL">일반실</option>
              <option value="FIRST">특실</option>
            </select>
            <ChevronDown size={16} />
          </div>
        </label>
        <div className="check-list">
          <label><input type="checkbox" checked={form.includeFirstClass} onChange={(e) => setForm({ ...form, includeFirstClass: e.target.checked })} /> 특실 포함</label>
          <label><input type="checkbox" checked={form.allowStanding} onChange={(e) => setForm({ ...form, allowStanding: e.target.checked })} /> 입석 허용</label>
          <label><input type="checkbox" checked={form.detectCancellation} onChange={(e) => setForm({ ...form, detectCancellation: e.target.checked })} /> 취소표 감지</label>
        </div>
        {running ? (
          <button className="primary-button danger-button" type="button" onClick={onStop} disabled={busy}>
            <Square size={16} /> 예약 중지
          </button>
        ) : (
          <button className="primary-button" type="submit" disabled={busy}>
            {busy ? <LoaderCircle className="spin" size={18} /> : <TrainFront size={18} />}
            예약 시작
          </button>
        )}
      </form>

      <div className="side-panels">
        <article className="panel status-card">
          <h2>현재 상태</h2>
          <div className="status-line">
            <span className={`status-icon ${status.state === "RESERVED" ? "status-success" : ""}`}>
              {running ? <LoaderCircle className="spin" size={22} /> : status.state === "RESERVED" ? <CheckCircle2 size={22} /> : <Clock3 size={22} />}
            </span>
            <div>
              <strong>{status.label}</strong>
              {status.message && <p>{status.message}</p>}
              {status.attemptCount > 0 && <small>조회 {status.attemptCount}회</small>}
            </div>
          </div>
        </article>
        <article className="panel activity-card">
          <h2>활동 로그</h2>
          {logs.length === 0 ? <p className="empty-text">로그가 없습니다.</p> : (
            <ul className="mini-log-list">
              {logs.slice(0, 6).map((log) => (
                <li key={log.id}>
                  <span className={`log-dot dot-${log.level.toLowerCase()}`} />
                  <div><strong>{log.message}</strong><small>{formatTimestamp(log.timestamp)}</small></div>
                </li>
              ))}
            </ul>
          )}
        </article>
      </div>
    </section>
  );
}

function ReservationsPage({ reservations, onSelect }: { reservations: Reservation[]; onSelect: (value: Reservation) => void }) {
  return (
    <section>
      <header className="page-header">
        <h1>예약 현황</h1>
        <p>진행중이거나 완료된 예약 내역을 확인할 수 있습니다.</p>
      </header>
      <div className="panel table-panel">
        <h2>예약 목록</h2>
        {reservations.length === 0 ? (
          <div className="empty-state"><TrainFront size={32} /><p>아직 예약 내역이 없습니다.</p></div>
        ) : (
          <div className="table-scroll">
            <table>
              <thead><tr><th>열차번호</th><th>출발</th><th>도착</th><th>날짜</th><th>시간</th><th>좌석</th><th>상태</th><th>작업</th></tr></thead>
              <tbody>
                {reservations.map((item) => (
                  <tr key={item.id}>
                    <td>{item.trainNumber ?? "확인 중"}</td>
                    <td>{item.departure}</td>
                    <td>{item.arrival}</td>
                    <td>{item.travelDate}</td>
                    <td>{item.departureTime?.slice(0, 5) ?? "-"}</td>
                    <td>{item.seat ?? "-"}</td>
                    <td><StatusBadge status={item.status} /></td>
                    <td><button className="text-button" onClick={() => onSelect(item)}>상세보기</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}

function SettingsPage({
  settings,
  onSave,
  onSaveCredentials,
}: {
  settings: AppSettings;
  onSave: (value: AppSettings) => Promise<void>;
  onSaveCredentials: (accountId: string, password: string) => Promise<void>;
}) {
  const [draft, setDraft] = useState(settings);
  const [accountId, setAccountId] = useState("");
  const [password, setPassword] = useState("");
  const [saving, setSaving] = useState(false);
  useEffect(() => setDraft(settings), [settings]);

  const saveAutomation = async () => {
    setSaving(true);
    try { await onSave(draft); } finally { setSaving(false); }
  };
  const saveAccount = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    try {
      await onSaveCredentials(accountId, password);
      setPassword("");
    } finally { setSaving(false); }
  };

  const settingRow = (
    title: string,
    description: string,
    key: "cancellationDetection" | "browserNotification" | "soundNotification" | "emailNotification",
  ) => (
    <div className="setting-row">
      <div><strong>{title}</strong><p>{description}</p></div>
      <Toggle checked={draft[key]} onChange={(checked) => setDraft({ ...draft, [key]: checked })} label={title} />
    </div>
  );

  return (
    <section>
      <header className="page-header">
        <h1>설정</h1>
        <p>예약 자동화 및 알림 설정을 관리합니다.</p>
      </header>
      <div className="settings-column">
        <form className="panel settings-panel" onSubmit={saveAccount}>
          <h2>계정 설정</h2>
          <p className="section-description">코레일 회원 정보를 입력하세요. 비밀번호는 운영체제 자격증명 저장소에 보관됩니다.</p>
          <label><span>회원번호 / 이메일 / 휴대폰</span><input value={accountId} onChange={(e) => setAccountId(e.target.value)} placeholder={settings.credentialsConfigured ? "저장된 계정이 있습니다" : "코레일 로그인 계정"} required /></label>
          <label><span>비밀번호</span><input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" required /></label>
          <button className="small-button" disabled={saving}><Save size={15} /> 저장</button>
          {settings.credentialsConfigured && <span className="saved-hint"><CheckCircle2 size={14} /> 계정 저장됨</span>}
        </form>

        <div className="panel settings-panel">
          <h2>자동화 설정</h2>
          <p className="section-description">예약 시도 및 재시도 관련 설정입니다.</p>
          <div className="setting-row disabled-setting">
            <div><strong>자동 결제</strong><p>안전을 위해 좌석 확보 후 직접 결제합니다.</p></div>
            <Toggle checked={false} onChange={() => undefined} disabled label="자동 결제" />
          </div>
          {settingRow("취소표 자동 감지", "취소된 좌석을 자동으로 감지하고 예약합니다.", "cancellationDetection")}
          <label className="stacked-field"><span>재시도 횟수</span><input type="number" min={1} max={1000} value={draft.retryCount} onChange={(e) => setDraft({ ...draft, retryCount: Number(e.target.value) })} /></label>
          <label className="stacked-field"><span>재시도 간격 (초)</span><input type="number" min={15} max={300} step={1} value={draft.retryInterval} onChange={(e) => setDraft({ ...draft, retryInterval: Number(e.target.value) })} /></label>
          <p className="section-description">실제 코레일 모드는 이용 제한을 줄이기 위해 최소 20초 간격으로 조회합니다.</p>
        </div>

        <div className="panel settings-panel">
          <h2>알림 설정</h2>
          <p className="section-description">예약 상태 변경 시 알림을 받습니다.</p>
          {settingRow("브라우저 알림", "데스크톱 알림을 받습니다.", "browserNotification")}
          {settingRow("사운드 알림", "예약 성공 시 소리로 알립니다.", "soundNotification")}
          {settingRow("이메일 알림", "향후 이메일 연동을 위한 설정입니다.", "emailNotification")}
          <button className="primary-button settings-save" onClick={saveAutomation} disabled={saving}>
            {saving ? <LoaderCircle className="spin" size={17} /> : <Save size={17} />} 설정 저장
          </button>
        </div>

        <div className="mode-note">
          <Info size={18} /> 현재 자동화 모드: <strong>{settings.automationMode === "mock" ? "데모(mock)" : "실제 브라우저(playwright)"}</strong>
        </div>
      </div>
    </section>
  );
}

function LogsPage({ logs, onClear }: { logs: LogEntry[]; onClear: () => Promise<void> }) {
  return (
    <section>
      <header className="page-header actions-header">
        <div><h1>로그</h1><p>모든 예약 활동 기록을 확인할 수 있습니다.</p></div>
        <div className="header-actions">
          <a className="outline-button" href="/api/logs/export"><Download size={16} /> 내보내기</a>
          <button className="outline-button" onClick={onClear}><Trash2 size={16} /> 전체 삭제</button>
        </div>
      </header>
      <div className="panel log-panel">
        <h2>활동 기록</h2>
        {logs.length === 0 ? <div className="empty-state"><FileText size={32} /><p>아직 활동 로그가 없습니다.</p></div> : (
          <div className="log-list">
            {logs.map((log) => (
              <article key={log.id}>
                <time>{formatTimestamp(log.timestamp)}</time>
                <LevelBadge level={log.level} />
                <strong>{log.message}</strong>
              </article>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function Modal({ children, onClose }: { children: ReactNode; onClose: () => void }) {
  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div className="modal" onMouseDown={(e) => e.stopPropagation()}>
        <button className="icon-button modal-close" onClick={onClose}><X size={20} /></button>
        {children}
      </div>
    </div>
  );
}

function App() {
  const [page, setPage] = useState<PageKey>("booking");
  const [menuOpen, setMenuOpen] = useState(false);
  const [status, setStatus] = useState<StatusResponse>(IDLE_STATUS);
  const [reservations, setReservations] = useState<Reservation[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [settings, setSettings] = useState<AppSettings>(DEFAULT_SETTINGS);
  const [selected, setSelected] = useState<Reservation | null>(null);
  const [helpOpen, setHelpOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const previousState = useRef(status.state);

  const showToast = (text: string, tone: "success" | "error" = "success") => {
    setToast({ text, tone });
    window.setTimeout(() => setToast(null), 3500);
  };

  const refreshLists = async () => {
    const [reservationValues, logValues] = await Promise.all([api.getReservations(), api.getLogs()]);
    setReservations(reservationValues);
    setLogs(logValues);
  };

  useEffect(() => {
    Promise.all([api.getStatus(), api.getReservations(), api.getLogs(), api.getSettings()])
      .then(([statusValue, reservationValues, logValues, settingValues]) => {
        setStatus(statusValue);
        setReservations(reservationValues);
        setLogs(logValues);
        setSettings(settingValues);
      })
      .catch((error: Error) => showToast(`백엔드 연결 실패: ${error.message}`, "error"));

    const disconnect = connectEvents((event: ApiEvent) => {
      if (event.type === "status" && event.data) {
        setStatus(event.data as unknown as StatusResponse);
        void refreshLists();
        void api.getSettings().then(setSettings).catch(() => undefined);
      } else if (event.type === "log" || event.type === "logsCleared") {
        void refreshLists();
      }
    });
    const poll = window.setInterval(() => api.getStatus().then(setStatus).catch(() => undefined), 5000);
    return () => { disconnect(); window.clearInterval(poll); };
  }, []);

  useEffect(() => {
    if (status.state === "RESERVED" && previousState.current !== "RESERVED") {
      if (settings.browserNotification && "Notification" in window && Notification.permission === "granted") {
        new Notification("KTX 좌석 확보", { body: status.message ?? "예약 가능한 좌석을 확보했습니다." });
      }
      if (settings.soundNotification) {
        const AudioContextClass = window.AudioContext ?? (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
        if (AudioContextClass) {
          const context = new AudioContextClass();
          const oscillator = context.createOscillator();
          oscillator.frequency.value = 880;
          oscillator.connect(context.destination);
          oscillator.start();
          oscillator.stop(context.currentTime + 0.2);
        }
      }
    }
    previousState.current = status.state;
  }, [status, settings.browserNotification, settings.soundNotification]);

  const startReservation = async (payload: BookingPayload) => {
    setBusy(true);
    try {
      await api.startReservation(payload);
      setStatus(await api.getStatus());
      await refreshLists();
      showToast("예약 작업을 시작했습니다.");
    } catch (error) {
      showToast((error as Error).message, "error");
    } finally { setBusy(false); }
  };

  const stopReservation = async () => {
    setBusy(true);
    try {
      const result = await api.stopReservation();
      setStatus(await api.getStatus());
      await refreshLists();
      showToast(result.message);
    } catch (error) { showToast((error as Error).message, "error"); }
    finally { setBusy(false); }
  };

  const saveSettings = async (value: AppSettings) => {
    try {
      const { credentialsConfigured: _credentialsConfigured, automationMode: _automationMode, ...payload } = value;
      const saved = await api.saveSettings(payload);
      setSettings(saved);
      if (saved.browserNotification && "Notification" in window && Notification.permission === "default") {
        await Notification.requestPermission();
      }
      showToast("설정을 저장했습니다.");
    } catch (error) { showToast((error as Error).message, "error"); }
  };

  const saveCredentials = async (accountId: string, password: string) => {
    try {
      await api.saveCredentials(accountId, password);
      setSettings({ ...settings, credentialsConfigured: true });
      showToast("코레일 계정을 안전하게 저장했습니다.");
    } catch (error) { showToast((error as Error).message, "error"); }
  };

  const clearLogs = async () => {
    if (!window.confirm("모든 활동 로그를 삭제할까요?")) return;
    try {
      await api.clearLogs();
      setLogs([]);
      showToast("로그를 삭제했습니다.");
    } catch (error) { showToast((error as Error).message, "error"); }
  };

  const content = useMemo(() => {
    if (page === "booking") return <BookingPage status={status} logs={logs} busy={busy} onStart={startReservation} onStop={stopReservation} />;
    if (page === "reservations") return <ReservationsPage reservations={reservations} onSelect={setSelected} />;
    if (page === "settings") return <SettingsPage settings={settings} onSave={saveSettings} onSaveCredentials={saveCredentials} />;
    return <LogsPage logs={logs} onClear={clearLogs} />;
  }, [page, status, logs, busy, reservations, settings]);

  return (
    <div className="app-shell">
      <Sidebar page={page} onPage={setPage} open={menuOpen} onClose={() => setMenuOpen(false)} />
      <main>
        <div className="mobile-bar">
          <button className="icon-button" onClick={() => setMenuOpen(true)}><Menu /></button>
          <strong>KTX AUTO BOOKER</strong>
        </div>
        {content}
      </main>
      <button className="help-button" onClick={() => setHelpOpen(true)} aria-label="도움말"><HelpCircle size={22} /></button>
      {toast && <div className={`toast toast-${toast.tone}`}>{toast.tone === "success" ? <CheckCircle2 size={18} /> : <CircleAlert size={18} />}{toast.text}</div>}

      {selected && (
        <Modal onClose={() => setSelected(null)}>
          <h2>예약 상세</h2>
          <dl className="detail-list">
            <div><dt>열차번호</dt><dd>{selected.trainNumber ?? "확인 중"}</dd></div>
            <div><dt>구간</dt><dd>{selected.departure} → {selected.arrival}</dd></div>
            <div><dt>출발일</dt><dd>{formatDate(selected.travelDate)}</dd></div>
            <div><dt>출발시간</dt><dd>{selected.departureTime?.slice(0, 5) ?? "-"}</dd></div>
            <div><dt>좌석</dt><dd>{selected.seat ?? "-"}</dd></div>
            <div><dt>상태</dt><dd><StatusBadge status={selected.status} /></dd></div>
            <div className="detail-wide"><dt>메시지</dt><dd>{selected.message ?? "-"}</dd></div>
          </dl>
        </Modal>
      )}

      {helpOpen && (
        <Modal onClose={() => setHelpOpen(false)}>
          <h2>빠른 사용 방법</h2>
          <ol className="help-list">
            <li><span>1</span><div><strong>데모 모드 확인</strong><p>예약하기에서 조건을 입력하고 예약 시작을 누르세요.</p></div></li>
            <li><span>2</span><div><strong>상태와 로그 확인</strong><p>약 7초 후 mock 모드에서는 좌석 확보가 표시됩니다.</p></div></li>
            <li><span>3</span><div><strong>실사용 전환</strong><p>서버를 끈 뒤 MODE_REAL_KORAIL.bat을 실행하고 서버를 다시 시작하세요.</p></div></li>
          </ol>
          <div className="help-warning"><Bell size={18} /> CAPTCHA·본인인증과 결제는 열린 브라우저에서 직접 처리합니다.</div>
        </Modal>
      )}
    </div>
  );
}

export default App;
