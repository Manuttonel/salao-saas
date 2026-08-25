// Componente "guarda de rota": só renderiza a página filha se houver um
// usuário logado com um dos papéis permitidos. Caso contrário, redireciona
// para /login. Usado em App.jsx para proteger cada dashboard.

import { Navigate } from "react-router-dom";
import { obterUsuarioLogado } from "../services/api";

export default function ProtectedRoute({ papeisPermitidos, children }) {
  const usuario = obterUsuarioLogado();

  if (!usuario) {
    return <Navigate to="/login" replace />;
  }

  if (papeisPermitidos && !papeisPermitidos.includes(usuario.papel)) {
    return <Navigate to="/login" replace />;
  }

  return children;
}
