/**
 * SpectrumOverlay — modal wrapping the SecuritySpectrum visualisation.
 *
 * Surfaced secretly via the footer link 「安全等級總覽」. Pure presentational
 * overlay: no API calls, no internal demo state. It simply renders the existing
 * <SecuritySpectrum /> component inside a centered modal with a short
 * Traditional Chinese footnote describing the layered-defense framing.
 *
 * Behaviour:
 *   - Closes via the [X] button, backdrop click, or the ESC key.
 *   - Uses framer-motion for fade transitions; Tailwind for layout.
 *
 * Props:
 *   @param {object} props
 *   @param {boolean} props.open    Whether the overlay is visible.
 *   @param {() => void} props.onClose  Invoked when the user dismisses the modal.
 *   @returns {JSX.Element|null}
 */

import { useEffect } from 'react';
import { AnimatePresence, motion } from 'framer-motion';

import SecuritySpectrum from '../SecuritySpectrum.jsx';

export default function SpectrumOverlay({ open, onClose }) {
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
          key="spectrum-backdrop"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          onClick={onClose}
        >
          <motion.div
            key="spectrum-modal"
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
                安全等級總覽
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

            {/* Body — SecuritySpectrum */}
            <div className="px-6 py-5">
              <SecuritySpectrum />
            </div>

            {/* Footer narration */}
            <div className="px-6 pb-5">
              <div className="rounded-lg bg-gray-800/80 border border-gray-700 px-4 py-3">
                <p className="text-xs uppercase tracking-wider text-gray-500 mb-1">
                  說明
                </p>
                <p className="text-sm text-gray-200 leading-relaxed">
                  本系統採用多層防禦設計。從左至右，安全強度由脆弱遞增至強健。
                </p>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
