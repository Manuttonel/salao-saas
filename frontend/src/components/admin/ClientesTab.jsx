// Aba "Clientes": controle de clientes do salão (CRM).
//
// As fichas nascem de três formas: cadastro manual aqui, cliente que criou
// conta no site, ou cliente que conversou com o bot do WhatsApp (a ficha é
// criada sozinha pelo telefone). Cada ficha guarda observações e o histórico
// de atendimentos.

import { useCallback, useEffect, useState } from "react";
import api, { extrairMensagemErro } from "../../services/api";
import { ORIGENS, STATUS, formatarDataHora, formatarTelefone, iniciais, linkWhatsapp } from "../../services/formatar";

function Ficha({ clienteId, aoAtualizar, aoFechar }) {
  const [ficha, setFicha] = useState(null);
  const [form, setForm] = useState({ nome: "", telefone: "", email: "", observacoes: "" });
  const [msg, setMsg] = useState({ tipo: "", texto: "" });

  useEffect(() => {
    api.get(`/clientes/${clienteId}`).then(({ data }) => {
      setFicha(data);
      setForm({ nome: data.nome || "", telefone: data.telefone || "", email: data.email || "", observacoes: data.observacoes || "" });
    });
  }, [clienteId]);

  async function salvar(e) {
    e.preventDefault();
    try {
      await api.put(`/clientes/${clienteId}`, form);
      setMsg({ tipo: "ok", texto: "Ficha salva." });
      aoAtualizar();
    } catch (err) {
      setMsg({ tipo: "erro", texto: extrairMensagemErro(err) });
    }
  }

  async function arquivar() {
    if (!confirm("Arquivar este cliente? O histórico de atendimentos é mantido.")) return;
    await api.delete(`/clientes/${clienteId}`);
    aoAtualizar(); aoFechar();
  }

  if (!ficha) return <div className="card text-sm text-muted">Carregando…</div>;

  return (
    <section className="card space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="titulo text-lg">{ficha.nome}</h3>
          <p className="text-xs text-muted">Origem: {ORIGENS[ficha.origem] || ficha.origem}</p>
        </div>
        <button className="btn-ghost btn-sm" onClick={aoFechar} aria-label="Fechar ficha">✕</button>
      </div>

      <form onSubmit={salvar} className="grid gap-3 sm:grid-cols-2">
        <div><label className="rotulo" htmlFor="c-nome">Nome</label>
          <input id="c-nome" className="input" required value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} /></div>
        <div><label className="rotulo" htmlFor="c-tel">WhatsApp</label>
          <input id="c-tel" className="input" required value={form.telefone} onChange={(e) => setForm({ ...form, telefone: e.target.value })} /></div>
        <div className="sm:col-span-2"><label className="rotulo" htmlFor="c-email">E-mail</label>
          <input id="c-email" type="email" className="input" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
        <div className="sm:col-span-2"><label className="rotulo" htmlFor="c-obs">Observações do salão</label>
          <textarea id="c-obs" rows={3} className="input" placeholder="Alergias, preferências, produtos que usa…"
            value={form.observacoes} onChange={(e) => setForm({ ...form, observacoes: e.target.value })} /></div>
        <div className="flex flex-wrap items-center gap-2 sm:col-span-2">
          <button className="btn-primary">Salvar ficha</button>
          <a className="btn-outline" href={linkWhatsapp(ficha.telefone || "")} target="_blank" rel="noreferrer">Abrir WhatsApp</a>
          <button type="button" className="btn-ghost text-[rgb(var(--bad-fg))]" onClick={arquivar}>Arquivar</button>
          {msg.texto && <span role="status" className={`text-sm ${msg.tipo === "ok" ? "text-[rgb(var(--ok-fg))]" : "text-[rgb(var(--bad-fg))]"}`}>{msg.texto}</span>}
        </div>
      </form>

      <div>
        <h4 className="rotulo uppercase tracking-wide">Histórico</h4>
        <ul className="divide-y divide-line text-sm">
          {ficha.historico.map((a) => (
            <li key={a.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <span><span>{formatarDataHora(a.inicio)}</span> · {a.servico_nome}</span>
              <span className={STATUS[a.status].classe}>{STATUS[a.status].texto}</span>
            </li>
          ))}
          {ficha.historico.length === 0 && <li className="py-2 text-muted">Sem atendimentos ainda.</li>}
        </ul>
      </div>
    </section>
  );
}

export default function ClientesTab({ salao }) {
  const [clientes, setClientes] = useState([]);
  const [busca, setBusca] = useState("");
  const [aberto, setAberto] = useState(null);
  const [novo, setNovo] = useState(false);
  const [form, setForm] = useState({ nome: "", telefone: "", email: "", observacoes: "" });
  const [erro, setErro] = useState("");

  const carregar = useCallback(async () => {
    const { data } = await api.get("/clientes/", { params: { salao_id: salao.id, busca } });
    setClientes(data);
  }, [salao.id, busca]);

  // Pequeno atraso na busca para não consultar a cada tecla.
  useEffect(() => {
    const espera = setTimeout(() => carregar().catch(() => {}), 250);
    return () => clearTimeout(espera);
  }, [carregar]);

  async function cadastrar(e) {
    e.preventDefault(); setErro("");
    try {
      const { data } = await api.post("/clientes/", { ...form, salao_id: salao.id });
      setForm({ nome: "", telefone: "", email: "", observacoes: "" });
      setNovo(false); carregar(); setAberto(data.id);
    } catch (err) {
      setErro(extrairMensagemErro(err));
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_1fr]">
      <section className="card">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="titulo text-lg">Clientes <span className="text-sm text-muted">({clientes.length})</span></h2>
          <button className="btn-primary btn-sm" onClick={() => setNovo((v) => !v)}>{novo ? "Fechar" : "+ Novo cliente"}</button>
        </div>

        {novo && (
          <form onSubmit={cadastrar} className="mt-4 grid gap-3 rounded-xl border border-line p-4 sm:grid-cols-2">
            <input required className="input" placeholder="Nome" value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} />
            <input required className="input" placeholder="WhatsApp com DDD" value={form.telefone} onChange={(e) => setForm({ ...form, telefone: e.target.value })} />
            <input className="input sm:col-span-2" type="email" placeholder="E-mail (opcional)" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            <textarea className="input sm:col-span-2" rows={2} placeholder="Observações (opcional)" value={form.observacoes} onChange={(e) => setForm({ ...form, observacoes: e.target.value })} />
            {erro && <p role="alert" className="text-sm text-[rgb(var(--bad-fg))] sm:col-span-2">{erro}</p>}
            <button className="btn-primary sm:col-span-2">Cadastrar</button>
          </form>
        )}

        <input className="input mt-4" type="search" placeholder="Buscar por nome, telefone ou e-mail…" aria-label="Buscar clientes"
          value={busca} onChange={(e) => setBusca(e.target.value)} />

        <ul className="mt-3 divide-y divide-line">
          {clientes.map((c) => (
            <li key={c.id}>
              <button onClick={() => setAberto(c.id)}
                className={`flex w-full items-center gap-3 rounded-lg px-2 py-3 text-left transition hover:bg-card2 ${aberto === c.id ? "bg-brand-50" : ""}`}>
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-100 text-xs font-semibold text-brand-700">{iniciais(c.nome)}</span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">{c.nome}</span>
                  <span className="block text-xs text-muted">{formatarTelefone(c.telefone)}</span>
                </span>
                <span className="text-right text-xs text-muted">
                  <span className="block">{c.total_atendimentos} atend.</span>
                  <span className="badge-info mt-0.5">{ORIGENS[c.origem] || c.origem}</span>
                </span>
              </button>
            </li>
          ))}
          {clientes.length === 0 && <li className="py-6 text-center text-sm text-muted">Nenhum cliente encontrado.</li>}
        </ul>
      </section>

      {aberto ? (
        <Ficha key={aberto} clienteId={aberto} aoAtualizar={carregar} aoFechar={() => setAberto(null)} />
      ) : (
        <div className="card hidden items-center justify-center text-sm text-muted lg:flex">Selecione um cliente para ver a ficha e o histórico.</div>
      )}
    </div>
  );
}
