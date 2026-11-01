// Barra de topo das páginas internas: marca, nome do usuário, seletor de
// tema e botão de sair.

import { useNavigate } from "react-router-dom";
import { encerrarSessao } from "../services/api";
import SeletorTema from "./SeletorTema";

const ROTULO_PAPEL = {
  dono: "Dono",
  administrador: "Administrador",
  profissional: "Profissional",
  cliente: "Cliente",
};

export default function Navbar({ usuario, titulo }) {
  const navigate = useNavigate();

  function sair() {
    encerrarSessao();
    navigate("/login");
  }

  return (
    <header className="barra-topo sticky top-0 z-20">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3">
        <div className="min-w-0">
          <span className="titulo block truncate text-lg text-brand-600">{titulo || "Salão SaaS"}</span>
        </div>

        <div className="flex items-center gap-2 text-sm sm:gap-3">
          <span className="hidden text-right leading-tight sm:block">
            <span className="block font-medium text-ink">{usuario?.nome}</span>
            <span className="block text-xs text-muted">{ROTULO_PAPEL[usuario?.papel] || usuario?.papel}</span>
          </span>
          <SeletorTema />
          <button onClick={sair} className="btn-outline btn-sm">
            Sair
          </button>
        </div>
      </div>
    </header>
  );
}
