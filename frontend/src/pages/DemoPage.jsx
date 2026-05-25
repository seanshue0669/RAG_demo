/**
 * DemoPage — top-level integration page for the Cloud RAG Security demo.
 *
 * Layout (per cloud-rag-demo-spec.md §五):
 *
 *   ┌────────────────────────────────────────────────────────┐
 *   │ [ActNavigation]  第一幕 | 第二幕 | 第三幕 | 第四幕      │
 *   │ [Quick actions: 執行預設攻擊／防禦腳本]                 │
 *   ├──────────────────────────┬─────────────────────────────┤
 *   │ [ChatWindow]             │ [SystemLog] (Act 1–3)        │
 *   │                          │ [HEDashboard] (Act 4)        │
 *   ├──────────────────────────┴─────────────────────────────┤
 *   │ [UserRoleSwitcher]                                      │
 *   ├────────────────────────────────────────────────────────┤
 *   │ [SecuritySpectrum] (Act 4 only)                         │
 *   └────────────────────────────────────────────────────────┘
 *
 * Responsibilities:
 *   - Owns local state for the current act, role, useFilter toggle, message
 *     history, retrieved docs, filter state, gen-mode used, narration, HE
 *     payload, and a "poisoned" banner flag.
 *   - Wires the existing useQuery / useDemo hooks plus an inline useHESearch
 *     helper (W1-F didn't ship a dedicated hook for /api/he/search).
 *   - Switching acts resets the chat and applies the act-specific preset
 *     (role, filter default, suggested queries).
 *   - Quick-action buttons trigger POST /api/demo/{act} and replay the
 *     response into the chat/log so the audience sees a fully populated
 *     scene without typing.
 *   - Act 2 exposes a visible "啟用存取控制" toggle that replays the last
 *     query whenever flipped so the contrast is immediate.
 *   - Act 3 surfaces a "⚠️ Prompt Injection 攻擊被觸發！" banner whenever
 *     the latest retrieval includes a poisoned_policy document.
 *   - Act 4 swaps SystemLog for HEDashboard and exposes SecuritySpectrum.
 *
 * @returns {JSX.Element}
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import ActNavigation from '../components/ActNavigation.jsx';
import ChatWindow from '../components/ChatWindow.jsx';
import SystemLog from '../components/SystemLog.jsx';
import HEDashboard from '../components/HEDashboard.jsx';
import UserRoleSwitcher from '../components/UserRoleSwitcher.jsx';
import SecuritySpectrum from '../components/SecuritySpectrum.jsx';
import { useQuery } from '../hooks/useQuery.js';
import { useDemo } from '../hooks/useDemo.js';
import { API_BASE_URL } from '../config.js';

/**
 * Per-act presets. `useFilter` is the default; Act 2 lets the user toggle it.
 * @type {Record<string, {role:'employee'|'manager'|'hr_admin',
 *                       useFilter:boolean,
 *                       suggestedQueries:string[],
 *                       subtitle:string}>}
 */
const ACT_PRESETS = {
  act1: {
    role: 'employee',
    useFilter: true,
    suggestedQueries: ['公司請假規定', '加班費怎麼算', '健保補助'],
    subtitle: '第一幕：基本 RAG 流程 — 觀察一個合規查詢的全貌。',
  },
  act2: {
    role: 'employee',
    useFilter: true,
    suggestedQueries: [
      '張小明的薪資',
      '工程部的績效評核',
      'HR 部門員工聯絡方式',
    ],
    subtitle:
      '第二幕：檢索層權限漏洞 — 透過上方 toggle 切換存取控制，比對檢索結果。',
  },
  act3: {
    role: 'employee',
    useFilter: true,
    suggestedQueries: ['公司福利政策有哪些？', '年終獎金規定'],
    subtitle: '第三幕：生成層 Prompt Injection — 注意檢索結果中的可疑文件。',
  },
  act4: {
    role: 'employee',
    useFilter: true,
    suggestedQueries: ['薪資查詢', '請假規定', '林志明的個資'],
    subtitle: '第四幕：儲存層同態加密 — 密文檢索全程不解密。',
  },
};

const QUICK_ACTIONS = {
  act1: [{ key: 'act1', label: '執行 Act 1 預設' }],
  act2: [{ key: 'act2', label: '執行 Act 2 攻擊／防禦對照' }],
  act3: [{ key: 'act3', label: '執行 Act 3 Prompt Injection' }],
  act4: [{ key: 'act4', label: '執行 Act 4 加密搜尋' }],
};

/**
 * Inline replacement for the missing useHESearch hook. Wraps
 * POST /api/he/search with the same loading / error / data tuple as the
 * sibling hooks in /hooks/.
 *
 * @returns {{
 *   runSearch: (query: string, top_k?: number) => Promise<object>,
 *   loading: boolean,
 *   error: string | null,
 *   data: object | null,
 *   reset: () => void,
 * }}
 */
function useHESearch() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);

  const runSearch = useCallback(async (query, top_k = 5) => {
    setLoading(true);
    setError(null);
    try {
      const { data: resp } = await axios.post(
        `${API_BASE_URL}/api/he/search`,
        { query, top_k },
      );
      setData(resp);
      return resp;
    } catch (e) {
      const msg = e.response?.data?.detail || e.message || 'Unknown error';
      setError(msg);
      throw e;
    } finally {
      setLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setData(null);
    setError(null);
  }, []);

  return { runSearch, loading, error, data, reset };
}

export default function DemoPage() {
  // ---------- Page-level state ----------
  const [act, setAct] = useState('act1');
  const [role, setRole] = useState(ACT_PRESETS.act1.role);
  const [useFilter, setUseFilter] = useState(ACT_PRESETS.act1.useFilter);
  const [messages, setMessages] = useState([]);
  const [retrievedDocs, setRetrievedDocs] = useState([]);
  const [filterApplied, setFilterApplied] = useState(true);
  const [genModeUsed, setGenModeUsed] = useState('llm');
  const [narration, setNarration] = useState('');
  const [poisonedBanner, setPoisonedBanner] = useState(false);

  // Remember the last typed query so the Act 2 toggle can replay it.
  const lastQueryRef = useRef('');

  // ---------- Hooks for API calls ----------
  const { sendQuery, loading: queryLoading, error: queryError } = useQuery();
  const { runDemo, loading: demoLoading, error: demoError } = useDemo();
  const {
    runSearch: runHESearch,
    loading: heLoading,
    error: heError,
    data: heData,
    reset: resetHE,
  } = useHESearch();

  const preset = ACT_PRESETS[act];
  const quickActions = QUICK_ACTIONS[act] ?? [];
  const error = queryError || demoError || heError;
  const busy = queryLoading || demoLoading || heLoading;

  // ---------- Helpers ----------

  /**
   * Apply the API query response into the page state (messages, sidebar).
   * @param {object} resp - QueryResponse-shaped payload.
   * @param {string} userQuery - The query string the user/demo issued.
   */
  const applyQueryResponse = useCallback((resp, userQuery) => {
    if (!resp) return;
    const docs = Array.isArray(resp.retrieved_docs) ? resp.retrieved_docs : [];
    setMessages((prev) => [
      ...prev,
      { role: 'user', text: userQuery },
      { role: 'assistant', text: resp.answer ?? '(無回應)', piiMatches: [] },
    ]);
    setRetrievedDocs(docs);
    setFilterApplied(Boolean(resp.filter_applied));
    if (resp.gen_mode_used) setGenModeUsed(resp.gen_mode_used);
    setPoisonedBanner(docs.some((d) => d?.doc_type === 'poisoned_policy'));
  }, []);

  /**
   * Send a user query through /api/query and surface the result in the UI.
   * @param {string} text - User input.
   * @param {object} [overrides] - Optional overrides (role, useFilter).
   */
  const dispatchQuery = useCallback(
    async (text, overrides = {}) => {
      const trimmed = (text ?? '').trim();
      if (!trimmed) return;
      lastQueryRef.current = trimmed;
      const effectiveRole = overrides.role ?? role;
      const effectiveFilter =
        overrides.useFilter !== undefined ? overrides.useFilter : useFilter;
      try {
        const resp = await sendQuery({
          query: trimmed,
          user_role: effectiveRole,
          use_filter: effectiveFilter,
          gen_mode: 'llm',
          top_k: 5,
        });
        applyQueryResponse(resp, trimmed);
      } catch (_e) {
        // Surfaced via `error` from the hook; no further action needed.
      }
    },
    [applyQueryResponse, role, sendQuery, useFilter],
  );

  /**
   * Reset chat state when changing acts or applying presets.
   */
  const resetChatState = useCallback(() => {
    setMessages([]);
    setRetrievedDocs([]);
    setPoisonedBanner(false);
    setNarration('');
    lastQueryRef.current = '';
  }, []);

  // ---------- Act switching ----------
  useEffect(() => {
    const next = ACT_PRESETS[act];
    if (!next) return;
    setRole(next.role);
    setUseFilter(next.useFilter);
    resetChatState();
    if (act === 'act4') {
      // HE dashboard owns its own input + state; just clear previous data.
      resetHE();
    }
    // We intentionally only react to `act` changes here.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [act]);

  // ---------- Act 2 toggle behaviour ----------
  /**
   * Flip the Act 2 access-control toggle. If we already have a query in
   * memory, replay it immediately so the audience sees the contrast.
   * @param {boolean} nextValue
   */
  const handleAct2ToggleChange = useCallback(
    (nextValue) => {
      setUseFilter(nextValue);
      const last = lastQueryRef.current;
      if (last) {
        // Fire-and-forget replay with the new filter setting.
        void dispatchQuery(last, { useFilter: nextValue });
      }
    },
    [dispatchQuery],
  );

  // ---------- Quick action handler ----------
  /**
   * Trigger one of the act-specific demo scripts on the backend.
   * @param {'act1'|'act2'|'act3'|'act4'} actKey
   */
  const handleQuickAction = useCallback(
    async (actKey) => {
      try {
        const data = await runDemo(actKey);
        if (!data) return;
        setNarration(data.narration ?? '');
        // For Acts 1–3 the `result` field is a QueryResponse. For Act 4
        // it may be an HESearchResponse / Act4 attack payload; in that
        // case we route into the HE dashboard if the shape matches.
        const result = data.result || {};
        if (result && Array.isArray(result.retrieved_docs)) {
          applyQueryResponse(result, data.query || '(預設查詢)');
        } else if (result && result.timing && Array.isArray(result.results)) {
          // HE-shaped result — let HEDashboard render directly.
          // Best-effort: stash into hook state via a manual call.
          // useHESearch doesn't expose a setter, so simply re-run the
          // search using the demo query to keep timing consistent.
          if (data.query) {
            void runHESearch(data.query);
          }
        }
      } catch (_e) {
        // Surfaced via demoError.
      }
    },
    [applyQueryResponse, runDemo, runHESearch],
  );

  // ---------- Derived data ----------
  const subtitle = useMemo(() => preset?.subtitle ?? '', [preset]);

  // ---------- Render ----------
  return (
    <div className="flex flex-col h-full w-full text-gray-100">
      {/* Top: ActNavigation + quick actions */}
      <div className="border-b border-gray-700/60 bg-gray-900/60">
        <ActNavigation act={act} onChange={setAct} subtitle={subtitle} />

        <div className="px-4 py-2 flex flex-wrap items-center gap-2 bg-gray-900/30">
          {quickActions.map((qa) => (
            <button
              key={qa.key}
              type="button"
              onClick={() => handleQuickAction(qa.key)}
              disabled={busy}
              className="px-3 py-1.5 text-xs rounded-md border border-blue-500/40 bg-blue-500/10 text-blue-200 hover:bg-blue-500/20 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {qa.label}
            </button>
          ))}

          {act === 'act2' && (
            <label className="ml-auto inline-flex items-center gap-2 text-xs text-gray-300 select-none">
              <span className="text-gray-400">啟用存取控制</span>
              <button
                type="button"
                role="switch"
                aria-checked={useFilter}
                onClick={() => handleAct2ToggleChange(!useFilter)}
                disabled={busy}
                className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors duration-150 ${
                  useFilter ? 'bg-green-500/70' : 'bg-red-500/70'
                } disabled:opacity-50`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform duration-150 ${
                    useFilter ? 'translate-x-4' : 'translate-x-1'
                  }`}
                />
              </button>
              <span
                className={`font-mono ${
                  useFilter ? 'text-green-300' : 'text-red-300'
                }`}
              >
                {useFilter ? 'ON' : 'OFF'}
              </span>
            </label>
          )}
        </div>

        {/* Error / narration banners */}
        {error && (
          <div className="px-4 py-1.5 text-xs text-red-300 bg-red-500/10 border-t border-red-500/30">
            錯誤: {error}
          </div>
        )}
        {act === 'act3' && poisonedBanner && (
          <div className="px-4 py-1.5 text-xs font-semibold text-red-200 bg-red-500/20 border-t border-red-500/40">
            ⚠️ Prompt Injection 攻擊被觸發！檢索結果中含有 poisoned_policy 文件。
          </div>
        )}
        {narration && (
          <div className="px-4 py-1.5 text-xs text-blue-200 bg-blue-500/10 border-t border-blue-500/30 italic">
            {narration}
          </div>
        )}
      </div>

      {/* Middle: ChatWindow + SystemLog/HEDashboard */}
      <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-2 gap-3 p-3">
        <div className="min-h-[420px] lg:min-h-0">
          <ChatWindow
            role={role}
            useFilter={useFilter}
            genMode="llm"
            messages={messages}
            onSend={(text) => dispatchQuery(text)}
            loading={queryLoading || demoLoading}
            suggestedQueries={preset?.suggestedQueries ?? []}
          />
        </div>

        <div className="min-h-[420px] lg:min-h-0">
          {act === 'act4' ? (
            <HEDashboard
              query={lastQueryRef.current}
              data={heData}
              loading={heLoading}
              onRunSearch={(text) => {
                lastQueryRef.current = text;
                void runHESearch(text);
              }}
            />
          ) : (
            <SystemLog
              retrievedDocs={retrievedDocs}
              filterApplied={filterApplied}
              userRole={role}
              genModeUsed={genModeUsed}
              loading={queryLoading || demoLoading}
            />
          )}
        </div>
      </div>

      {/* Bottom: role switcher */}
      <div className="border-t border-gray-700/60 bg-gray-900/60 px-4 py-3 flex items-center justify-between gap-4 flex-wrap">
        <UserRoleSwitcher role={role} onChange={setRole} />
        <span className="text-[11px] text-gray-500">
          切換角色不會自動重發查詢；請使用上方建議查詢或重新輸入問題。
        </span>
      </div>

      {/* Act 4: security spectrum below the main panel */}
      {act === 'act4' && (
        <div className="px-3 pb-4">
          <SecuritySpectrum />
        </div>
      )}
    </div>
  );
}
