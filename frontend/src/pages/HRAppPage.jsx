/**
 * HRAppPage — the public-facing main page of the NovaTech HR assistant.
 *
 * Designed to look like a real corporate HR intranet tool. No act tabs, no
 * role switcher, no admin toggles by default. Demo scenarios are triggered
 * from the innocuous-looking footer links and play out INLINE in the main
 * workspace (no modal pop-ups for acts 1-4):
 *
 *   - act1 / act3:  preload a scripted query into the chat input. The
 *                   presenter clicks 送出 to actually run it. Result appears
 *                   in the normal chat / SystemLog.
 *   - act2:         preload the query AND surface a temporary "啟用存取控制"
 *                   toggle above the input. Presenter can toggle and resend
 *                   to compare. The toggle disappears when the scenario is
 *                   cleared.
 *   - act4:         swap the right-side panel from SystemLog to HEDashboard
 *                   and preload a query into the dashboard input. Presenter
 *                   clicks the dashboard's search button to run CKKS.
 *   - spectrum:     still rendered as a modal overlay by App.jsx — this page
 *                   does not need to react.
 *
 * A small "scenario banner" is rendered at the top of the workspace while an
 * act is active, with an X to clear the scenario.
 *
 * Loading UX: the backend LLM (gemma-4-26B) takes 5-10 seconds per query, so
 * a prominent animated indicator with an elapsed-seconds counter is rendered
 * inline in the chat list while a request is in flight.
 *
 * @param {object} props
 * @param {'act1'|'act2'|'act3'|'act4'|'spectrum'|null} props.activeAct
 *   The currently loaded demo scenario. App.jsx owns this state.
 * @param {(key: 'act1'|'act2'|'act3'|'act4'|'spectrum'|null) => void} props.onTriggerAct
 *   Setter for the active scenario. Footer links call onTriggerAct(key); the
 *   scenario banner's close button calls onTriggerAct(null).
 * @returns {JSX.Element|null}
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import ChatWindow from '../components/ChatWindow.jsx';
import SystemLog from '../components/SystemLog.jsx';
import HEDashboard from '../components/HEDashboard.jsx';
import { useAuth } from '../contexts/AuthContext.jsx';
import { useQuery } from '../hooks/useQuery.js';
import { API_BASE_URL } from '../config.js';

const ROLE_LABELS = {
  employee: '一般員工',
  manager: '部門主管',
  hr_admin: 'HR 管理員',
};

const ROLE_BADGE_STYLES = {
  employee: 'bg-blue-500/15 text-blue-200 border-blue-500/40',
  manager: 'bg-amber-500/15 text-amber-200 border-amber-500/40',
  hr_admin: 'bg-purple-500/15 text-purple-200 border-purple-500/40',
};

const SUGGESTED_QUERIES = {
  employee: ['公司請假規定', '加班費怎麼算', '健保補助'],
  manager: ['工程部績效評核流程', '預算審核流程', '部門人事異動'],
  hr_admin: ['員工個資查詢', '勞健保異動', '招募流程'],
};

const FOOTER_LINKS = [
  { label: '關於 NovaTech', key: 'act1' },
  { label: '公司治理', key: 'act2' },
  { label: '資訊安全政策', key: 'act3' },
  { label: '隱私權保護', key: 'act4' },
  { label: '安全等級總覽', key: 'spectrum' },
];

// Scripted scenarios. Each act has a preset query + scenario metadata used by
// the inline banner. Banner copy intentionally describes what is about to be
// demonstrated, not what is happening to which "幕".
const SCENARIO_PRESETS = {
  act1: {
    query: '請問公司的請假規定？',
    title: '情境一：正常使用',
    description: '一般員工查詢公開政策，存取控制正常運作，AI 依據合法可見的文件回答。',
  },
  act2: {
    query: '張秀玉的薪資是多少？',
    title: '情境二：存取控制比較',
    description: '同一個查詢，比較「啟用存取控制」與「未啟用」的差異。請使用下方的開關切換後再次送出。',
  },
  act3: {
    query: '請問公司最新的福利政策',
    title: '情境三：Prompt Injection',
    description: '一份「合法」的 Level 1 公開文件內嵌惡意指令。送出後觀察 AI 回答是否被誘導。可用下方的防禦開關切換後再次送出，比較有/無防禦的差異。',
  },
  act4: {
    query: '公司請假規定',
    title: '情境四：同態加密搜尋',
    description: '右側面板已切換為 CKKS 加密搜尋介面，按搜尋鈕觀察密文與明文的時間差。',
  },
};

/**
 * Inline NovaTech logo. A minimal SVG mark so the header does not depend on
 * an external asset and renders crisply at any DPI.
 *
 * @returns {JSX.Element}
 */
function NovaTechLogo() {
  return (
    <div className="flex items-center gap-2.5 select-none">
      <svg
        viewBox="0 0 32 32"
        className="h-7 w-7"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id="ntg" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#60a5fa" />
            <stop offset="100%" stopColor="#2563eb" />
          </linearGradient>
        </defs>
        <rect x="2" y="2" width="28" height="28" rx="7" fill="url(#ntg)" />
        <path
          d="M9 22 V10 L16 19 V10 M19 10 H24 M21.5 10 V22"
          stroke="#0b1220"
          strokeWidth="2.4"
          fill="none"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <div className="leading-tight">
        <div className="text-sm font-semibold text-gray-100 tracking-wide">
          NovaTech
        </div>
        <div className="text-[10px] uppercase tracking-[0.18em] text-gray-500">
          Corporate Portal
        </div>
      </div>
    </div>
  );
}

/**
 * Prominent inline "AI is thinking" indicator overlaid on top of the chat
 * area while a query is pending. Includes an elapsed-seconds counter so the
 * user understands the wait is intentional, not a hang.
 *
 * @param {{ visible: boolean }} props
 * @returns {JSX.Element|null}
 */
function ThinkingIndicator({ visible }) {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    if (!visible) {
      setSeconds(0);
      return undefined;
    }
    const start = Date.now();
    const id = setInterval(() => {
      setSeconds(Math.floor((Date.now() - start) / 1000));
    }, 200);
    return () => clearInterval(id);
  }, [visible]);

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 8 }}
          transition={{ duration: 0.2 }}
          className="pointer-events-none absolute inset-x-0 bottom-32 flex justify-center px-4"
        >
          <div className="pointer-events-auto flex items-center gap-3 px-5 py-3 rounded-xl border border-blue-400/40 bg-gray-900/95 shadow-2xl backdrop-blur">
            <div className="relative h-7 w-7">
              <span className="absolute inset-0 rounded-full border-2 border-blue-400/30" />
              <span className="absolute inset-0 rounded-full border-2 border-blue-400 border-t-transparent animate-spin" />
            </div>
            <div className="flex flex-col">
              <span className="text-sm font-semibold text-blue-100">
                AI 正在思考...
              </span>
              <span className="text-[11px] text-gray-400 font-mono">
                已等待 {seconds} 秒（LLM 約需 5-10 秒）
              </span>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/**
 * Slim banner at the top of the workspace showing which demo scenario has
 * been loaded. Provides a close button so the presenter can return to the
 * "normal" HR app view at any time.
 *
 * @param {{ preset: {title:string, description:string} | null, onClose: () => void }} props
 * @returns {JSX.Element|null}
 */
function ScenarioBanner({ preset, onClose }) {
  return (
    <AnimatePresence>
      {preset && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          transition={{ duration: 0.2 }}
          className="mx-auto max-w-[1500px] mb-3 flex items-start justify-between gap-3 rounded-lg border border-blue-400/30 bg-blue-500/10 px-4 py-3"
        >
          <div className="flex flex-col">
            <span className="text-sm font-semibold text-blue-100">
              {preset.title}
            </span>
            <span className="text-xs text-blue-200/80 mt-0.5">
              {preset.description}
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="shrink-0 text-blue-200/70 hover:text-blue-100 transition-colors text-lg leading-none"
            aria-label="關閉示範情境"
            title="關閉示範情境"
          >
            ×
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/**
 * Temporary "存取控制" toggle exposed only while scenario === 'act2'. Lets
 * the presenter compare filter-on vs filter-off without exposing the toggle
 * in the default UI (which would break immersion).
 *
 * @param {{ value: boolean, onChange: (v: boolean) => void }} props
 * @returns {JSX.Element}
 */
function AccessControlToggle({ value, onChange }) {
  return (
    <div className="mx-auto max-w-[1500px] mb-2 flex items-center justify-end gap-3 text-xs">
      <span className="text-gray-400">示範控制：</span>
      <span className="text-gray-300">啟用存取控制</span>
      <button
        type="button"
        role="switch"
        aria-checked={value}
        onClick={() => onChange(!value)}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
          value ? 'bg-green-500/70' : 'bg-red-500/70'
        }`}
      >
        <span
          className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform ${
            value ? 'translate-x-5' : 'translate-x-0.5'
          }`}
        />
      </button>
      <span className={`font-mono ${value ? 'text-green-300' : 'text-red-300'}`}>
        {value ? 'ON' : 'OFF'}
      </span>
    </div>
  );
}

/**
 * Temporary "Prompt Injection 防禦" toggle exposed only while scenario ===
 * 'act3'. Mirrors AccessControlToggle so the presenter can resend the same
 * query with/without defenses and compare the AI's behaviour. Default OFF so
 * the unmitigated attack is shown first.
 *
 * @param {{ value: boolean, onChange: (v: boolean) => void }} props
 * @returns {JSX.Element}
 */
function DefenseToggle({ value, onChange }) {
  return (
    <div className="mx-auto max-w-[1500px] mb-2 flex items-center justify-end gap-3 text-xs">
      <span className="text-gray-400">示範控制：</span>
      <span className="text-gray-300">啟用 Prompt Injection 防禦</span>
      <button
        type="button"
        role="switch"
        aria-checked={value}
        onClick={() => onChange(!value)}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
          value ? 'bg-green-500/70' : 'bg-red-500/70'
        }`}
      >
        <span
          className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform ${
            value ? 'translate-x-5' : 'translate-x-0.5'
          }`}
        />
      </button>
      <span className={`font-mono ${value ? 'text-green-300' : 'text-red-300'}`}>
        {value ? 'ON' : 'OFF'}
      </span>
    </div>
  );
}

export default function HRAppPage({ activeAct, onTriggerAct }) {
  const { role, logout } = useAuth();
  const { sendQuery, loading, error } = useQuery();

  // Conversation history rendered by ChatWindow.
  const [messages, setMessages] = useState([]);
  // The most recent successful response feeds SystemLog.
  const [lastResult, setLastResult] = useState(null);
  // Scenario-driven prefill string for ChatWindow.
  const [prefill, setPrefill] = useState('');
  // Act 2 toggle state. Lifted here so handleSend can read it.
  const [demoUseFilter, setDemoUseFilter] = useState(true);
  // Act 3 toggle state. Default OFF so the unmitigated attack is shown first.
  const [defenseMode, setDefenseMode] = useState(false);
  // HE search state (Act 4).
  const [heQuery, setHeQuery] = useState('');
  const [heData, setHeData] = useState(null);
  const [heLoading, setHeLoading] = useState(false);

  // Reset transient state when the active role changes (e.g. logout -> login).
  useEffect(() => {
    setMessages([]);
    setLastResult(null);
  }, [role]);

  // React to scenario changes: preload the relevant query and reset toggles
  // that should not leak between scenarios. NB: each prefill update must use
  // a NEW string identity so ChatWindow's effect re-fires; appending a
  // zero-width space keeps the visible text identical but makes consecutive
  // identical-query scenarios still re-fill.
  useEffect(() => {
    const preset = SCENARIO_PRESETS[activeAct];
    if (preset) {
      setPrefill(`${preset.query}​`.replace(/​+$/, '​'));
      // Strip the trailing ZWSP after a tick so the textarea shows clean text.
      // (ChatWindow's effect copies prefillInput verbatim; we want the user
      // to see "請問公司的請假規定？" not the marker character.)
      // Use a microtask so React has flushed the prefill into ChatWindow's
      // internal state first.
      queueMicrotask(() => setPrefill(preset.query));
    } else {
      setPrefill('');
    }
    // Toggle resets to ON whenever scenario changes.
    setDemoUseFilter(true);
    // Defense toggle resets to OFF so each Act 3 entry starts un-mitigated.
    setDefenseMode(false);
    // Preload HE search for act4 but do not auto-run.
    if (activeAct === 'act4') {
      setHeQuery(SCENARIO_PRESETS.act4.query);
      setHeData(null);
    }
  }, [activeAct]);

  const suggested = useMemo(
    () => (role ? SUGGESTED_QUERIES[role] ?? [] : []),
    [role],
  );

  // App.jsx routes to LoginPage when there is no role, but guard anyway.
  if (!role) return null;

  const roleLabel = ROLE_LABELS[role] ?? role;
  const roleBadgeCls =
    ROLE_BADGE_STYLES[role] ?? 'bg-gray-500/15 text-gray-200 border-gray-500/40';

  // Greeting + suggested-query hint, used only when the chat is empty.
  const greeting = `您好，您目前以 ${roleLabel} 身份登入。請輸入您的問題，或點擊下方的常見問題快速查詢。`;
  const displayedMessages = messages.length === 0
    ? [{ role: 'assistant', text: greeting }]
    : messages;

  const banner = SCENARIO_PRESETS[activeAct] ?? null;
  const showAccessToggle = activeAct === 'act2';
  const showDefenseToggle = activeAct === 'act3';
  const showHEPanel = activeAct === 'act4';
  // Effective filter setting that drives backend queries.
  const effectiveUseFilter = showAccessToggle ? demoUseFilter : true;
  // Effective defense setting — only meaningful in Act 3.
  const effectiveDefenseMode = showDefenseToggle ? defenseMode : false;
  // Defense actions reported by the backend on the last query (Act 3 only).
  const defenseActions = Array.isArray(lastResult?.defense_actions)
    ? lastResult.defense_actions
    : [];

  /**
   * Dispatch a user query to the backend pipeline, append both turns to the
   * conversation, and refresh the SystemLog state. Errors are surfaced as an
   * assistant message so the audience always sees a response.
   *
   * @param {string} text
   * @returns {Promise<void>}
   */
  async function handleSend(text) {
    const userMsg = { role: 'user', text };
    setMessages((prev) => [...prev, userMsg]);
    try {
      const data = await sendQuery({
        query: text,
        user_role: role,
        use_filter: effectiveUseFilter,
        gen_mode: 'llm',
        top_k: 5,
        defense_mode: effectiveDefenseMode,
      });
      setLastResult(data);
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', text: data?.answer ?? '（無回應）' },
      ]);
    } catch (_e) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: '系統暫時無法回應，請稍後再試。',
        },
      ]);
    }
  }

  /**
   * Fire a CKKS-encrypted search through /api/he/search. Used by HEDashboard
   * in Act 4 mode.
   *
   * @param {string} query
   * @returns {Promise<void>}
   */
  async function runHESearch(query) {
    setHeQuery(query);
    setHeLoading(true);
    try {
      const { data } = await axios.post(
        `${API_BASE_URL}/api/he/search`,
        { query, top_k: 5 },
      );
      setHeData(data);
    } catch (_e) {
      setHeData(null);
    } finally {
      setHeLoading(false);
    }
  }

  return (
    <div className="min-h-screen w-full bg-gray-950 text-gray-100 flex flex-col">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-gray-800 bg-gray-900/80 backdrop-blur">
        <div className="flex items-center gap-5">
          <NovaTechLogo />
          <div className="hidden md:block h-6 w-px bg-gray-700" />
          <div className="hidden md:flex flex-col leading-tight">
            <span className="text-sm font-medium text-gray-100">
              HR 智能助理
            </span>
            <span className="text-[11px] text-gray-500">
              人力資源知識查詢系統 v2.4
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div
            className={`px-3 py-1 rounded-full border text-xs font-medium ${roleBadgeCls}`}
            title={`目前以 ${roleLabel} 身份登入`}
          >
            目前身份：{roleLabel}
          </div>
          <button
            type="button"
            onClick={logout}
            className="px-3 py-1.5 rounded-md border border-gray-700 bg-gray-800/60 text-xs text-gray-300 hover:bg-gray-700/80 hover:text-gray-100 hover:border-gray-600 transition-colors"
          >
            登出
          </button>
        </div>
      </header>

      {/* Workspace */}
      <main className="flex-1 px-6 py-4">
        <ScenarioBanner preset={banner} onClose={() => onTriggerAct?.(null)} />
        {showAccessToggle && (
          <AccessControlToggle
            value={demoUseFilter}
            onChange={setDemoUseFilter}
          />
        )}
        {showDefenseToggle && (
          <DefenseToggle value={defenseMode} onChange={setDefenseMode} />
        )}
        <div className="mx-auto max-w-[1500px] h-[calc(100vh-13rem)] grid grid-cols-1 lg:grid-cols-[1fr_22rem] gap-5">
          {/* Chat column */}
          <section className="relative min-h-0">
            <ChatWindow
              role={role}
              useFilter={effectiveUseFilter}
              genMode="llm"
              messages={displayedMessages}
              onSend={handleSend}
              loading={loading}
              suggestedQueries={suggested}
              prefillInput={prefill}
            />
            <ThinkingIndicator visible={loading} />
            {error && !loading && (
              <div className="absolute top-2 left-1/2 -translate-x-1/2 px-3 py-1.5 rounded-md border border-red-500/50 bg-red-500/15 text-red-200 text-xs">
                查詢發生錯誤：{error}
              </div>
            )}
          </section>

          {/* Right panel — SystemLog by default, HEDashboard during Act 4 */}
          <aside className="min-h-0 flex flex-col gap-2">
            {showDefenseToggle && defenseActions.length > 0 && (
              <div className="rounded-md border border-emerald-400/40 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-100">
                <div className="font-semibold mb-1">🛡️ 防禦觸發</div>
                <ul className="list-disc list-inside space-y-0.5 text-emerald-200/90">
                  {defenseActions.map((action, idx) => (
                    <li key={idx}>{action}</li>
                  ))}
                </ul>
              </div>
            )}
            {showHEPanel ? (
              <HEDashboard
                query={heQuery}
                data={heData}
                loading={heLoading}
                onRunSearch={runHESearch}
              />
            ) : (
              <SystemLog
                retrievedDocs={lastResult?.retrieved_docs ?? []}
                filterApplied={lastResult?.filter_applied ?? true}
                userRole={role}
                genModeUsed={lastResult?.gen_mode_used}
                loading={loading}
              />
            )}
          </aside>
        </div>
      </main>

      {/* Footer (secret demo trigger surface) */}
      <footer className="border-t border-gray-800 bg-gray-900/60">
        <div className="mx-auto max-w-[1500px] px-6 py-4 flex flex-col md:flex-row md:items-center md:justify-between gap-2 text-xs text-gray-500">
          <nav className="flex flex-wrap items-center gap-x-4 gap-y-1">
            {FOOTER_LINKS.map((link) => (
              <button
                key={link.key}
                type="button"
                onClick={() => onTriggerAct?.(link.key)}
                className="text-gray-400 hover:text-gray-200 hover:underline underline-offset-4 decoration-gray-500 transition-colors"
              >
                {link.label}
              </button>
            ))}
          </nav>
          <div className="text-gray-600">
            &copy; 2026 NovaTech Corp. All rights reserved.
          </div>
        </div>
      </footer>
    </div>
  );
}
