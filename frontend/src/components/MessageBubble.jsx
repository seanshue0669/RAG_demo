/**
 * MessageBubble — renders a single chat message in the demo conversation.
 *
 * Behaviour:
 *   - `role === 'user'`   → right-aligned, blue-toned bubble.
 *   - `role === 'assistant'` → left-aligned, gray-toned bubble.
 *   - When `piiMatches` is provided, every matching substring in `text` is
 *     wrapped with a red highlight to visualise PII leakage.
 *   - When `doc` is provided, a small metadata badge is rendered beneath the
 *     bubble showing the document's security level (color-coded) and the
 *     similarity score as a percentage.
 *
 * The component is purely presentational — it does not own state or fetch
 * data. Tailwind classes are used exclusively for styling.
 *
 * @param {object} props
 * @param {'user'|'assistant'} props.role - Who produced the message.
 * @param {string} props.text - Raw text content of the message.
 * @param {string[]} [props.piiMatches] - Substrings to highlight as PII.
 * @param {{doc_id: string, security_level: number, similarity: number,
 *          doc_type?: string}} [props.doc] - Optional source document badge.
 * @returns {JSX.Element}
 */

const SECURITY_BADGE_STYLES = {
  1: 'bg-green-500/20 text-green-300 border-green-500/40',
  2: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40',
  3: 'bg-red-500/20 text-red-300 border-red-500/40',
};

/**
 * Escape a string so it can be safely embedded inside a RegExp.
 * @param {string} s
 * @returns {string}
 */
function escapeRegExp(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Split `text` into an array of plain-text / highlighted segments based on
 * `matches`. Case-insensitive and tolerant of overlapping matches (longest
 * first to avoid partial double-highlighting).
 *
 * @param {string} text
 * @param {string[]} matches
 * @returns {Array<{ value: string, highlight: boolean }>}
 */
function buildSegments(text, matches) {
  if (!matches || matches.length === 0) {
    return [{ value: text, highlight: false }];
  }
  const cleaned = matches
    .filter((m) => typeof m === 'string' && m.length > 0)
    .sort((a, b) => b.length - a.length)
    .map(escapeRegExp);
  if (cleaned.length === 0) {
    return [{ value: text, highlight: false }];
  }
  const pattern = new RegExp(`(${cleaned.join('|')})`, 'gi');
  const parts = text.split(pattern);
  return parts
    .filter((p) => p !== '')
    .map((p) => ({ value: p, highlight: pattern.test(p) }));
}

export default function MessageBubble({ role, text, piiMatches, doc }) {
  const isUser = role === 'user';
  const containerAlign = isUser ? 'justify-end' : 'justify-start';
  const bubbleTone = isUser
    ? 'bg-blue-600/80 text-blue-50 border-blue-400/40'
    : 'bg-gray-700/80 text-gray-100 border-gray-500/40';
  const corner = isUser ? 'rounded-br-sm' : 'rounded-bl-sm';

  const segments = buildSegments(text ?? '', piiMatches);
  const badgeStyle =
    doc && SECURITY_BADGE_STYLES[doc.security_level]
      ? SECURITY_BADGE_STYLES[doc.security_level]
      : 'bg-gray-500/20 text-gray-300 border-gray-500/40';

  return (
    <div className={`w-full flex ${containerAlign} mb-3`}>
      <div className={`max-w-[80%] flex flex-col ${isUser ? 'items-end' : 'items-start'}`}>
        <div
          className={`px-4 py-2 rounded-2xl border whitespace-pre-wrap break-words text-sm leading-relaxed ${bubbleTone} ${corner}`}
        >
          {segments.map((seg, idx) =>
            seg.highlight ? (
              <span
                key={idx}
                className="bg-red-500/30 text-red-300 px-0.5 rounded"
                title="PII detected"
              >
                {seg.value}
              </span>
            ) : (
              <span key={idx}>{seg.value}</span>
            ),
          )}
        </div>
        {doc && (
          <div className="mt-1 flex items-center gap-2 text-[11px]">
            <span
              className={`px-1.5 py-0.5 rounded border font-mono ${badgeStyle}`}
              title={`Security level L${doc.security_level}`}
            >
              L{doc.security_level}
            </span>
            <span className="text-gray-400 font-mono">
              {(doc.similarity * 100).toFixed(1)}%
            </span>
            {doc.doc_type && (
              <span className="text-gray-500 italic">{doc.doc_type}</span>
            )}
            <span className="text-gray-600 truncate max-w-[160px]" title={doc.doc_id}>
              {doc.doc_id}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
