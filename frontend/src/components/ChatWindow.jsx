/**
 * ChatWindow — controlled chat UI for the RAG demo.
 *
 * The component is purely presentational; the parent (DemoPage) owns the
 * message history and the API call. ChatWindow only:
 *   - Renders the scrollable list of messages via MessageBubble.
 *   - Renders an input bar with Enter-to-send.
 *   - Renders optional suggested-query pills above the input. Clicking a pill
 *     fires `onSend` with the pill text.
 *   - Shows a small loading indicator while `loading` is true.
 *   - Shows a tiny status bar reflecting the current role / filter / mode.
 *
 * Tailwind classes only. No external state, no API calls.
 *
 * @param {object} props
 * @param {'employee'|'manager'|'hr_admin'} props.role
 * @param {boolean} props.useFilter
 * @param {'llm'|'scripted'} props.genMode
 * @param {Array<{role:'user'|'assistant', text:string, piiMatches?:string[]}>} props.messages
 * @param {(queryText: string) => Promise<void>} props.onSend
 * @param {boolean} [props.loading]
 * @param {string[]} [props.suggestedQueries]
 * @param {string} [props.prefillInput] — when this string changes, the input
 *   textarea is reset to its value (used by demo scenarios to "auto-fill" a
 *   query without auto-sending). Presenter clicks the send button manually.
 * @returns {JSX.Element}
 */

import { useEffect, useRef, useState } from 'react';
import MessageBubble from './MessageBubble.jsx';

const ROLE_LABELS = {
  employee: '一般員工',
  manager: '部門主管',
  hr_admin: 'HR 管理員',
};

const GEN_MODE_LABELS = {
  llm: 'LLM',
  scripted: 'Scripted',
};

export default function ChatWindow({
  role,
  useFilter,
  genMode,
  messages = [],
  onSend,
  loading = false,
  suggestedQueries = [],
  prefillInput,
}) {
  const [draft, setDraft] = useState('');
  const listRef = useRef(null);
  const inputRef = useRef(null);

  // Auto-scroll to bottom when new messages arrive or loading toggles.
  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages, loading]);

  // When the parent pushes a new prefill, replace the current draft and focus
  // the input so the presenter sees the "loaded" query and can hit send.
  useEffect(() => {
    if (typeof prefillInput === 'string' && prefillInput.length > 0) {
      setDraft(prefillInput);
      if (inputRef.current) {
        inputRef.current.focus();
        inputRef.current.setSelectionRange(prefillInput.length, prefillInput.length);
      }
    }
  }, [prefillInput]);

  async function dispatch(text) {
    const trimmed = (text ?? '').trim();
    if (!trimmed || loading || typeof onSend !== 'function') return;
    try {
      await onSend(trimmed);
    } catch (_e) {
      // Parent surfaces the error; ChatWindow is presentational only.
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const text = draft;
    setDraft('');
    await dispatch(text);
  }

  function handleKeyDown(e) {
    // Enter to send, Shift+Enter for newline.
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  }

  const roleLabel = ROLE_LABELS[role] ?? role ?? '未指定';
  const filterLabel = useFilter ? '啟用' : '停用';
  const genModeLabel = GEN_MODE_LABELS[genMode] ?? genMode ?? '—';
  const isEmpty = messages.length === 0;

  return (
    <div className="flex flex-col h-full w-full bg-gray-900/40 border border-gray-700/40 rounded-lg overflow-hidden">
      {/* Message list */}
      <div
        ref={listRef}
        className="flex-1 overflow-y-auto px-4 py-3 space-y-1"
      >
        {isEmpty && !loading && (
          <div className="h-full flex items-center justify-center text-gray-400 text-sm italic">
            請選擇一個建議查詢，或自行輸入問題
          </div>
        )}

        {messages.map((m, idx) => (
          <MessageBubble
            key={idx}
            role={m.role}
            text={m.text}
            piiMatches={m.piiMatches}
            doc={m.doc}
          />
        ))}

        {loading && (
          <div className="w-full flex justify-start mb-3">
            <div className="px-4 py-2 rounded-2xl border bg-gray-700/80 text-gray-300 border-gray-500/40 text-sm flex items-center gap-2">
              <span
                className="inline-block h-3 w-3 border-2 border-gray-300 border-t-transparent rounded-full animate-spin"
                aria-label="loading"
              />
              <span>思考中...</span>
            </div>
          </div>
        )}
      </div>

      {/* Suggested queries */}
      {suggestedQueries && suggestedQueries.length > 0 && (
        <div className="px-4 py-2 border-t border-gray-700/40 flex flex-wrap gap-2">
          {suggestedQueries.map((q, idx) => (
            <button
              key={idx}
              type="button"
              disabled={loading}
              onClick={() => dispatch(q)}
              className="text-xs px-3 py-1 rounded-full border border-blue-500/40 bg-blue-500/10 text-blue-200 hover:bg-blue-500/20 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              title={q}
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {/* Status bar */}
      <div className="px-4 py-1.5 border-t border-gray-700/40 bg-gray-800/40 text-[11px] text-gray-400 font-mono flex items-center gap-3">
        <span>目前身份: <span className="text-gray-200">{roleLabel}</span></span>
        <span className="text-gray-600">|</span>
        <span>存取控制: <span className={useFilter ? 'text-green-300' : 'text-red-300'}>{filterLabel}</span></span>
        <span className="text-gray-600">|</span>
        <span>模式: <span className="text-gray-200">{genModeLabel}</span></span>
      </div>

      {/* Input bar */}
      <form
        onSubmit={handleSubmit}
        className="px-3 py-3 border-t border-gray-700/40 bg-gray-900/60 flex items-end gap-2"
      >
        <textarea
          ref={inputRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          placeholder="輸入問題，按 Enter 送出（Shift+Enter 換行）"
          disabled={loading}
          className="flex-1 resize-none px-3 py-2 rounded-md bg-gray-800/80 border border-gray-600/50 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-blue-400/60 focus:ring-1 focus:ring-blue-400/40 disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={loading || draft.trim().length === 0}
          className="px-4 py-2 rounded-md bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium disabled:bg-gray-700 disabled:text-gray-400 disabled:cursor-not-allowed transition-colors"
        >
          送出
        </button>
      </form>
    </div>
  );
}
