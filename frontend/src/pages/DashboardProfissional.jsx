// Painel do profissional: mostra a própria agenda e permite marcar
// períodos como indisponíveis (folga, almoço etc.) e cancelar
// agendamentos.

import { useEffect, useState } from "react";
import api, { obterUsuarioLogado, extrairMensagemErro } from "../services/api";
import Navbar from "../components/Navbar";

export default function DashboardProfissional() {
  const usuario = obterUsuarioLogado();
  const [agendamentos, setAgendamentos] = useState([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");
  const [formIndisponibilidade, setFormIndisponibilidade] = useState({
    inicio: "",
    fim: "",
    motivo: "",
  });
  const [mensagem, setMensagem] = useState("");

  useEffect(() => {
    carregarAgendamentos();
  }, []);

  async function carregarAgendamentos() {
    setCarregando(true);
    try {
      const { data } = await api.get("/agendamentos/");
      setAgendamentos(data);
    } catch (e) {
      setErro(extrairMensagemErro(e));
    } finally {
      setCarregando(false);
    }
  }

  async function cancelar(id) {
    try {
      await api.post(`/agendamentos/${id}/cancelar`);
      await carregarAgendamentos();
    } catch (e) {
      alert(extrairMensagemErro(e));
    }
  }

  async function marcarIndisponibilidade(e) {
    e.preventDefault();
    setErro("");
    setMensagem("");
    try {
      await api.post(`/saloes/profissionais/${usuario.profissional_id}/indisponibilidades`, formIndisponibilidade);
      setMensagem("Período marcado como indisponível.");
      setFormIndisponibilidade({ inicio: "", fim: "", motivo: "" });
    } catch (e2) {
      setErro(extrairMensagemErro(e2));
    }
  }

  return (
    <div>
      <Navbar usuario={usuario} />
      <div className="max-w-4xl mx-auto px-4 py-8 space-y-8">
        <section className="bg-white border border-gray-200 rounded-xl p-6">
          <h2 className="font-semibold mb-4">Minha agenda</h2>
          {carregando ? (
            <p className="text-sm text-gray-500">Carregando...</p>
          ) : (
            <ul className="divide-y divide-gray-100">
              {agendamentos.map((a) => (
                <li key={a.id} className="py-2 flex justify-between items-center text-sm">
                  <span>
                    {new Date(a.inicio).toLocaleString("pt-BR")} — {a.cliente_nome} ({a.servico_nome})
                    <span className="ml-2 text-xs text-gray-400">[{a.status}]</span>
                  </span>
                  {a.status !== "cancelado" && (
                    <button onClick={() => cancelar(a.id)} className="text-red-600 hover:underline text-xs">
                      Cancelar
                    </button>
                  )}
                </li>
              ))}
              {agendamentos.length === 0 && <p className="text-sm text-gray-400 py-2">Nenhum agendamento.</p>}
            </ul>
          )}
          {erro && <p className="text-sm text-red-600 mt-2">{erro}</p>}
        </section>

        <section className="bg-white border border-gray-200 rounded-xl p-6 max-w-md">
          <h2 className="font-semibold mb-4">Marcar indisponibilidade</h2>
          <form onSubmit={marcarIndisponibilidade} className="space-y-3">
            <label className="text-sm text-gray-600 block">
              Início
              <input required type="datetime-local" className="w-full border rounded-md px-3 py-2 text-sm mt-1"
                value={formIndisponibilidade.inicio}
                onChange={(e) => setFormIndisponibilidade({ ...formIndisponibilidade, inicio: e.target.value })} />
            </label>
            <label className="text-sm text-gray-600 block">
              Fim
              <input required type="datetime-local" className="w-full border rounded-md px-3 py-2 text-sm mt-1"
                value={formIndisponibilidade.fim}
                onChange={(e) => setFormIndisponibilidade({ ...formIndisponibilidade, fim: e.target.value })} />
            </label>
            <input placeholder="Motivo (opcional)" className="w-full border rounded-md px-3 py-2 text-sm"
              value={formIndisponibilidade.motivo}
              onChange={(e) => setFormIndisponibilidade({ ...formIndisponibilidade, motivo: e.target.value })} />
            <button className="bg-brand-600 hover:bg-brand-700 text-white rounded-md py-2 px-4 text-sm">
              Marcar
            </button>
          </form>
          {mensagem && <p className="text-sm text-green-600 mt-2">{mensagem}</p>}
        </section>
      </div>
    </div>
  );
}
