// Barra de navegação simples, mostrada em todas as páginas internas
// (depois do login). Mostra o nome do usuário e um botão de sair.

import { useNavigate } from "react-router-dom";
import { encerrarSessao } from "../services/api";

export default function Navbar({ usuario }) {
  const navigate = useNavigate();

  function sair() {
    encerrarSessao();
    navigate("/login");
  }

  return (
    <header className="bg-white border-b border-gray-200">
      <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
        <span className="font-semibold text-brand-700">Salão SaaS</span>
        <div className="flex items-center gap-4 text-sm">
          <span className="text-gray-600">
            {usuario?.nome} <span className="text-gray-400">({usuario?.papel})</span>
          </span>
          <button
            onClick={sair}
            className="px-3 py-1.5 rounded-md border border-gray-300 hover:bg-gray-100 transition"
          >
            Sair
          </button>
        </div>
      </div>
    </header>
  );
}
