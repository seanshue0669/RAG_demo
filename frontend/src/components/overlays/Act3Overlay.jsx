/**
 * Act3Overlay — secret modal triggered by the footer "資訊安全政策" link.
 *
 * Demonstrates Act 3 (Prompt Injection): a legitimately classified L1 public
 * policy document carries an embedded injection payload that hijacks the LLM
 * even though the access-control filter is operating correctly. The overlay
 * fires a single POST to /api/demo/act3 on open, surfaces the retrieved doc
 * set, expands the poisoned document inline, and uses a regex to visually
 * isolate the injection payload inside that doc.
 *
 * Behaviour summary:
 *   - Props: { open: boolean, onClose: () => void }.
 *   - On open: dispatches one axios POST to /api/demo/act3, shows a
 *     prominent loading state (the backend call can take 10s+).
 *   - Closes via the [X] button, clicking the backdrop, or pressing ESC.
 *   - Non-poisoned docs render collapsed (title + first 80 chars).
 *   - The poisoned doc (doc_type === 'poisoned_policy') renders fully
 *     expanded with the injection segment highlighted in red.
 *   - framer-motion fades in/out, max width is 5xl, dark glass styling.
 *
 * Injection-highlight regex strategy (first match wins, falls back to the
 * whole text if nothing matches):
 *   1. /【系統內部備註】[\s\S]*?(?=如有相關問題)/  — preferred terminator-aware
 *   2. /【系統內部備註】[\s\S]+/                    — open-ended marker fallback
 *   3. SYSTEM_NOTE / INTERNAL / Ignore previous / 請忽略 / [INTERNAL] heuristics
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { AnimatePresence, motion } from 'framer-motion';
import { API_BASE_URL } from '../../config.js';

const LEVEL_BADGE_STYLES = {
  1: 'bg-green-500/20 text-green-300 border-green-500/40',
  2: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40',
  3: 'bg-red-500/20 text-red-300 border-red-500/40',
};

const DOC_TYPE_LABELS = {
  employee_record: '員工個資',
  performance_review: '績效評核',
  policy_document: '政策文件',
  poisoned_policy: '⚠️ 偵測到可疑文件',
};

/**
 * Locate the injection payload inside a poisoned document body.
 *
 * @param {string} text - Raw document text from the backend.
 * @returns {{ before: string, payload: string, after: string }}
 *   Three-way split such that `before + payload + after === text`. When no
 *   pattern matches, `payload` is the entire text and the other two strings
 *   are empty so the caller still has something to highlight.
 */
function splitInjection(text) {
  if (!text) return { before: '', payload: '', after: '' };

  // Patterns tried in order — first one with a match wins.
  const patterns = [
    /【系統內部備註】[\s\S]*?(?=如有相關問題)/,
    /【系統內部備註】[\s\S]+/,
    /(?:SYSTEM\s*(?:NOTE|OVERRIDE)|\[INTERNAL\][:：]?|<!--[\s\S]*?-->|Ignore\s+previous\s+instructions|請忽略(?:前述|先前)?指示)[\s\S]+?(?=\n\n|$)/i,
  ];

  for (const re of patterns) {
    const match = text.match(re);
    if (match && typeof match.index === 'number') {
      const start = match.index;
      const end = start + match[0].length;
      return {
        before: text.slice(0, start),
        payload: text.slice(start, end),
        after: text.slice(end),
      };
    }
  }

  // No marker found — still highlight the whole text so the audience sees
  // *something* tagged as the payload.
  return { before: '', payload: text, after: '' };
}

/**
 * Render a card for a non-poisoned retrieved document (collapsed preview).
 *
 * @param {{ doc: { doc_id: string, text: string, security_level: number,
 *                  similarity: number, doc_type?: string } }} props
 * @returns {JSX.Element}
 */
function CleanDocCard({ doc }) {
  const text = doc.text ?? '';
  const excerpt = text.length > 80 ? `${text.slice(0, 80)}…` : text;
  const levelStyle =
    LEVEL_BADGE_STYLES[doc.security_level] ||
    'bg-gray-500/20 text-gray-300 border-gray-500/40';
  const typeLabel = DOC_TYPE_LABELS[doc.doc_type] || doc.doc_type || '政策文件';
  const sim = Number.isFinite(doc.similarity)
    ? doc.similarity.toFixed(2)
    : '—';

  return (
    <div className="p-3 rounded-md border border-gray-700/50 bg-gray-900/40">
      <div className="flex items-center gap-2 mb-1">
        <span
          className={`px-1.5 py-0.5 rounded border text-[10px] font-mono ${levelStyle}`}
        >
          L{doc.security_level}
        </span>
        <span
          className="font-mono text-sm text-gray-100 truncate"
          title={doc.doc_id}
        >
          {doc.doc_id}
        </span>
        <span className="text-xs text-gray-400">{typeLabel}</span>
        <span className="ml-auto text-[11px] font-mono text-gray-400">
          sim={sim}
        </span>
      </div>
      <p className="text-xs text-gray-300 leading-relaxed whitespace-pre-wrap break-words">
        {excerpt}
      </p>
    </div>
  );
}

/**
 * Render the poisoned document card with the injection payload visually
 * isolated in a red-tinted block plus a floating warning label.
 *
 * @param {{ doc: { doc_id: string, text: string, security_level: number,
 *                  similarity: number, doc_type?: string } }} props
 * @returns {JSX.Element}
 */
function PoisonedDocCard({ doc }) {
  const text = doc.text ?? '';
  const { before, payload, after } = useMemo(
    () => splitInjection(text),
    [text],
  );
  const sim = Number.isFinite(doc.similarity)
    ? doc.similarity.toFixed(2)
    : '—';

  return (
    <div className="p-3 rounded-md border border-red-500/70 ring-1 ring-red-500/40 bg-red-950/30">
      <div className="flex items-center gap-2 mb-2">
        <span className="px-1.5 py-0.5 rounded border text-[10px] font-mono bg-green-500/20 text-green-300 border-green-500/40">
          L{doc.security_level}
        </span>
        <span
          className="font-mono text-sm text-gray-100 truncate"
          title={doc.doc_id}
        >
          {doc.doc_id}
        </span>
        <span className="text-xs text-red-300 font-semibold">
          ⚠️ 偵測到可疑文件
        </span>
        <span className="ml-auto text-[11px] font-mono text-gray-400">
          sim={sim}
        </span>
      </div>

      <div className="text-[11px] uppercase tracking-wider text-gray-500 mb-1">
        完整內容
      </div>

      <div className="text-xs text-gray-200 leading-relaxed whitespace-pre-wrap break-words space-y-2">
        {before && <div>{before}</div>}

        <div className="relative">
          <span className="absolute -top-2 left-3 px-1.5 py-0.5 rounded border text-[10px] font-mono bg-red-600/80 text-white border-red-400 shadow">
            ⚠️ Prompt Injection Payload
          </span>
          <div className="mt-2 pl-3 pr-2 py-2 bg-red-900/40 border-l-4 border-red-500 rounded-r-md text-red-100">
            {payload}
          </div>
        </div>

        {after && <div>{after}</div>}
      </div>
    </div>
  );
}

/**
 * Loading splash used while the /api/demo/act3 call is in flight.
 * The backend can take 10s+ on the first hit because of LLM warm-up, so
 * the splash explicitly explains this rather than showing a generic spinner.
 *
 * @returns {JSX.Element}
 */
function LoadingPanel() {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="w-12 h-12 border-4 border-red-500/40 border-t-red-400 rounded-full animate-spin mb-5" />
      <div className="text-sm text-gray-200 font-semibold mb-1">
        正在執行 Prompt Injection 攻擊展示…
      </div>
      <div className="text-xs text-gray-400 max-w-md leading-relaxed">
        後端會檢索文件、組合 prompt、並呼叫 LLM 生成回答，整個流程通常需要
        10 秒以上，請稍候。
      </div>
    </div>
  );
}

/**
 * Act3Overlay — secret modal that demonstrates a successful prompt-injection
 * attack via a poisoned L1 policy document.
 *
 * @param {object} props
 * @param {boolean} props.open - Whether the overlay is currently visible.
 * @param {() => void} props.onClose - Close handler (X, backdrop, ESC).
 * @returns {JSX.Element|null}
 */
export default function Act3Overlay({ open, onClose }) {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  // ESC closes.
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') onClose?.();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  // Fetch act3 demo response on open. Reset state on close so a re-open
  // re-runs the call (useful for re-demoing during a presentation).
  useEffect(() => {
    if (!open) {
      setData(null);
      setError(null);
      setLoading(false);
      return undefined;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);
    setData(null);

    axios
      .post(`${API_BASE_URL}/api/demo/act3`)
      .then((resp) => {
        if (cancelled) return;
        setData(resp.data);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(
          err?.response?.data?.detail ||
            err?.message ||
            '無法載入示範資料，請稍後再試。',
        );
      })
      .finally(() => {
        if (cancelled) return;
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [open]);

  const handleBackdropClick = useCallback(
    (e) => {
      if (e.target === e.currentTarget) onClose?.();
    },
    [onClose],
  );

  // Pull the shape we actually need out of DemoResponse.
  const result = data?.result ?? null;
  const retrievedDocs = Array.isArray(result?.retrieved_docs)
    ? result.retrieved_docs
    : [];
  const poisonedDocs = retrievedDocs.filter(
    (d) => d?.doc_type === 'poisoned_policy',
  );
  const cleanDocs = retrievedDocs.filter(
    (d) => d?.doc_type !== 'poisoned_policy',
  );
  const answer = result?.answer ?? '';
  const query = data?.query ?? '公司福利政策有哪些？';
  const userRole = data?.user_role ?? 'employee';
  const filterApplied = result?.filter_applied ?? true;
  const attackTriggered = poisonedDocs.length > 0;

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          key="act3-backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          onMouseDown={handleBackdropClick}
          className="fixed inset-0 z-50 flex items-start justify-center bg-black/70 backdrop-blur-sm overflow-y-auto py-10 px-4"
        >
          <motion.div
            key="act3-panel"
            initial={{ opacity: 0, y: 16, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.98 }}
            transition={{ duration: 0.22 }}
            className="w-full max-w-5xl bg-gray-950/95 border border-gray-700/60 rounded-xl shadow-2xl overflow-hidden"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-3 border-b border-gray-700/60 bg-gray-900/60">
              <h2 className="text-base font-semibold text-gray-100 tracking-wide">
                資訊安全政策
              </h2>
              <button
                type="button"
                onClick={onClose}
                aria-label="關閉"
                className="w-8 h-8 flex items-center justify-center rounded-md text-gray-300 hover:text-white hover:bg-gray-700/60 transition"
              >
                ✕
              </button>
            </div>

            {/* Intro */}
            <div className="px-5 py-4 border-b border-gray-700/40 bg-gray-900/30">
              <div className="text-sm font-semibold text-red-300 mb-1">
                Prompt Injection 攻擊展示
              </div>
              <div className="text-xs text-gray-400 leading-relaxed">
                一份「合法」的 Level 1 公開政策文件，內嵌惡意指令。
                即使存取控制完全運作，這份 L1 文件仍會被一般員工檢索到，
                並把注入內容帶入 LLM 上下文。
              </div>
            </div>

            {/* Query meta */}
            <div className="px-5 py-3 border-b border-gray-700/40 bg-gray-900/30 text-xs text-gray-300 space-y-1">
              <div>
                <span className="text-gray-500">查詢：</span>
                <span className="text-gray-100">「{query}」</span>
              </div>
              <div>
                <span className="text-gray-500">身份：</span>
                <span className="text-gray-100">
                  {userRole === 'employee'
                    ? '一般員工'
                    : userRole === 'manager'
                      ? '主管'
                      : userRole === 'hr_admin'
                        ? '人資管理員'
                        : userRole}
                </span>
                <span className="text-gray-500 ml-2">
                  (Level 1，存取控制{filterApplied ? '已啟用' : '已停用'})
                </span>
              </div>
            </div>

            {/* Body */}
            <div className="px-5 py-4 space-y-5 max-h-[70vh] overflow-y-auto">
              {loading && <LoadingPanel />}

              {!loading && error && (
                <div className="p-4 rounded-md border border-red-500/60 bg-red-900/30 text-sm text-red-200">
                  載入失敗：{error}
                </div>
              )}

              {!loading && !error && data && (
                <>
                  {/* Retrieved docs */}
                  <section>
                    <div className="text-xs uppercase tracking-wider text-gray-500 mb-2">
                      檢索到的文件
                    </div>
                    <div className="space-y-2">
                      {cleanDocs.map((doc) => (
                        <CleanDocCard
                          key={doc.doc_id ?? Math.random()}
                          doc={doc}
                        />
                      ))}
                      {poisonedDocs.map((doc) => (
                        <PoisonedDocCard
                          key={doc.doc_id ?? Math.random()}
                          doc={doc}
                        />
                      ))}
                      {retrievedDocs.length === 0 && (
                        <div className="text-xs text-gray-500 italic">
                          本次未檢索到任何文件。
                        </div>
                      )}
                    </div>
                  </section>

                  {/* LLM answer */}
                  <section>
                    <div className="text-xs uppercase tracking-wider text-gray-500 mb-2">
                      AI 回答
                    </div>
                    <div className="p-3 rounded-md border border-gray-700/50 bg-gray-900/40 text-sm text-gray-200 leading-relaxed whitespace-pre-wrap break-words">
                      {answer || '（LLM 沒有回傳內容）'}
                    </div>
                  </section>

                  {/* Outcome banner */}
                  <section
                    className={`p-4 rounded-md border ${
                      attackTriggered
                        ? 'border-red-500/70 bg-red-950/40'
                        : 'border-yellow-500/60 bg-yellow-900/20'
                    }`}
                  >
                    <div
                      className={`text-sm font-semibold mb-1 ${
                        attackTriggered ? 'text-red-300' : 'text-yellow-200'
                      }`}
                    >
                      {attackTriggered
                        ? '⚠️ 攻擊成功偵測'
                        : '本次未命中 poisoned_policy 文件'}
                    </div>
                    <div className="text-xs text-gray-300 leading-relaxed">
                      {attackTriggered
                        ? '檢索結果中含有 doc_type=poisoned_policy 的文件，Prompt Injection 已注入 AI 的上下文中。即使存取控制正確運作，惡意內容仍然透過合法的公開（L1）文件流入 LLM，導致回答被誘導洩漏額外資訊。'
                        : '本次檢索沒有命中任何 poisoned_policy 文件，Prompt Injection 路徑未被觸發。可重新開啟此面板再試一次。'}
                    </div>
                    {data?.narration && (
                      <div className="mt-2 text-[11px] text-gray-400 italic">
                        旁白：{data.narration}
                      </div>
                    )}
                  </section>
                </>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
