// Painel do profissional (quem tem login): vê a própria agenda e bloqueia
// períodos em que não pode atender (folga, almoço, médico...).

import { useCallback, useEffect, useState } from "react";
import api, { obterUsuarioLogado, extrairMensagemErro } from "../services/api";
import Navbar from "../components/Navbar";
import { STATUS, formatarDataHora, formatarHora, formatarDiaCurto } from "../services/formatar";

export default function DashboardProfissional() {
  const usuario = obterUsuarioLogado();
  const [agendamentos, setAgendamentos] = useState([]);
  const [bloqueios, setBloqueios] = useState([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");
  const [mensagem, setMensagem] = useState("");
  const [form, setForm] = useState({ inicio: "", fim: "", motivo: "" });

  const carregar = useCallback(async () => {
    try {
      const [ag, bl] = await Promise.all([
        api.get("/agendamentos/", { params: { status: "pendente,confirmado,concluido", futuros: 1 } }),
        api.get(`/saloes/profissionais/${usuario.profissional_id}/indisponibilidades`),
      ]);
      setAgendamentos(ag.data);
      setBloqueios(bl.data);
    } catch (e) {
      setErro(extrairMensagemErro(e));
    } finally {
      setCarregando(false);
    }
  }, [usuario.profissional_id]);

  useEffect(() => { carregar(); }, [carregar]);

  async function acao(id, nome) {
    try {
      await api.post(`/agendamentos/${id}/${nome}`);
      carregar();
    } catch (e) {
      alert(extrairMensagemErro(e));
    }
  }

  async function bloquear(e) {
    e.preventDefault(); setErro(""); setMensagem("");
    try {
      await api.post(`/saloes/profissionais/${usuario.profissional_id}/indisponibilidades`, form);
      setMensagem("Período bloqueado.");
      setForm({ inicio: "", fim: "", motivo: "" });
      carregar();
    } catch (err) {
      setErro(extrairMensagemErro(err));
    }
  }

  async function desbloquear(id) {
    await api.delete(`/saloes/indisponibilidades/${id}`);
    carregar();
  }

  return (
    <div>
      <Navbar usuario={usuario} titulo="Minha agenda" />
      <main className="mx-auto grid max-w-5xl gap-6 px-4 py-8 lg:grid-cols-[1fr_340px]">
        <section className="card">
          <h2 className="titulo mb-4 text-lg">Próximos atendimentos</h2>
          {carregando ? (
            <p className="text-sm text-muted">Carregando…</p>
          ) : (
            <ul className="divide-y divide-line">
              {agendamentos.map((a) => (
                <li key={a.id} className="flex flex-wrap items-center justify-between gap-3 py-3 text-sm">
                  <div>
                    <p className="font-medium">{formatarDataHora(a.inicio)} · {a.cliente_nome}</p>
                    <p className="text-xs text-muted">{a.servico_nome} ({a.duracao_minutos} min)</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={STATUS[a.status].classe}>{STATUS[a.status].texto}</span>
                    {a.status === "confirmado" && <button className="btn-outline btn-sm" onClick={() => acao(a.id, "concluir")}>Concluir</button>}
                  </div>
                </li>
              ))}
              {agendamentos.length === 0 && <li className="py-3 text-sm text-muted">Nenhum atendimento futuro.</li>}
            </ul>
          )}
          {erro && <p role="alert" className="mt-3 text-sm text-[rgb(var(--bad-fg))]">{erro}</p>}
        </section>

        <section className="card h-fit">
          <h2 className="titulo mb-4 text-lg">Bloquear horário</h2>
          <form onSubmit={bloquear} className="space-y-3">
            <div><label className="rotulo" htmlFor="b-ini">Início</label>
              <input id="b-ini" required type="datetime-local" className="input" value={form.inicio} onChange={(e) => setForm({ ...form, inicio: e.target.value })} /></div>
            <div><label className="rotulo" htmlFor="b-fim">Fim</label>
              <input id="b-fim" required type="datetime-local" className="input" value={form.fim} onChange={(e) => setForm({ ...form, fim: e.target.value })} /></div>
            <input className="input" placeholder="Motivo (opcional)" value={form.motivo} onChange={(e) => setForm({ ...form, motivo: e.target.value })} />
            <button className="btn-primary w-full">Bloquear</button>
          </form>
          {mensagem && <p role="status" className="mt-2 text-sm text-[rgb(var(--ok-fg))]">{mensagem}</p>}

          {bloqueios.length > 0 && (
            <ul className="mt-5 space-y-2 text-sm">
              {bloqueios.map((b) => (
                <li key={b.id} className="flex items-center justify-between gap-2 rounded-lg border border-line px-3 py-2">
                  <span>{formatarDiaCurto(b.inicio)} {formatarHora(b.inicio)}–{formatarHora(b.fim)}{b.motivo ? ` · ${b.motivo}` : ""}</span>
                  <button className="btn-ghost btn-sm" onClick={() => desbloquear(b.id)} aria-label="Remover bloqueio">✕</button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>
    </div>
  );
}
