/**
 * Root application component.
 *
 * Routing:
 *   - Unauthenticated → LoginPage
 *   - Authenticated   → HRAppPage. Demo scenarios (acts 1-4) play out inline
 *                       within HRAppPage; only the SecuritySpectrum is shown
 *                       as a modal overlay because it is a pure visualization
 *                       with no chat interaction.
 *
 * App owns the activeAct state. HRAppPage reads activeAct to set up the
 * scenario (prefill query, expose Act 2 toggle, swap to HE dashboard) and
 * uses onTriggerAct to set / clear it.
 */

import { useState } from 'react';

import { AuthProvider, useAuth } from './contexts/AuthContext.jsx';
import LoginPage from './pages/LoginPage.jsx';
import HRAppPage from './pages/HRAppPage.jsx';
import SpectrumOverlay from './components/overlays/SpectrumOverlay.jsx';

function AuthedShell() {
  const { isAuthed } = useAuth();
  const [activeAct, setActiveAct] = useState(null);

  if (!isAuthed) {
    return <LoginPage />;
  }

  return (
    <>
      <HRAppPage activeAct={activeAct} onTriggerAct={setActiveAct} />
      <SpectrumOverlay
        open={activeAct === 'spectrum'}
        onClose={() => setActiveAct(null)}
      />
    </>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AuthedShell />
    </AuthProvider>
  );
}
