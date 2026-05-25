/**
 * ActNavigation — top-level tab strip for switching between the four demo
 * acts. Each act maps to a different RAG security narrative:
 *
 *   - act1: 基本 RAG 流程
 *   - act2: 檢索層權限漏洞
 *   - act3: 生成層 Prompt Injection
 *   - act4: 儲存層同態加密防禦
 *
 * The component is fully controlled. The currently selected tab is
 * underlined and tinted blue; inactive tabs use a muted gray treatment.
 *
 * @param {object} props
 * @param {'act1'|'act2'|'act3'|'act4'} props.act - Currently selected act.
 * @param {(act: 'act1'|'act2'|'act3'|'act4') => void} props.onChange
 *   Callback invoked when the user clicks a different tab.
 * @param {string} [props.subtitle] - Optional one-line theme description
 *   rendered beneath the tab strip for the active act.
 * @returns {JSX.Element}
 */

const ACT_OPTIONS = [
  { value: 'act1', label: '第一幕' },
  { value: 'act2', label: '第二幕' },
  { value: 'act3', label: '第三幕' },
  { value: 'act4', label: '第四幕' },
];

export default function ActNavigation({ act, onChange, subtitle }) {
  return (
    <nav className="w-full border-b border-gray-700 bg-gray-900/60">
      <div className="flex items-end gap-1 px-4">
        {ACT_OPTIONS.map((opt) => {
          const active = opt.value === act;
          const base =
            'px-4 py-2 text-sm font-medium transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-blue-400/40 border-b-2';
          const activeCls = 'text-blue-300 border-blue-400';
          const inactiveCls =
            'text-gray-400 border-transparent hover:text-gray-200 hover:border-gray-600';
          return (
            <button
              key={opt.value}
              type="button"
              onClick={() => onChange(opt.value)}
              className={`${base} ${active ? activeCls : inactiveCls}`}
              aria-pressed={active}
              aria-current={active ? 'page' : undefined}
            >
              {opt.label}
            </button>
          );
        })}
      </div>
      {subtitle && (
        <div className="px-4 pb-2 text-xs text-gray-500 italic">{subtitle}</div>
      )}
    </nav>
  );
}
