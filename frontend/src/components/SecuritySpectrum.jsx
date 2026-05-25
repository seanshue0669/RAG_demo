/**
 * SecuritySpectrum — horizontal visualisation summarising the four defenses
 * showcased across Acts 1–4.
 *
 * Renders a left-to-right gradient bar going from "脆弱" (red) to "安全"
 * (green). Four numbered markers sit along the spectrum, each representing
 * one of the demo's security postures:
 *
 *   1. 無存取控制              (far left, red)         — Act 2 attack baseline.
 *   2. Metadata filter         (middle-left, yellow)  — Act 2 defense.
 *   3. Prompt guard / 輸出過濾  (middle-right, lime)   — Act 3 defense, partial.
 *   4. 同態加密儲存 + Access    (far right, green)     — Act 4 defense.
 *
 * Beneath each marker is a one-sentence Traditional Chinese rationale.
 * Tailwind classes only; framer-motion is used for a subtle fade-in.
 *
 * @returns {JSX.Element}
 */

import { motion } from 'framer-motion';

const SPECTRUM_MARKERS = [
  {
    id: 'no-acl',
    position: 6,
    title: '無存取控制',
    subtitle: 'Act 2 攻擊基線',
    description: '任何角色都能檢索 L1～L3 全部文件，個資直接外洩。',
    dotCls: 'bg-red-500 border-red-300',
    textCls: 'text-red-300',
  },
  {
    id: 'metadata-filter',
    position: 35,
    title: 'Metadata Filter',
    subtitle: 'Act 2 防禦',
    description: '依角色 security_level 過濾，限制檢索結果不超過授權等級。',
    dotCls: 'bg-yellow-400 border-yellow-200',
    textCls: 'text-yellow-300',
  },
  {
    id: 'prompt-guard',
    position: 65,
    title: 'Prompt Guard / 輸出過濾',
    subtitle: 'Act 3 防禦（部分）',
    description: '偵測 prompt injection 與敏感輸出，但仍依賴啟發式，可能繞過。',
    dotCls: 'bg-lime-400 border-lime-200',
    textCls: 'text-lime-300',
  },
  {
    id: 'he-search',
    position: 94,
    title: '同態加密儲存 + Access Control',
    subtitle: 'Act 4 防禦',
    description: '密文檢索全程不解密，即使儲存層被入侵，原文與向量都無法還原。',
    dotCls: 'bg-green-500 border-green-300',
    textCls: 'text-green-300',
  },
];

export default function SecuritySpectrum() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: 'easeOut' }}
      className="w-full bg-gray-900/40 border border-gray-700/40 rounded-lg p-4"
    >
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-100 tracking-wide">
          安全性光譜
        </h3>
        <span className="text-[11px] text-gray-500">
          從「脆弱」走向「安全」的防禦演進
        </span>
      </div>

      {/* Spectrum bar */}
      <div className="relative pt-6 pb-2">
        {/* Gradient track */}
        <div className="relative h-2.5 w-full rounded-full overflow-hidden bg-gradient-to-r from-red-500 via-yellow-400 via-lime-400 to-green-500 shadow-inner" />

        {/* End labels */}
        <div className="flex justify-between mt-1 text-[11px] font-mono">
          <span className="text-red-300">脆弱</span>
          <span className="text-green-300">安全</span>
        </div>

        {/* Markers */}
        {SPECTRUM_MARKERS.map((marker, idx) => (
          <div
            key={marker.id}
            className="absolute top-5 -translate-x-1/2"
            style={{ left: `${marker.position}%` }}
            aria-label={`${idx + 1}. ${marker.title}`}
          >
            <div
              className={`w-4 h-4 rounded-full border-2 ${marker.dotCls} shadow ring-2 ring-gray-900/60`}
            />
          </div>
        ))}
      </div>

      {/* Marker captions */}
      <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {SPECTRUM_MARKERS.map((marker, idx) => (
          <motion.div
            key={marker.id}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: 0.1 + idx * 0.08 }}
            className="p-3 rounded-md border border-gray-700/50 bg-gray-900/50"
          >
            <div className="flex items-baseline gap-2 mb-1">
              <span
                className={`text-xs font-mono ${marker.textCls}`}
                aria-hidden="true"
              >
                {idx + 1}.
              </span>
              <span className={`text-sm font-semibold ${marker.textCls}`}>
                {marker.title}
              </span>
            </div>
            <div className="text-[11px] text-gray-500 mb-1 italic">
              {marker.subtitle}
            </div>
            <p className="text-xs text-gray-300 leading-relaxed">
              {marker.description}
            </p>
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
}
