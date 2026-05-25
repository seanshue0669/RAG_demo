/**
 * Act4Overlay — "Privacy Protection" modal wrapping the HEDashboard live demo.
 *
 * Surfaced secretly via the footer link 「隱私權保護」. The overlay frames the
 * Act 4 demo (CKKS homomorphic-encryption search) as a privacy-protection
 * disclosure page. When `open` flips false → true the overlay seeds a default
 * query and immediately POSTs to `/api/he/search`, then forwards the resulting
 * payload into <HEDashboard /> for visualisation.
 *
 * Behaviour:
 *   - Auto-fires a search on open with a default query (公司請假規定).
 *   - `onRunSearch(newQuery)` re-fires `/api/he/search` and refreshes state.
 *   - Closes via the [X] button, backdrop click, or the ESC key.
 *   - Cancels any in-flight axios request when the overlay closes or a new
 *     search begins.
 *   - Uses framer-motion for fade transitions; Tailwind for layout.
 *
 * Props:
 *   @param {object} props
 *   @param {boolean} props.open    Whether the overlay is visible.
 *   @param {() => void} props.onClose  Invoked when the user dismisses the modal.
 *   @returns {JSX.Element|null}
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { AnimatePresence, motion } from 'framer-motion';

import HEDashboard from '../HEDashboard.jsx';

const DEFAULT_QUERY = '公司請假規定';
const DEFAULT_TOP_K = 5;

export default function Act4Overlay({ open, onClose }) {
  const [query, setQuery] = useState(DEFAULT_QUERY);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const abortRef = useRef(null);

  // Stable searcher used both for the auto-fire on open and the dashboard's
  // onRunSearch callback. Aborts any previous in-flight request.
  const runSearch = useCallback((queryText) => {
    const text = (queryText ?? '').trim();
    if (!text) return;

    // Abort the previous request, if any.
    if (abortRef.current) {
      abortRef.current.abort();
    }
    const controller = new AbortController();
    abortRef.current = controller;

    setQuery(text);
    setLoading(true);
    setError(null);

    axios
      .post(
        '/api/he/search',
        { query: text, top_k: DEFAULT_TOP_K },
        { signal: controller.signal },
      )
      .then((res) => {
        setData(res.data);
      })
      .catch((err) => {
        if (axios.isCancel(err) || err.name === 'CanceledError') return;
        setError(err?.response?.data?.detail || err.message || '請求失敗');
      })
      .finally(() => {
        if (abortRef.current === controller) {
          abortRef.current = null;
        }
        setLoading(false);
      });
  }, []);

  // Auto-fire the default query when the overlay opens; reset state on close.
  useEffect(() => {
    if (!open) {
      if (abortRef.current) {
        abortRef.current.abort();
        abortRef.current = null;
      }
      return undefined;
    }
    setData(null);
    setError(null);
    setQuery(DEFAULT_QUERY);
    runSearch(DEFAULT_QUERY);
    return () => {
      if (abortRef.current) {
        abortRef.current.abort();
        abortRef.current = null;
      }
    };
  }, [open, runSearch]);

  // ESC key closes the modal.
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') onClose?.();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          key="act4-backdrop"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          onClick={onClose}
        >
          <motion.div
            key="act4-modal"
            className="w-full max-w-6xl max-h-[90vh] overflow-y-auto rounded-2xl border border-gray-700 bg-gray-900 text-gray-100 shadow-2xl"
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 8 }}
            transition={{ duration: 0.22, ease: 'easeOut' }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-700">
              <h2 className="text-xl font-semibold tracking-wide">
                隱私權保護
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
                同態加密儲存 — 抵禦 embedding 逆向攻擊
              </p>
              <p className="text-xs text-gray-400 mt-0.5">
                即使資料庫被攻破，攻擊者也無法從密文 embedding 還原原文。
              </p>
            </div>

            {/* Body — HEDashboard */}
            <div className="px-6 py-5">
              {error && (
                <div className="mb-3 rounded-lg border border-red-700/60 bg-red-900/20 px-4 py-2 text-xs text-red-200">
                  請求失敗：{String(error)}
                </div>
              )}
              <div className="h-[60vh] min-h-[420px]">
                <HEDashboard
                  query={query}
                  data={data}
                  loading={loading}
                  onRunSearch={runSearch}
                />
              </div>
            </div>

            {/* Footer narration */}
            <div className="px-6 pb-5">
              <div className="rounded-lg bg-gray-800/80 border border-gray-700 px-4 py-3">
                <p className="text-xs uppercase tracking-wider text-gray-500 mb-1">
                  說明
                </p>
                <p className="text-sm text-gray-200 leading-relaxed">
                  CKKS 同態加密允許在不解密的情況下計算相似度。代價是每次搜尋
                  需要對每筆 embedding 做密文點積，速度比明文搜尋慢約 400 倍
                  （本機 ~1.3s vs ~3ms）。對於不需即時毫秒級延遲的企業 RAG
                  場景，是合理的安全 / 效能折衷。
                </p>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
