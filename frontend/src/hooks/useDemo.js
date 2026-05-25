/**
 * useDemo — React hook wrapping POST /api/demo/{act}.
 *
 * The scripted demo endpoints accept no body parameters; each act has fixed
 * server-side defaults for query, role, and filter state. This hook simply
 * dispatches the POST for the requested act identifier and exposes the
 * standard loading / error / result tuple.
 *
 * Backend contract:
 *   POST /api/demo/{act}
 *   body: {}
 *   resp: { act, query, user_role, result, narration }
 *
 * Errors thrown by axios are normalised into a string and exposed via
 * `error`. The underlying promise rejection is re-thrown so callers may
 * still `await runDemo(...)` inside a try/catch when needed.
 */

import { useState } from 'react';
import axios from 'axios';
import { API_BASE_URL } from '../config.js';

/**
 * @typedef {'act1'|'act2'|'act3'|'act4'} ActId
 */

/**
 * @typedef {object} DemoResult
 * @property {string} act
 * @property {string} query
 * @property {string} user_role
 * @property {object} result
 * @property {string} narration
 */

/**
 * @returns {{
 *   runDemo: (act: ActId) => Promise<DemoResult>,
 *   loading: boolean,
 *   error: string | null,
 *   result: DemoResult | null,
 *   reset: () => void,
 * }}
 */
export function useDemo() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  async function runDemo(act) {
    setLoading(true);
    setError(null);
    try {
      const { data } = await axios.post(`${API_BASE_URL}/api/demo/${act}`, {});
      setResult(data);
      return data;
    } catch (e) {
      const msg = e.response?.data?.detail || e.message || 'Unknown error';
      setError(msg);
      throw e;
    } finally {
      setLoading(false);
    }
  }

  function reset() {
    setResult(null);
    setError(null);
  }

  return { runDemo, loading, error, result, reset };
}

export default useDemo;
