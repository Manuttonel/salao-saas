// Define todas as rotas da aplicação e protege cada dashboard com o
// papel de usuário correto (ProtectedRoute).

import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import Login from "./pages/Login";
import DashboardDono from "./pages/DashboardDono";
import DashboardProfissional from "./pages/DashboardProfissional";
import AgendaCliente from "./pages/AgendaCliente";
import Assinatura from "./pages/Assinatura";
import ProtectedRoute from "./components/ProtectedRoute";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />

        <Route
          path="/dashboard"
          element={
            <ProtectedRoute papeisPermitidos={["dono"]}>
              <DashboardDono />
            </ProtectedRoute>
          }
        />

        <Route
          path="/profissional"
          element={
            <ProtectedRoute papeisPermitidos={["profissional"]}>
              <DashboardProfissional />
            </ProtectedRoute>
          }
        />

        <Route
          path="/agenda"
          element={
            <ProtectedRoute papeisPermitidos={["cliente"]}>
              <AgendaCliente />
            </ProtectedRoute>
          }
        />

        <Route
          path="/assinatura"
          element={
            <ProtectedRoute papeisPermitidos={["dono"]}>
              <Assinatura />
            </ProtectedRoute>
          }
        />

        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
