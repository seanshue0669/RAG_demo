/**
 * Act2Overlay — hidden "公司治理" overlay that visualises the Act 2
 * "retrieval bypass" scenario as a side-by-side comparison.
 *
 * When the overlay opens, two demo endpoints are fired in parallel:
 *   - POST /api/demo/act2_no_filter   (attack: filter OFF)
 *   - POST /api/demo/act2_with_filter (defense: filter ON)
 *
 * The component renders an attacker column (left) and a defender column
 * (right) showing, for the same query and same employee role, which
 * documents were retrieved and what the LLM answered. Any L3 document
 * surfaced on the attacker side is highlighted with a red ring and a
 * "PII" badge to make the leak unmistakable.
 *
 * Backend response shape (per column):
 *   DemoResponse {
 *     act, query, user_role,
 *     result: QueryResponse {
 *       answer, retrieved_docs[], filter_applied, user_role, gen_mode_used
 *     },
 *     narration
 *   }
 *
 * @param {object} props
 * @param {boolean} props.open
 * @param {() => void} props.onClose
 * @returns {JSX.Element|null}
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import axios from 'axios';
import { API_BASE_URL } from '../../config.js';

const LEVEL_BADGE_STYLES = {
  1: 'bg-green-500/20 text-green-300 border-green-500/40',
  2: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40',
  3: 'bg-red-500/20 text-red-300 border-red-500/40',
};

const ROLE_LABELS = {
  employee: '一般員工',
  manager: '主管',
  hr_admin: 'HR 管理員',
};

/**
 * Render a single retrieved-document card inside one of the two columns.
 *
 * @param {object} props
 * @param {{doc_id:string, text:string, security_level:number,
 *          similarity:number, doc_type?:string, department?:string}} props.doc
 * @param {boolean} props.highlightLeak - When true and the document is
 *     L2/L3, render a red ring + "PII" badge to flag the leak.
 * @returns {JSX.Element}
 */
function DocCard({ doc, highlightLeak }) {
  const level = doc.security_level;
  const isLeak = highlightLeak && level >= 2;
  const isPII = highlightLeak && level >= 3;
  const levelStyle =
    LEVEL_BADGE_STYLES[level] ||
    'bg-gray-500/20 text-gray-300 border-gray-500/40';

  const text = doc.text ?? '';
  const excerpt = text.length > 120 ? `${text.slice(0, 120)}...` : text;

  const borderTone = isPII
    ? 'border-red-500/70 ring-1 ring-red-500/50'
    : isLeak
      ? 'border-yellow-500/50'
      : 'border-gray-700/50';

  return (
    <div className={`p-2.5 rounded-md border bg-gray-900/40 ${borderTone}`}>
      <div className="flex items-center gap-2 mb-1">
        <span
          className="font-mono text-xs text-gray-100 truncate"
          title={doc.doc_id}
        >
          {doc.doc_id}
        </span>
        <span
          className={`px-1.5 py-0.5 rounded border text-[10px] font-mono ${levelStyle}`}
          title={`Security level L${level}`}
        >
          L{level}
        </span>
        {isPII && (
          <span className="px-1.5 py-0.5 rounded border text-[10px] font-mono bg-red-500/25 text-red-200 border-red-500/60">
            ⚠ PII
          </span>
        )}
        <span className="ml-auto text-[11px] font-mono text-gray-400">
          {Number.isFinite(doc.similarity)
            ? `${(doc.similarity * 100).toFixed(1)}%`
            : '—'}
        </span>
      </div>
      {doc.department && (
        <div className="text-[11px] text-gray-400 mb-1">
          {doc.department}
        </div>
      )}
      <div className="text-xs text-gray-300 leading-relaxed whitespace-pre-wrap break-words">
        {excerpt}
      </div>
    </div>
  );
}

/**
 * Render a single comparison column (attacker or defender).
 *
 * @param {object} props
 * @param {'attack'|'defense'} props.variant
 * @param {string} props.title
 * @param {string} props.subtitle
 * @param {{retrieved_docs:Array, answer:string, filter_applied:boolean}|null} props.payload
 * @returns {JSX.Element}
 */
function ComparisonColumn({ variant, title, subtitle, payload }) {
  const isAttack = variant === 'attack';
  const headerCls = isAttack
    ? 'border-red-500/50 bg-red-500/10 text-red-200'
    : 'border-green-500/50 bg-green-500/10 text-green-200';
  const docs = payload?.retrieved_docs ?? [];
  const answer = payload?.answer ?? '(無回應)';
  const leakCount = isAttack
    ? docs.filter((d) => (d?.security_level ?? 0) >= 2).length
    : 0;

  return (
    <div className="flex flex-col min-h-0 rounded-lg border border-gray-700/40 bg-gray-900/30 overflow-hidden">
      <div className={`px-4 py-2.5 border-b ${headerCls}`}>
        <div className="text-sm font-semibold tracking-wide">{title}</div>
        <div className="text-[11px] opacity-80 mt-0.5">{subtitle}</div>
      </div>

      <div className="px-4 py-3 space-y-3 overflow-y-auto">
        <section>
          <div className="text-xs uppercase tracking-wider text-gray-500 mb-1.5 flex items-center justify-between">
            <span>檢索到的文件</span>
            <span className="text-[11px] normal-case font-mono text-gray-500">
              {docs.length} 筆
              {isAttack && leakCount > 0 && (
                <span className="ml-2 text-red-300">
                  · {leakCount} 筆越權
                </span>
              )}
            </span>
          </div>
          {docs.length === 0 ? (
            <div className="text-xs text-gray-500 italic px-1 py-2">
              尚無檢索結果
            </div>
          ) : (
            <div className="space-y-2">
              {docs.map((doc, idx) => (
                <DocCard
                  key={`${doc.doc_id}-${idx}`}
                  doc={doc}
                  highlightLeak={isAttack}
                />
              ))}
            </div>
          )}
        </section>

        <section>
          <div className="text-xs uppercase tracking-wider text-gray-500 mb-1.5">
            AI 回答
          </div>
          <div
            className={`text-sm leading-relaxed whitespace-pre-wrap break-words p-3 rounded-md border ${
              isAttack
                ? 'border-red-500/40 bg-red-500/5 text-red-100'
                : 'border-green-500/40 bg-green-500/5 text-green-100'
            }`}
          >
            {answer}
          </div>
        </section>
      </div>
    </div>
  );
}

export default function Act2Overlay({ open, onClose }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const [noFilterResp, setNoFilterResp] = useState(null);
  const [withFilterResp, setWithFilterResp] = useState(null);

  const requestIdRef = useRef(0);

  // Stable close handler (also wired to backdrop / ESC).
  const handleClose = useCallback(() => {
    if (typeof onClose === 'function') onClose();
  }, [onClose]);

  // Fire both demo endpoints in parallel whenever the overlay opens.
  useEffect(() => {
    if (!open) return undefined;
    const reqId = requestIdRef.current + 1;
    requestIdRef.current = reqId;

    setLoading(true);
    setError(null);
    setNoFilterResp(null);
    setWithFilterResp(null);
    setElapsed(0);

    const t0 = performance.now();
    const tick = setInterval(() => {
      setElapsed((performance.now() - t0) / 1000);
    }, 100);

    Promise.all([
      axios.post(`${API_BASE_URL}/api/demo/act2_no_filter`, {}),
      axios.post(`${API_BASE_URL}/api/demo/act2_with_filter`, {}),
    ])
      .then(([noFilter, withFilter]) => {
        if (requestIdRef.current !== reqId) return;
        setNoFilterResp(noFilter.data);
        setWithFilterResp(withFilter.data);
      })
      .catch((e) => {
        if (requestIdRef.current !== reqId) return;
        const msg =
          e.response?.data?.detail || e.message || '無法載入示範資料';
        setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
      })
      .finally(() => {
        if (requestIdRef.current !== reqId) return;
        setLoading(false);
        clearInterval(tick);
      });

    return () => {
      clearInterval(tick);
    };
  }, [open]);

  // ESC to close.
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') handleClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, handleClose]);

  // Lock body scroll while modal is open.
  useEffect(() => {
    if (!open) return undefined;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  const query =
    noFilterResp?.query ||
    withFilterResp?.query ||
    '張小明的薪資是多少？';
  const role = noFilterResp?.user_role || withFilterResp?.user_role || 'employee';
  const roleLabel = ROLE_LABELS[role] || role;

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          key="act2-overlay-root"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          onClick={handleClose}
          role="dialog"
          aria-modal="true"
          aria-label="公司治理 — 存取控制機制比較"
        >
          <motion.div
            key="act2-overlay-card"
            className="relative w-full max-w-7xl max-h-[90vh] flex flex-col bg-gray-950/95 border border-gray-700/60 rounded-xl shadow-2xl overflow-hidden"
            initial={{ opacity: 0, scale: 0.96, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.97, y: 8 }}
            transition={{ duration: 0.22, ease: 'easeOut' }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Title bar */}
            <div className="flex items-center justify-between px-5 py-3 border-b border-gray-700/50 bg-gray-900/70">
              <div className="text-sm font-semibold text-gray-200 tracking-wide">
                公司治理
              </div>
              <button
                type="button"
                onClick={handleClose}
                aria-label="關閉"
                className="text-gray-400 hover:text-gray-100 text-lg leading-none px-2 py-1 rounded hover:bg-gray-700/40"
              >
                ✕
              </button>
            </div>

            {/* Heading / subtitle */}
            <div className="px-5 py-4 border-b border-gray-700/40 bg-gray-900/40">
              <h2 className="text-lg font-bold text-gray-100">
                存取控制機制比較
              </h2>
              <p className="text-xs text-gray-400 mt-1 leading-relaxed">
                同一個查詢、同一位員工，在「啟用存取控制」與「未啟用」下，
                系統行為的差異。
              </p>
            </div>

            {/* Query / role pill row */}
            <div className="px-5 py-3 border-b border-gray-700/40 bg-gray-900/30 flex flex-wrap items-center gap-x-6 gap-y-2">
              <div className="text-xs">
                <span className="text-gray-500 mr-1.5">查詢：</span>
                <span className="font-mono text-gray-100">「{query}」</span>
              </div>
              <div className="text-xs">
                <span className="text-gray-500 mr-1.5">身份：</span>
                <span className="px-2 py-0.5 rounded border text-[11px] font-mono bg-blue-500/20 text-blue-200 border-blue-500/40">
                  {roleLabel}
                </span>
              </div>
            </div>

            {/* Body */}
            <div className="flex-1 overflow-y-auto px-5 py-4">
              {error && (
                <div className="mb-3 px-3 py-2 rounded-md border border-red-500/50 bg-red-500/10 text-sm text-red-200">
                  載入失敗：{error}
                </div>
              )}

              {loading && (
                <div className="flex flex-col items-center justify-center py-16 gap-3 text-gray-300">
                  <span className="inline-block h-8 w-8 border-2 border-gray-300 border-t-transparent rounded-full animate-spin" />
                  <div className="text-sm">AI 正在思考中...</div>
                  <div className="text-[11px] font-mono text-gray-500">
                    {elapsed.toFixed(1)}s
                  </div>
                </div>
              )}

              {!loading && !error && (noFilterResp || withFilterResp) && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <ComparisonColumn
                    variant="attack"
                    title="⚠️ 未啟用存取控制（攻擊情境）"
                    subtitle="filter OFF — 員工的查詢直接觸及所有層級的文件"
                    payload={noFilterResp?.result}
                  />
                  <ComparisonColumn
                    variant="defense"
                    title="✓ 啟用存取控制（防禦）"
                    subtitle="filter ON — 僅可檢索員工層級內的 L1 文件"
                    payload={withFilterResp?.result}
                  />
                </div>
              )}
            </div>

            {/* Footer explainer */}
            <div className="px-5 py-3 border-t border-gray-700/40 bg-gray-900/60 text-[11px] text-gray-400 leading-relaxed">
              說明：未啟用存取控制時，員工的查詢直接觸及高機密文件
              （Level 2 / Level 3），造成 PII 洩漏。啟用 metadata-based
              access control 後，相同查詢只能取得合法可見的 Level 1 文件。
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
