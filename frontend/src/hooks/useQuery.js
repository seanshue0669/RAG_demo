/**
 * useQuery — React hook wrapping POST /api/query.
 *
 * Encapsulates the loading / error / result state for a single user-driven
 * RAG query. Callers invoke `sendQuery({...})` with whatever pipeline
 * parameters they need; the hook returns the parsed response payload and
 * stores it in state so the UI can render it without manually wiring
 * additional `useState` hooks.
 *
 * The backend contract is:
 *   POST /api/query
 *   body: { query, user_role, use_filter, gen_mode, top_k, defense_mode }
 *   resp: { answer, retrieved_docs[], filter_applied, user_role, gen_mode_used,
 *           defense_actions? }
 *
 * Errors thrown by axios are normalised into a string and exposed via
 * `error`. The original promise rejection is still re-thrown so callers may
 * await `sendQuery(...)` inside a try/catch when needed.
 */

import { useState } from 'react';
import axios from 'axios';
import { API_BASE_URL } from '../config.js';

/**
 * @typedef {object} QueryParams
 * @property {string} query - The user's question.
 * @property {'employee'|'manager'|'hr_admin'} user_role - Caller's role.
 * @property {boolean} [use_filter=true] - Whether to apply security filter.
 * @property {'llm'|'scripted'} [gen_mode='llm'] - Generation backend.
 * @property {number} [top_k=5] - Number of documents to retrieve.
 * @property {boolean} [defense_mode=false] - Whether to enable prompt-injection
 *   defenses (Act 3 only). When true the backend is expected to sanitise
 *   retrieved documents and/or harden the system prompt.
 */

/**
 * @typedef {object} RetrievedDoc
 * @property {string} doc_id
 * @property {string} text
 * @property {number} security_level
 * @property {number} similarity
 * @property {string} [doc_type]
 * @property {string} [department]
 */

/**
 * @typedef {object} QueryResult
 * @property {string} answer
 * @property {RetrievedDoc[]} retrieved_docs
 * @property {boolean} filter_applied
 * @property {string} user_role
 * @property {string} gen_mode_used
 */

/**
 * @returns {{
 *   sendQuery: (params: QueryParams) => Promise<QueryResult>,
 *   loading: boolean,
 *   error: string | null,
 *   result: QueryResult | null,
 *   reset: () => void,
 * }}
 */
export function useQuery() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  async function sendQuery({
    query,
    user_role,
    use_filter = true,
    gen_mode = 'llm',
    top_k = 5,
    defense_mode = false,
  }) {
    setLoading(true);
    setError(null);
    try {
      const { data } = await axios.post(`${API_BASE_URL}/api/query`, {
        query,
        user_role,
        use_filter,
        gen_mode,
        top_k,
        defense_mode,
      });
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

  return { sendQuery, loading, error, result, reset };
}

export default useQuery;
