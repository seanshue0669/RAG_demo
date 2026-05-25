/**
 * LoginPage — corporate intranet style entry screen for the NovaTech HR
 * self-service portal. This is the visible front door of the demo and is
 * intentionally styled to look like a real internal tool rather than a
 * generic minimalist login. The user picks one of three roles, which the
 * AuthContext then locks for the entire session.
 *
 * Visual contract:
 *   - Dark neutral background with a centered card.
 *   - NovaTech "N" logo placeholder + corporate title and subtitle.
 *   - Compliance-style monitoring disclaimer to sell the "real intranet" feel.
 *   - Three radio-style role cards, each annotated with the document
 *     security tier the role can access (L1, L1-L2, L1-L3).
 *   - Primary "登入" button, disabled until a role is selected.
 *   - framer-motion fade-in on mount.
 *
 * Behaviour:
 *   - On submit, calls login(role) from AuthContext. The parent App owns the
 *     actual page swap based on isAuthed; this component does not navigate.
 *
 * All visible strings are in Traditional Chinese per the project i18n rule.
 */

import { useState } from 'react';
import { motion } from 'framer-motion';
import { useAuth } from '../contexts/AuthContext.jsx';

/**
 * Role catalogue rendered as selectable cards. Keep this list as the single
 * source of truth for role labels + access-tier copy on the login screen.
 */
const ROLE_OPTIONS = [
  {
    value: 'employee',
    label: '一般員工',
    description: '可存取公開政策文件 (L1)',
  },
  {
    value: 'manager',
    label: '部門主管',
    description: '可存取公開政策 + 部門內部文件 (L1-L2)',
  },
  {
    value: 'hr_admin',
    label: 'HR 管理員',
    description: '可存取所有文件 (L1-L3)',
  },
];

/**
 * NovaLogo — small inline SVG used as a logo placeholder. Rendered as a
 * rounded square containing a stylised "N". Kept inline so the page has no
 * extra asset dependencies.
 *
 * @returns {JSX.Element}
 */
function NovaLogo() {
  return (
    <div
      aria-hidden="true"
      className="w-12 h-12 rounded-lg bg-gradient-to-br from-indigo-500 to-indigo-700 flex items-center justify-center shadow-lg ring-1 ring-indigo-400/40"
    >
      <svg
        viewBox="0 0 24 24"
        className="w-7 h-7 text-white"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M5 19V5l14 14V5" />
      </svg>
    </div>
  );
}

/**
 * LoginPage — see file-level docstring.
 *
 * @returns {JSX.Element}
 */
export default function LoginPage() {
  const { login } = useAuth();
  const [selectedRole, setSelectedRole] = useState(null);

  const canSubmit = selectedRole !== null;

  const handleSubmit = (event) => {
    event.preventDefault();
    if (!canSubmit) return;
    login(selectedRole);
    // Navigation is owned by App.jsx (reacts to isAuthed flipping true).
  };

  return (
    <div className="min-h-screen w-full bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-slate-100 flex flex-col">
      {/* Top thin brand bar — adds the "real intranet" affordance. */}
      <div className="w-full border-b border-slate-800/80 bg-slate-950/60 backdrop-blur-sm">
        <div className="max-w-6xl mx-auto px-4 py-2 flex items-center justify-between text-[11px] text-slate-400 font-mono">
          <span>NovaTech Internal Portal</span>
          <span>v2.4.1 · Secure Session</span>
        </div>
      </div>

      <main className="flex-1 flex items-center justify-center px-4 py-10">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, ease: 'easeOut' }}
          className="w-full max-w-md"
        >
          {/* Public security-demo notice (visible on the login page only) */}
          <div className="mb-4 rounded-lg border border-amber-400/40 bg-amber-500/10 px-4 py-3 text-xs leading-relaxed text-amber-100">
            <div className="font-semibold text-amber-200 mb-0.5">
              This is a public security demonstration
            </div>
            <p className="text-amber-100/80">
              本網站為企業 RAG 安全性教學展示。所有員工、薪資、身分證等資料均由 Faker
              合成，與真實人物無關。請勿輸入任何真實個資。
            </p>
          </div>

          <div className="bg-slate-900/80 border border-slate-700/70 rounded-xl shadow-2xl shadow-black/40 backdrop-blur-md overflow-hidden">
            {/* Header */}
            <div className="px-7 pt-7 pb-5 border-b border-slate-800/80">
              <div className="flex items-center gap-3">
                <NovaLogo />
                <div className="min-w-0">
                  <h1 className="text-lg font-semibold tracking-wide text-slate-50 truncate">
                    NovaTech Corp 企業內部入口
                  </h1>
                  <p className="text-xs text-slate-400 mt-0.5">
                    員工自助服務系統
                  </p>
                </div>
              </div>
            </div>

            {/* Form */}
            <form onSubmit={handleSubmit} className="px-7 py-6 space-y-5">
              <div>
                <label className="block text-xs font-medium uppercase tracking-wider text-slate-400 mb-3">
                  請選擇身份
                </label>
                <div
                  role="radiogroup"
                  aria-label="請選擇身份"
                  className="space-y-2"
                >
                  {ROLE_OPTIONS.map((opt) => {
                    const isSelected = selectedRole === opt.value;
                    return (
                      <label
                        key={opt.value}
                        className={[
                          'flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors',
                          isSelected
                            ? 'border-indigo-500/80 bg-indigo-500/10'
                            : 'border-slate-700/70 bg-slate-800/40 hover:border-slate-500 hover:bg-slate-800/70',
                        ].join(' ')}
                      >
                        <input
                          type="radio"
                          name="role"
                          value={opt.value}
                          checked={isSelected}
                          onChange={() => setSelectedRole(opt.value)}
                          className="mt-1 h-4 w-4 accent-indigo-500 cursor-pointer"
                        />
                        <div className="min-w-0">
                          <div className="text-sm font-medium text-slate-100">
                            {opt.label}
                          </div>
                          <div className="text-xs text-slate-400 mt-0.5">
                            {opt.description}
                          </div>
                        </div>
                      </label>
                    );
                  })}
                </div>
              </div>

              <button
                type="submit"
                disabled={!canSubmit}
                className={[
                  'w-full py-2.5 rounded-lg text-sm font-medium tracking-wide transition-colors',
                  canSubmit
                    ? 'bg-indigo-600 hover:bg-indigo-500 text-white shadow shadow-indigo-900/40'
                    : 'bg-slate-700/60 text-slate-400 cursor-not-allowed',
                ].join(' ')}
              >
                登入
              </button>

              <p className="text-[11px] leading-relaxed text-slate-500 border-t border-slate-800/70 pt-4">
                本系統僅供 NovaTech 員工使用，所有操作均受監控與記錄。
              </p>
            </form>
          </div>

          {/* Footer caption under the card — also reinforces the corporate look. */}
          <p className="mt-5 text-center text-[11px] text-slate-500 font-mono">
            © NovaTech Corp · Human Resources Information System
          </p>
        </motion.div>
      </main>
    </div>
  );
}
