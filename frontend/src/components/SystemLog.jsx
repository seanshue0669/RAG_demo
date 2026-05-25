/**
 * SystemLog — right-hand sidebar showing RAG pipeline state.
 *
 * Mirrors the layout described in cloud-rag-demo-spec.md §五:
 *   1. Access-control status badge ("已啟用 ✓" green / "已停用 ⚠" red) with a
 *      subtitle listing the security levels currently accessible to the role.
 *   2. Generation mode badge ("LLM" / "Scripted") with a fallback note when
 *      the requested mode and the mode actually used disagree.
 *   3. Scrollable list of retrieved documents (top-k). Each card shows the
 *      doc_id, an L1/L2/L3 colour-coded security badge, similarity %, a
 *      Chinese doc_type label, department, and a truncated text excerpt that
 *      expands on click.
 *
 * Poisoned policy documents (doc_type === 'poisoned_policy') receive a red
 * border and a global "⚠️ 偵測到可疑文件" warning surfaces at the top of the
 * document list.
 *
 * Purely presentational. Tailwind only.
 *
 * @param {object} props
 * @param {Array<{doc_id:string, text:string, security_level:number,
 *                similarity:number, doc_type?:string, department?:string}>} props.retrievedDocs
 * @param {boolean} props.filterApplied
 * @param {'employee'|'manager'|'hr_admin'} props.userRole
 * @param {'llm'|'scripted'} [props.genModeUsed]
 * @param {boolean} [props.loading]
 * @returns {JSX.Element}
 */

import { useState } from 'react';

const ROLE_TO_LEVEL = {
  employee: 1,
  manager: 2,
  hr_admin: 3,
};

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

const DOC_TYPE_LABELS = {
  employee_record: '員工個資',
  employee_profile: '員工個資',
  performance_review: '績效評核',
  policy_document: '政策文件',
  internal_doc: '內部文件',
  poisoned_policy: '⚠️ 可疑文件',
};

const GEN_MODE_LABELS = {
  llm: 'LLM',
  scripted: 'Scripted',
};

/**
 * Generate a human-readable list of accessible security levels for a role.
 * @param {string} role
 * @param {boolean} filterApplied
 * @returns {string}
 */
function accessibleLevelsLabel(role, filterApplied) {
  if (!filterApplied) return 'L1, L2, L3（無存取控制）';
  const max = ROLE_TO_LEVEL[role];
  if (!max) return '未知角色';
  const labels = [];
  for (let i = 1; i <= max; i += 1) {
    labels.push(`L${i}`);
  }
  return labels.join(', ');
}

/**
 * Render a single retrieved-document card.
 * @param {object} props
 * @param {{doc_id:string, text:string, security_level:number, similarity:number,
 *          doc_type?:string, department?:string}} props.doc
 * @returns {JSX.Element}
 */
function DocCard({ doc }) {
  const [expanded, setExpanded] = useState(false);
  const isPoisoned = doc.doc_type === 'poisoned_policy';
  const levelStyle =
    LEVEL_BADGE_STYLES[doc.security_level] ||
    'bg-gray-500/20 text-gray-300 border-gray-500/40';
  const typeLabel = DOC_TYPE_LABELS[doc.doc_type] || doc.doc_type || '—';
  const text = doc.text ?? '';
  const excerpt = text.length > 80 ? `${text.slice(0, 80)}...` : text;
  const hasMore = text.length > 80;

  const borderTone = isPoisoned
    ? 'border-red-500/70 ring-1 ring-red-500/40'
    : 'border-gray-700/50';

  return (
    <div
      className={`p-2.5 rounded-md border bg-gray-900/40 ${borderTone}`}
    >
      <div className="flex items-center gap-2 mb-1">
        <span
          className="font-mono text-sm text-gray-100 truncate"
          title={doc.doc_id}
        >
          {doc.doc_id}
        </span>
        <span
          className={`px-1.5 py-0.5 rounded border text-[10px] font-mono ${levelStyle}`}
          title={`Security level L${doc.security_level}`}
        >
          L{doc.security_level}
        </span>
        <span className="ml-auto text-[11px] font-mono text-gray-400">
          {Number.isFinite(doc.similarity)
            ? `${(doc.similarity * 100).toFixed(1)}%`
            : '—'}
        </span>
      </div>
      <div className="flex items-center gap-2 text-[11px] text-gray-400 mb-1">
        <span className={isPoisoned ? 'text-red-300 font-semibold' : ''}>
          {typeLabel}
        </span>
        {doc.department && (
          <>
            <span className="text-gray-600">·</span>
            <span>{doc.department}</span>
          </>
        )}
      </div>
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="block w-full text-left text-xs text-gray-300 leading-relaxed whitespace-pre-wrap break-words hover:text-gray-100"
        title={hasMore ? '點擊展開／收合' : ''}
      >
        {expanded ? text : excerpt}
        {hasMore && (
          <span className="ml-1 text-blue-300 text-[11px]">
            {expanded ? '［收合］' : '［展開］'}
          </span>
        )}
      </button>
    </div>
  );
}

export default function SystemLog({
  retrievedDocs = [],
  filterApplied,
  userRole,
  genModeUsed,
  loading = false,
}) {
  const hasPoisoned = retrievedDocs.some((d) => d?.doc_type === 'poisoned_policy');

  // Access-control badge.
  const accessBadge = filterApplied
    ? {
        text: '已啟用 ✓',
        cls: 'bg-green-500/20 text-green-300 border-green-500/40',
      }
    : {
        text: '已停用 ⚠',
        cls: 'bg-red-500/20 text-red-300 border-red-500/40',
      };

  // Generation-mode badge.
  const genLabel = GEN_MODE_LABELS[genModeUsed] ?? genModeUsed ?? '—';
  const genBadgeCls =
    genModeUsed === 'llm'
      ? 'bg-purple-500/20 text-purple-300 border-purple-500/40'
      : genModeUsed === 'scripted'
        ? 'bg-blue-500/20 text-blue-300 border-blue-500/40'
        : 'bg-gray-500/20 text-gray-300 border-gray-500/40';

  return (
    <div className="flex flex-col h-full w-full bg-gray-900/40 border border-gray-700/40 rounded-lg overflow-hidden">
      {/* Header */}
      <div className="px-4 py-2.5 border-b border-gray-700/40 bg-gray-800/40">
        <h2 className="text-sm font-semibold text-gray-100 tracking-wide">
          系統狀態
        </h2>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
        {/* Section 1: Access control */}
        <section>
          <div className="text-xs uppercase tracking-wider text-gray-500 mb-1.5">
            存取控制狀態
          </div>
          <div className="flex items-center gap-2">
            <span
              className={`px-2 py-0.5 rounded border text-xs font-mono ${accessBadge.cls}`}
            >
              {accessBadge.text}
            </span>
            <span className="text-[11px] text-gray-400">
              可存取等級: {accessibleLevelsLabel(userRole, filterApplied)}
            </span>
          </div>
        </section>

        {/* Section 2: Generation mode */}
        <section>
          <div className="text-xs uppercase tracking-wider text-gray-500 mb-1.5">
            生成模式
          </div>
          <div className="flex items-center gap-2">
            <span
              className={`px-2 py-0.5 rounded border text-xs font-mono ${genBadgeCls}`}
            >
              {genLabel}
            </span>
            {genModeUsed === 'scripted' && (
              <span className="text-[11px] text-yellow-300">
                （可能為 LLM fallback）
              </span>
            )}
          </div>
        </section>

        {/* Section 3: Retrieved documents */}
        <section className="flex flex-col min-h-0">
          <div className="text-xs uppercase tracking-wider text-gray-500 mb-1.5 flex items-center justify-between">
            <span>檢索到的文件</span>
            <span className="text-[11px] normal-case text-gray-500 font-mono">
              {retrievedDocs.length} 筆
            </span>
          </div>

          {hasPoisoned && (
            <div className="mb-2 px-2.5 py-1.5 rounded-md border border-red-500/60 bg-red-500/15 text-red-300 text-xs font-medium">
              ⚠️ 偵測到可疑文件
            </div>
          )}

          {loading && retrievedDocs.length === 0 && (
            <div className="flex items-center gap-2 text-xs text-gray-400 italic px-1 py-2">
              <span className="inline-block h-3 w-3 border-2 border-gray-300 border-t-transparent rounded-full animate-spin" />
              檢索中...
            </div>
          )}

          {!loading && retrievedDocs.length === 0 && (
            <div className="text-xs text-gray-500 italic px-1 py-2">
              尚無檢索結果
            </div>
          )}

          <div className="space-y-2">
            {retrievedDocs.map((doc, idx) => (
              <DocCard key={`${doc.doc_id}-${idx}`} doc={doc} />
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
