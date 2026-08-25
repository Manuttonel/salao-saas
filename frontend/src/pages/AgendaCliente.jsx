// Página do cliente: escolher salão, serviço, profissional e horário
// livre para agendar, além de ver/cancelar os próprios agendamentos.

import { useEffect, useState } from "react";
import api, { obterUsuarioLogado, extrairMensagemErro } from "../services/api";
import Navbar from "../components/Navbar";

function hojeISO() {
  return new Date().toISOString().slice(0, 10);
}

export default function AgendaCliente() {
  const usuario = obterUsuarioLogado();

  const [saloes, setSaloes] = useState([]);
  const [salaoId, setSalaoId] = useState("");
  const [servicos, setServicos] = useState([]);
  const [servicoId, setServicoId] = useState("");
  const [profissionais, setProfissionais] = useState([]);
  const [profissionalId, setProfissionalId] = useState("");
  const [data, setData] = useState(hojeISO());
  const [horarios, setHorarios] = useState([]);
  const [meusAgendamentos, setMeusAgendamentos] = useState([]);
  const [erro, setErro] = useState("");
  const [mensagem, setMensagem] = useState("");

  useEffect(() => {
    api.get("/saloes/").then(({ data }) => setSaloes(data));
    carregarMeusAgendamentos();
  }, []);

  useEffect(() => {
    if (!salaoId) return;
    api.get(`/saloes/${salaoId}/servicos`).then(({ data }) => setServicos(data));
    api.get(`/saloes/${salaoId}/profissionais`).then(({ data }) => setProfissionais(data));
    setServicoId("");
    setProfissionalId("");
    setHorarios([]);
  }, [salaoId]);

  useEffect(() => {
    if (salaoId && servicoId && profissionalId && data) {
      buscarHorarios();
    } else {
      setHorarios([]);
    }
  }, [salaoId, servicoId, profissionalId, data]);

  async function carregarMeusAgendamentos() {
    try {
      const { data } = await api.get("/agendamentos/");
      setMeusAgendamentos(data);
    } catch (e) {
      // silencioso: cliente pode ainda não ter nenhum agendamento
    }
  }

  async function buscarHorarios() {
    setErro("");
    try {
      const { data: resp } = await api.get("/agendamentos/horarios-disponiveis", {
        params: { salao_id: salaoId, profissional_id: profissionalId, servico_id: servicoId, data },
      });
      setHorarios(resp.horarios);
    } catch (e) {
      setErro(extrairMensagemErro(e));
    }
  }

  async function agendar(horario) {
    setErro("");
    setMensagem("");
    try {
      await api.post("/agendamentos/", {
        salao_id: salaoId,
        profissional_id: profissionalId,
        servico_id: servicoId,
        inicio: horario,
      });
      setMensagem("Agendamento confirmado! Você receberá uma mensagem de confirmação.");
      buscarHorarios();
      carregarMeusAgendamentos();
    } catch (e) {
      setErro(extrairMensagemErro(e));
    }
  }

  async function cancelar(id) {
    try {
      await api.post(`/agendamentos/${id}/cancelar`);
      carregarMeusAgendamentos();
    } catch (e) {
      alert(extrairMensagemErro(e));
    }
  }

  return (
    <div>
      <Navbar usuario={usuario} />
      <div className="max-w-4xl mx-auto px-4 py-8 space-y-8">
        <section className="bg-white border border-gray-200 rounded-xl p-6">
          <h2 className="font-semibold mb-4">Agendar horário</h2>

          <div className="grid sm:grid-cols-2 gap-3 mb-4">
            <select className="border rounded-md px-3 py-2 text-sm" value={salaoId} onChange={(e) => setSalaoId(e.target.value)}>
              <option value="">Escolha o salão</option>
              {saloes.map((s) => <option key={s.id} value={s.id}>{s.nome}</option>)}
            </select>

            <select className="border rounded-md px-3 py-2 text-sm" value={servicoId} onChange={(e) => setServicoId(e.target.value)} disabled={!salaoId}>
              <option value="">Escolha o serviço</option>
              {servicos.map((s) => <option key={s.id} value={s.id}>{s.nome} ({s.duracao_minutos} min)</option>)}
            </select>

            <select className="border rounded-md px-3 py-2 text-sm" value={profissionalId} onChange={(e) => setProfissionalId(e.target.value)} disabled={!salaoId}>
              <option value="">Escolha o profissional</option>
              {profissionais.map((p) => <option key={p.id} value={p.id}>{p.nome}</option>)}
            </select>

            <input type="date" className="border rounded-md px-3 py-2 text-sm" min={hojeISO()}
              value={data} onChange={(e) => setData(e.target.value)} />
          </div>

          {erro && <p className="text-sm text-red-600 mb-2">{erro}</p>}
          {mensagem && <p className="text-sm text-green-600 mb-2">{mensagem}</p>}

          {horarios.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {horarios.map((h) => (
                <button key={h} onClick={() => agendar(h)}
                  className="px-3 py-1.5 rounded-md border border-brand-500 text-brand-700 text-sm hover:bg-brand-50">
                  {new Date(h).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}
                </button>
              ))}
            </div>
          )}
          {salaoId && servicoId && profissionalId && horarios.length === 0 && (
            <p className="text-sm text-gray-400">Nenhum horário livre neste dia.</p>
          )}
        </section>

        <section className="bg-white border border-gray-200 rounded-xl p-6">
          <h2 className="font-semibold mb-4">Meus agendamentos</h2>
          <ul className="divide-y divide-gray-100">
            {meusAgendamentos.map((a) => (
              <li key={a.id} className="py-2 flex justify-between items-center text-sm">
                <span>
                  {new Date(a.inicio).toLocaleString("pt-BR")} — {a.servico_nome} com {a.profissional_nome}
                  <span className="ml-2 text-xs text-gray-400">[{a.status}]</span>
                </span>
                {a.status !== "cancelado" && (
                  <button onClick={() => cancelar(a.id)} className="text-red-600 hover:underline text-xs">
                    Cancelar
                  </button>
                )}
              </li>
            ))}
            {meusAgendamentos.length === 0 && <p className="text-sm text-gray-400 py-2">Nenhum agendamento ainda.</p>}
          </ul>
        </section>
      </div>
    </div>
  );
}
