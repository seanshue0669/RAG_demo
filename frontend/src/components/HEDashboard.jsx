/**
 * HEDashboard — Live demo panel for CKKS homomorphic-encryption search.
 *
 * Replaces the SystemLog sidebar during 第四幕 (Act 4) of the demo. Drives
 * the POST /api/he/search flow described in cloud-rag-demo-spec.md §4.7.
 *
 * Visual layout:
 *   1. Header: 「同態加密搜尋 — CKKS 即時 Demo」
 *   2. Query bar with example-suggestion chips. Submitting calls onRunSearch.
 *   3. Horizontal four-stage timing diagram (left-to-right):
 *        Encrypt query (blue) → Compute similarity (orange) →
 *        Decrypt scores (green) → Total (purple).
 *      Bar widths are proportional to the dominant stage; framer-motion
 *      animates bar growth on data updates.
 *   4. Contrasting "明文搜尋耗時" block on the right for plaintext comparison.
 *   5. Two-column result grid: 密文搜尋結果 (left) vs 明文搜尋結果 (right).
 *      Each row shows doc_id, L1/L2/L3 security badge, similarity %, and the
 *      first 60 characters of the document text.
 *   6. Empty state: 「請輸入查詢並點擊搜尋」
 *      Loading state: pulsing 「正在加密 → 搜尋 → 解密...」 indicator.
 *
 * Purely presentational. Tailwind only. No npm installs.
 *
 * @param {object} props
 * @param {string} props.query
 *   Latest query string the parent considers active (used to seed the input).
 * @param {null | {
 *   results: Array<{doc_id:string, similarity:number, text:string,
 *                   security_level:number}>,
 *   timing: {encrypt_query_ms:number, compute_similarity_ms:number,
 *            decrypt_ms:number, total_ms:number},
 *   plaintext_results: Array<{doc_id:string, similarity:number, text:string,
 *                             security_level:number}>,
 *   plaintext_timing_ms: number
 * }} props.data
 *   Response payload from POST /api/he/search, or null before first run.
 * @param {boolean} props.loading
 * @param {(queryText: string) => void} props.onRunSearch
 *   Parent callback that performs the API call.
 * @returns {JSX.Element}
 */

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';

const EXAMPLE_QUERIES = ['薪資查詢', '請假規定', '林志明的個資'];

const LEVEL_LABELS = {
  1: 'L1 公開',
  2: 'L2 內部',
  3: 'L3 機密',
};

const LEVEL_BADGE_STYLES = {
  1: 'bg-green-500/20 text-green-300 border-green-500/40',
  2: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40',
  3: 'bg-red-500/20 text-red-300 border-red-500/40',
};

const STAGE_COLORS = {
  encrypt: {
    label: '加密查詢',
    bar: 'bg-blue-500',
    text: 'text-blue-300',
    border: 'border-blue-500/40',
    bg: 'bg-blue-500/10',
  },
  compute: {
    label: '密文相似度計算',
    bar: 'bg-orange-500',
    text: 'text-orange-300',
    border: 'border-orange-500/40',
    bg: 'bg-orange-500/10',
  },
  decrypt: {
    label: '解密分數',
    bar: 'bg-green-500',
    text: 'text-green-300',
    border: 'border-green-500/40',
    bg: 'bg-green-500/10',
  },
  total: {
    label: '總耗時',
    bar: 'bg-purple-500',
    text: 'text-purple-300',
    border: 'border-purple-500/40',
    bg: 'bg-purple-500/10',
  },
};

/**
 * Render a single CKKS timing stage as a labelled bar.
 * @param {object} props
 * @param {'encrypt'|'compute'|'decrypt'|'total'} props.kind
 * @param {number} props.ms
 * @param {number} props.maxMs
 * @returns {JSX.Element}
 */
function TimingBar({ kind, ms, maxMs }) {
  const color = STAGE_COLORS[kind];
  const pct = maxMs > 0 ? Math.min(100, (ms / maxMs) * 100) : 0;
  const safeMs = Number.isFinite(ms) ? ms : 0;
  return (
    <div className={`flex-1 rounded-md border ${color.border} ${color.bg} p-2.5`}>
      <div className="flex items-center justify-between mb-1.5">
        <span className={`text-[11px] uppercase tracking-wider ${color.text}`}>
          {color.label}
        </span>
        <span className={`text-xs font-mono ${color.text}`}>
          {safeMs.toFixed(0)} ms
        </span>
      </div>
      <div className="h-2 w-full bg-gray-800/70 rounded overflow-hidden">
        <motion.div
          className={`h-full ${color.bar}`}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
        />
      </div>
    </div>
  );
}

/**
 * Render a single result row.
 * @param {object} props
 * @param {{doc_id:string, similarity:number, text:string,
 *          security_level:number}} props.row
 * @returns {JSX.Element}
 */
function ResultRow({ row }) {
  const levelStyle =
    LEVEL_BADGE_STYLES[row.security_level] ||
    'bg-gray-500/20 text-gray-300 border-gray-500/40';
  const text = row.text ?? '';
  const excerpt = text.length > 60 ? `${text.slice(0, 60)}...` : text;
  const sim = Number.isFinite(row.similarity)
    ? `${(row.similarity * 100).toFixed(1)}%`
    : '—';

  return (
    <div className="p-2.5 rounded-md border border-gray-700/50 bg-gray-900/40">
      <div className="flex items-center gap-2 mb-1">
        <span
          className="font-mono text-sm text-gray-100 truncate"
          title={row.doc_id}
        >
          {row.doc_id}
        </span>
        <span
          className={`px-1.5 py-0.5 rounded border text-[10px] font-mono ${levelStyle}`}
          title={LEVEL_LABELS[row.security_level] || ''}
        >
          L{row.security_level}
        </span>
        <span className="ml-auto text-[11px] font-mono text-gray-400">
          {sim}
        </span>
      </div>
      <div className="text-xs text-gray-300 leading-relaxed break-words">
        {excerpt}
      </div>
    </div>
  );
}

/**
 * Render an empty placeholder for a result column when there's no data.
 * @param {object} props
 * @param {string} props.message
 * @returns {JSX.Element}
 */
function EmptyResults({ message }) {
  return (
    <div className="text-xs text-gray-500 italic px-1 py-2">{message}</div>
  );
}

export default function HEDashboard({
  query = '',
  data = null,
  loading = false,
  onRunSearch,
}) {
  const [inputValue, setInputValue] = useState(query);

  // Keep the local input in sync if the parent updates `query` externally.
  useEffect(() => {
    setInputValue(query);
  }, [query]);

  const timing = data?.timing;
  const plaintextMs = data?.plaintext_timing_ms;
  const results = data?.results ?? [];
  const plaintextResults = data?.plaintext_results ?? [];

  // Bar widths share a common scale so the orange "compute" stage dominates.
  const maxMs = timing
    ? Math.max(
        timing.encrypt_query_ms ?? 0,
        timing.compute_similarity_ms ?? 0,
        timing.decrypt_ms ?? 0,
        timing.total_ms ?? 0,
      )
    : 0;

  const speedup =
    timing && plaintextMs && plaintextMs > 0
      ? (timing.total_ms / plaintextMs).toFixed(0)
      : null;

  const handleSubmit = (event) => {
    event.preventDefault();
    const text = inputValue.trim();
    if (!text || loading || typeof onRunSearch !== 'function') return;
    onRunSearch(text);
  };

  const handleExample = (example) => {
    setInputValue(example);
    if (!loading && typeof onRunSearch === 'function') {
      onRunSearch(example);
    }
  };

  const showEmptyState = !loading && data == null;

  return (
    <div className="flex flex-col h-full w-full bg-gray-900/40 border border-gray-700/40 rounded-lg overflow-hidden">
      {/* Header */}
      <div className="px-4 py-2.5 border-b border-gray-700/40 bg-gray-800/40">
        <h2 className="text-sm font-semibold text-gray-100 tracking-wide">
          同態加密搜尋 — CKKS 即時 Demo
        </h2>
        <p className="text-[11px] text-gray-400 mt-0.5">
          密文檢索全程不解密，與明文搜尋結果並列比較。
        </p>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
        {/* Query bar */}
        <section>
          <div className="text-xs uppercase tracking-wider text-gray-500 mb-1.5">
            查詢輸入
          </div>
          <form onSubmit={handleSubmit} className="flex items-center gap-2">
            <input
              type="text"
              value={inputValue}
              onChange={(event) => setInputValue(event.target.value)}
              placeholder="輸入查詢，例如：薪資查詢"
              disabled={loading}
              className="flex-1 px-3 py-2 rounded-md border border-gray-700/60 bg-gray-900/60 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-purple-500/60 disabled:opacity-60"
            />
            <button
              type="submit"
              disabled={loading || !inputValue.trim()}
              className="px-3 py-2 rounded-md border border-purple-500/40 bg-purple-500/20 text-sm text-purple-200 hover:bg-purple-500/30 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? '搜尋中…' : '加密搜尋'}
            </button>
          </form>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <span className="text-[11px] text-gray-500 self-center">範例：</span>
            {EXAMPLE_QUERIES.map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => handleExample(example)}
                disabled={loading}
                className="px-2 py-0.5 rounded-full border border-gray-700/60 bg-gray-800/60 text-[11px] text-gray-300 hover:bg-gray-700/60 hover:text-gray-100 disabled:opacity-50"
              >
                {example}
              </button>
            ))}
          </div>
        </section>

        {/* Loading indicator */}
        {loading && (
          <div className="flex items-center gap-2 text-xs text-purple-200 italic px-1">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-purple-400 animate-pulse" />
            正在加密 → 搜尋 → 解密...
          </div>
        )}

        {/* Empty state */}
        {showEmptyState && (
          <div className="text-sm text-gray-400 italic px-1 py-6 text-center border border-dashed border-gray-700/50 rounded-md">
            請輸入查詢並點擊搜尋
          </div>
        )}

        {/* Timing diagram */}
        {timing && (
          <section>
            <div className="text-xs uppercase tracking-wider text-gray-500 mb-1.5 flex items-center justify-between">
              <span>CKKS 四階段耗時</span>
              {speedup && (
                <span className="text-[11px] normal-case text-gray-400">
                  CKKS 比明文慢約{' '}
                  <span className="text-orange-300 font-mono">
                    {speedup}×
                  </span>
                </span>
              )}
            </div>
            <div className="flex items-stretch gap-2">
              <div className="flex-1 grid grid-cols-1 sm:grid-cols-4 gap-2">
                <TimingBar
                  kind="encrypt"
                  ms={timing.encrypt_query_ms}
                  maxMs={maxMs}
                />
                <TimingBar
                  kind="compute"
                  ms={timing.compute_similarity_ms}
                  maxMs={maxMs}
                />
                <TimingBar
                  kind="decrypt"
                  ms={timing.decrypt_ms}
                  maxMs={maxMs}
                />
                <TimingBar kind="total" ms={timing.total_ms} maxMs={maxMs} />
              </div>
              {/* Plaintext contrast block */}
              <div className="w-28 shrink-0 rounded-md border border-gray-700/60 bg-gray-800/40 p-2.5 flex flex-col items-center justify-center">
                <div className="text-[10px] uppercase tracking-wider text-gray-400">
                  明文搜尋耗時
                </div>
                <div className="mt-1 text-lg font-mono text-gray-100">
                  {Number.isFinite(plaintextMs)
                    ? `${plaintextMs.toFixed(0)}`
                    : '—'}
                </div>
                <div className="text-[10px] text-gray-500">ms</div>
              </div>
            </div>
          </section>
        )}

        {/* Results comparison */}
        {data && (
          <section>
            <div className="text-xs uppercase tracking-wider text-gray-500 mb-1.5">
              檢索結果對照
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-semibold text-purple-200">
                    密文搜尋結果
                  </span>
                  <span className="text-[11px] font-mono text-gray-500">
                    {results.length} 筆
                  </span>
                </div>
                <div className="space-y-2">
                  {results.length === 0 ? (
                    <EmptyResults message="尚無密文檢索結果" />
                  ) : (
                    results.map((row, idx) => (
                      <ResultRow key={`enc-${row.doc_id}-${idx}`} row={row} />
                    ))
                  )}
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-semibold text-gray-200">
                    明文搜尋結果
                  </span>
                  <span className="text-[11px] font-mono text-gray-500">
                    {plaintextResults.length} 筆
                  </span>
                </div>
                <div className="space-y-2">
                  {plaintextResults.length === 0 ? (
                    <EmptyResults message="尚無明文檢索結果" />
                  ) : (
                    plaintextResults.map((row, idx) => (
                      <ResultRow key={`plain-${row.doc_id}-${idx}`} row={row} />
                    ))
                  )}
                </div>
              </div>
            </div>
            <p className="text-[11px] text-gray-500 mt-2">
              註：兩側結果相似度應接近——CKKS
              在保護資料下達成可驗證的同等檢索品質。
            </p>
          </section>
        )}
      </div>
    </div>
  );
}
