/**
 * AuthContext — lightweight client-side "auth" context for the RAG security
 * demo. There is no real authentication: it simply stores which role the
 * user picked at the login screen and locks it for the rest of the session.
 *
 * Shape:
 *   {
 *     role:      'employee' | 'manager' | 'hr_admin' | null,
 *     isAuthed:  boolean,
 *     login:     (role) => void,
 *     logout:    () => void,
 *   }
 *
 * The selected role is persisted in localStorage under STORAGE_KEY so that a
 * page refresh preserves the demo session. The role is intentionally locked
 * after login (no in-app role switcher) to keep the "real corporate intranet"
 * illusion intact; the only way to change roles is to logout and pick again.
 *
 * Usage:
 *   <AuthProvider>
 *     <App />
 *   </AuthProvider>
 *
 *   const { role, login, logout, isAuthed } = useAuth();
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

const STORAGE_KEY = 'novatech.auth.role';
const VALID_ROLES = ['employee', 'manager', 'hr_admin'];

const AuthContext = createContext(null);

/**
 * Read the persisted role from localStorage. Returns null if there is no
 * value, the value is invalid, or localStorage is unavailable (SSR, private
 * mode, etc.).
 *
 * @returns {('employee'|'manager'|'hr_admin'|null)}
 */
function readPersistedRole() {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored && VALID_ROLES.includes(stored)) {
      return stored;
    }
  } catch (_err) {
    // Ignore — fall through to null.
  }
  return null;
}

/**
 * AuthProvider — wraps children with the auth context. Initialises the role
 * from localStorage so a refresh feels like a persisted session.
 *
 * @param {{ children: React.ReactNode }} props
 * @returns {JSX.Element}
 */
export function AuthProvider({ children }) {
  const [role, setRole] = useState(() => readPersistedRole());

  // Keep localStorage in sync with the in-memory role.
  useEffect(() => {
    try {
      if (role) {
        window.localStorage.setItem(STORAGE_KEY, role);
      } else {
        window.localStorage.removeItem(STORAGE_KEY);
      }
    } catch (_err) {
      // Storage may be unavailable; non-fatal for the demo.
    }
  }, [role]);

  const login = useCallback((nextRole) => {
    if (!VALID_ROLES.includes(nextRole)) {
      // Defensive: ignore invalid roles rather than corrupting state.
      // eslint-disable-next-line no-console
      console.warn(`[AuthContext] Ignoring invalid role: ${nextRole}`);
      return;
    }
    setRole(nextRole);
  }, []);

  const logout = useCallback(() => {
    setRole(null);
  }, []);

  const value = useMemo(
    () => ({
      role,
      isAuthed: role !== null,
      login,
      logout,
    }),
    [role, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/**
 * useAuth — hook to access the auth context. Throws if called outside of an
 * <AuthProvider>, which is the standard React idiom to catch wiring bugs
 * early.
 *
 * @returns {{
 *   role: ('employee'|'manager'|'hr_admin'|null),
 *   isAuthed: boolean,
 *   login: (role: string) => void,
 *   logout: () => void,
 * }}
 */
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (ctx === null) {
    throw new Error('useAuth must be used within an <AuthProvider>');
  }
  return ctx;
}

export default AuthContext;
