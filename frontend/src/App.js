import "./App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "./components/ui/sonner";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { ErrorBoundary } from "./components/ErrorBoundary";
import Landing from "./pages/Landing";
import Submit from "./pages/Submit";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import SubmissionDetail from "./pages/SubmissionDetail";
import Settings from "./pages/Settings";
import NotFound from "./pages/NotFound";

const Protected = ({ children }) => {
  const { email, loading } = useAuth();
  if (loading) return <div className="min-h-screen flex items-center justify-center text-[#0F2C4C]">Loading…</div>;
  if (!email) return <Navigate to="/insights/login" replace />;
  return children;
};

function App() {
  return (
    <div className="App">
      <ErrorBoundary>
        <AuthProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<Landing />} />
              <Route path="/submit" element={<Submit />} />
              <Route path="/insights/login" element={<Login />} />
              <Route path="/insights" element={<Protected><Dashboard /></Protected>} />
              <Route path="/insights/settings" element={<Protected><Settings /></Protected>} />
              <Route path="/insights/submission/:id" element={<Protected><SubmissionDetail /></Protected>} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </BrowserRouter>
          <Toaster position="top-right" richColors />
        </AuthProvider>
      </ErrorBoundary>
    </div>
  );
}

export default App;
