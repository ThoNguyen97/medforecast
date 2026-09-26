import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from './store/authStore';
import { ROUTES } from './utils/constants';
import Layout from './components/layout/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Inventory from './pages/Inventory';
import Forecasting from './pages/Forecasting';
import Alerts from './pages/Alerts';
import Epidemiology from './pages/Epidemiology';
import DiseaseCaseDetail from './pages/DiseaseCaseDetail';
import Weather from './pages/Weather';
import Reports from './pages/Reports';
import Settings from './pages/Settings';

// Route yêu cầu đăng nhập
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();

  if (!isAuthenticated) {
    return <Navigate to={ROUTES.LOGIN} replace />;
  }

  return <>{children}</>;
}

// Đã đăng nhập thì không vào lại trang /login
function PublicRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();

  if (isAuthenticated) {
    return <Navigate to={ROUTES.DASHBOARD} replace />;
  }

  return <>{children}</>;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Route công khai */}
        <Route
          path={ROUTES.LOGIN}
          element={
            <PublicRoute>
              <Login />
            </PublicRoute>
          }
        />

        {/* Route cần đăng nhập, bọc trong Layout */}
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          {/* Chuyển hướng mặc định */}
          <Route index element={<Navigate to={ROUTES.DASHBOARD} replace />} />

          {/* Các trang chính */}
          <Route path={ROUTES.DASHBOARD} element={<Dashboard />} />
          <Route path={ROUTES.INVENTORY} element={<Inventory />} />
          <Route path={ROUTES.FORECASTING} element={<Forecasting />} />
          <Route path={ROUTES.ALERTS} element={<Alerts />} />
          <Route path={ROUTES.EPIDEMIOLOGY} element={<Epidemiology />} />
          <Route path="/epidemiology/:caseId" element={<DiseaseCaseDetail />} />
          <Route path={ROUTES.WEATHER} element={<Weather />} />
          <Route path={ROUTES.REPORTS} element={<Reports />} />
          <Route path={ROUTES.SETTINGS} element={<Settings />} />
        </Route>

        {/* Route không khớp */}
        <Route path="*" element={<Navigate to={ROUTES.DASHBOARD} replace />} />
      </Routes>
    </BrowserRouter>
  );
}
