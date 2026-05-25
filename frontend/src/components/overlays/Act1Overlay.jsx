/**
 * Act1Overlay — "About NovaTech" modal that surfaces the Act 1 demo flow.
 *
 * On mount (or whenever `open` flips from false → true) the overlay POSTs to
 * `/api/demo/act1` and renders the resulting `DemoResponse` payload. Act 1 is
 * the baseline / happy-path scenario: a regular employee asks a public-policy
 * question, the retriever returns L1 documents only, and the LLM answers
 * correctly. The overlay is intentionally framed as a benign company-info
 * page; the security-demo aspect emerges through the displayed data.
 *
 * Behaviour:
 *   - Auto-fires the demo request on open; cancels in-flight requests on close.
 *   - Shows an animated loading state ("AI 正在思考中...") plus an elapsed
 *     seconds counter while the 5-10s LLM call resolves.
 *   - Closes via the [X] button, backdrop click, or the ESC key.
 *   - Uses framer-motion for fade/scale transitions and Tailwind for styling.
 *
 * Props:
 *   @param {object} props
 *   @param {boolean} props.open   Whether the overlay is visible.
 *   @param {() => void} props.onClose  Invoked when the user dismisses the modal.
 *   @returns {JSX.Element|null}
 */

import { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { AnimatePresence, motion } from 'framer-motion';

const SECURITY_BADGE_STYLES = {
  1: 'bg-green-500/20 text-green-300 border-green-500/40',
  2: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40',
  3: 'bg-red-500/20 text-red-300 border-red-500/40',
};

/**
 * Render a single retrieved document as a compact card.
 * @param {{ doc: { doc_id: string, text: string, security_level: number,
 *           similarity: number, doc_type?: string, department?: string|null } }} props
 * @returns {JSX.Element}
 */
function RetrievedDocCard({ doc }) {
  const badge =
    SECURITY_BADGE_STYLES[doc.security_level] ||
    'bg-gray-500/20 text-gray-300 border-gray-500/40';
  return (
    <div className="rounded-lg border border-gray-700 bg-gray-800/60 px-3 py-2 flex flex-col gap-1">
      <div className="flex items-center gap-2 text-[11px] font-mono">
        <span
          className={`px-1.5 py-0.5 rounded border ${badge}`}
          title={`Security level L${doc.security_level}`}
        >
          L{doc.security_level}
        </span>
        <span className="text-gray-300 truncate" title={doc.doc_id}>
          {doc.doc_id}
        </span>
        {doc.doc_type && (
          <span className="text-gray-500 italic">{doc.doc_type}</span>
        )}
        <span className="ml-auto text-gray-400">
          sim={doc.similarity?.toFixed?.(2) ?? '—'}
        </span>
      </div>
      <p className="text-xs text-gray-300 leading-relaxed line-clamp-3 whitespace-pre-wrap">
        {doc.text}
      </p>
    </div>
  );
}

export default function Act1Overlay({ open, onClose }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const abortRef = useRef(null);

  // Fetch /api/demo/act1 whenever the overlay opens; tear down on close.
  useEffect(() => {
    if (!open) return undefined;
    const controller = new AbortController();
    abortRef.current = controller;
    setData(null);
    setError(null);
    setLoading(true);
    setElapsed(0);

    axios
      .post('/api/demo/act1', null, { signal: controller.signal })
      .then((res) => {
        setData(res.data);
      })
      .catch((err) => {
        if (axios.isCancel(err) || err.name === 'CanceledError') return;
        setError(err?.response?.data?.detail || err.message || '請求失敗');
      })
      .finally(() => {
        setLoading(false);
      });

    return () => {
      controller.abort();
    };
  }, [open]);

  // Elapsed-seconds counter while the LLM call is in flight.
  useEffect(() => {
    if (!loading) return undefined;
    const start = Date.now();
    const id = setInterval(() => {
      setElapsed(Math.floor((Date.now() - start) / 1000));
    }, 250);
    return () => clearInterval(id);
  }, [loading]);

  // ESC key closes the modal.
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') onClose?.();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  const result = data?.result;
  const retrievedDocs = result?.retrieved_docs || [];

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          key="act1-backdrop"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          onClick={onClose}
        >
          <motion.div
            key="act1-modal"
            className="w-full max-w-4xl max-h-[90vh] overflow-y-auto rounded-2xl border border-gray-700 bg-gray-900 text-gray-100 shadow-2xl"
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 8 }}
            transition={{ duration: 0.22, ease: 'easeOut' }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-700">
              <h2 className="text-xl font-semibold tracking-wide">
                關於 NovaTech
              </h2>
              <button
                type="button"
                onClick={onClose}
                aria-label="關閉"
                className="rounded-full w-8 h-8 flex items-center justify-center text-gray-400 hover:text-gray-100 hover:bg-gray-800 transition"
              >
                ×
              </button>
            </div>

            {/* Subtitle band */}
            <div className="px-6 py-3 bg-gray-800/40 border-b border-gray-700">
              <p className="text-sm font-medium text-gray-200">
                正常使用情境
              </p>
              <p className="text-xs text-gray-400 mt-0.5">
                一般員工查詢公開政策，存取控制正常運作
              </p>
            </div>

            {/* Body */}
            <div className="px-6 py-5 space-y-5">
              {/* Query meta */}
              <div className="space-y-1 text-sm">
                <p className="text-gray-300">
                  <span className="text-gray-500 mr-2">▸ 查詢：</span>
                  <span className="text-gray-100">
                    「{data?.query ?? '請問公司的請假規定？'}」
                  </span>
                </p>
                <p className="text-gray-300">
                  <span className="text-gray-500 mr-2">▸ 身份：</span>
                  <span className="text-gray-100">
                    一般員工 (Level 1)
                  </span>
                </p>
              </div>

              {/* Loading state */}
              {loading && (
                <div className="flex flex-col items-center justify-center py-12 gap-3">
                  <div className="relative w-12 h-12">
                    <div className="absolute inset-0 rounded-full border-2 border-gray-700" />
                    <div className="absolute inset-0 rounded-full border-2 border-t-blue-400 border-r-transparent border-b-transparent border-l-transparent animate-spin" />
                  </div>
                  <p className="text-sm text-gray-300">AI 正在思考中...</p>
                  <p className="text-xs text-gray-500 font-mono">
                    已耗時 {elapsed} 秒
                  </p>
                </div>
              )}

              {/* Error state */}
              {!loading && error && (
                <div className="rounded-lg border border-red-700/60 bg-red-900/20 px-4 py-3 text-sm text-red-200">
                  請求失敗：{String(error)}
                </div>
              )}

              {/* Result */}
              {!loading && !error && data && (
                <>
                  <section>
                    <h3 className="text-sm font-medium text-gray-300 mb-2">
                      檢索到的文件：
                    </h3>
                    {retrievedDocs.length === 0 ? (
                      <p className="text-xs text-gray-500 italic">
                        （無相關文件）
                      </p>
                    ) : (
                      <div className="flex flex-col gap-2">
                        {retrievedDocs.map((doc, idx) => (
                          <RetrievedDocCard
                            key={doc.doc_id || idx}
                            doc={doc}
                          />
                        ))}
                      </div>
                    )}
                  </section>

                  <section>
                    <h3 className="text-sm font-medium text-gray-300 mb-2">
                      AI 回答：
                    </h3>
                    <div className="rounded-lg border border-gray-700 bg-gray-800/60 px-4 py-3 text-sm leading-relaxed text-gray-100 whitespace-pre-wrap">
                      {result?.answer || '（無回答）'}
                    </div>
                  </section>

                  {/* Narration footer */}
                  <div className="pt-3 border-t border-gray-700">
                    <div className="rounded-lg bg-gray-800/80 border border-gray-700 px-4 py-3">
                      <p className="text-xs uppercase tracking-wider text-gray-500 mb-1">
                        說明
                      </p>
                      <p className="text-sm text-gray-200 leading-relaxed whitespace-pre-wrap">
                        {data.narration ||
                          '本情境展示系統在權限正確設定下的標準操作。所有回傳文件均為 Level 1 公開政策，AI 回答基於合法可見的文件內容。'}
                      </p>
                    </div>
                  </div>
                </>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
