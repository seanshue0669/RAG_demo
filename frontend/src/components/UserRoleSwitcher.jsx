/**
 * UserRoleSwitcher — three-way pill selector for the simulated logged-in role.
 *
 * Roles map to a security clearance level used by the RAG pipeline:
 *   - employee  → Lv 1 (一般員工)
 *   - manager   → Lv 2 (部門主管)
 *   - hr_admin  → Lv 3 (HR 管理員)
 *
 * The active pill is visually highlighted and a coloured clearance badge is
 * rendered next to the group, matching the security palette used by
 * MessageBubble (green / yellow / red for L1 / L2 / L3).
 *
 * This component is fully controlled — it never owns state. `onChange` is
 * fired with the selected role string whenever the user picks a new pill.
 *
 * @param {object} props
 * @param {'employee'|'manager'|'hr_admin'} props.role - Currently active role.
 * @param {(role: 'employee'|'manager'|'hr_admin') => void} props.onChange
 *   Callback invoked when the user selects a new role.
 * @returns {JSX.Element}
 */

const ROLE_OPTIONS = [
  { value: 'employee', label: '一般員工', level: 1 },
  { value: 'manager', label: '部門主管', level: 2 },
  { value: 'hr_admin', label: 'HR 管理員', level: 3 },
];

const LEVEL_BADGE_STYLES = {
  1: 'bg-green-500/20 text-green-300 border-green-500/40',
  2: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40',
  3: 'bg-red-500/20 text-red-300 border-red-500/40',
};

export default function UserRoleSwitcher({ role, onChange }) {
  const activeOption =
    ROLE_OPTIONS.find((opt) => opt.value === role) ?? ROLE_OPTIONS[0];
  const badgeStyle = LEVEL_BADGE_STYLES[activeOption.level];

  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-gray-400 font-medium">使用者角色</span>
      <div className="inline-flex rounded-full bg-gray-800/80 border border-gray-700 p-1">
        {ROLE_OPTIONS.map((opt) => {
          const active = opt.value === role;
          const base =
            'px-3 py-1.5 text-sm rounded-full transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-blue-400/40';
          const activeCls = 'bg-blue-600 text-white shadow';
          const inactiveCls = 'text-gray-300 hover:bg-gray-700/70';
          return (
            <button
              key={opt.value}
              type="button"
              onClick={() => onChange(opt.value)}
              className={`${base} ${active ? activeCls : inactiveCls}`}
              aria-pressed={active}
            >
              {opt.label}
            </button>
          );
        })}
      </div>
      <span
        className={`px-2 py-0.5 text-xs font-mono rounded border ${badgeStyle}`}
        title={`Security clearance level ${activeOption.level}`}
      >
        Lv {activeOption.level}
      </span>
    </div>
  );
}
