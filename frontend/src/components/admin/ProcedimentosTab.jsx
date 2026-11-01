// Aba "Procedimentos": cadastro do que o salão faz (cabelo, unhas, estética,
// barba, outros), com o TEMPO de cada um — é essa duração que reserva o
// intervalo certo na agenda.
//
// "Marcar Avaliação" é um procedimento especial que todo salão já tem: o
// administrador só escolhe quanto tempo ele dura (normalmente bem curto).

import { useState } from "react";
import api, { extrairMensagemErro } from "../../services/api";
import { CATEGORIAS, agruparPorCategoria, moeda } from "../../services/formatar";

const DURACOES_RAPIDAS = [15, 30, 45, 60, 90, 120];
const VAZIO = { nome: "", categoria: "cabelo", duracao_minutos: 30, preco: "", descricao: "" };

function CartaoAvaliacao({ avaliacao, recarregar }) {
  const [duracao, setDuracao] = useState(avaliacao.duracao_minutos);
  const [ativo, setAtivo] = useState(avaliacao.ativo);
  const [msg, setMsg] = useState("");
  const [erro, setErro] = useState("");

  async function salvar() {
    setErro(""); setMsg("");
    try {
      await api.put(`/saloes/servicos/${avaliacao.id}`, { duracao_minutos: duracao, ativo });
      setMsg("Salvo."); recarregar();
    } catch (e) {
      setErro(extrairMensagemErro(e));
    }
  }

  return (
    <section className="card border-2 !border-dashed !border-accent/60">
      <h2 className="titulo text-lg text-brand-600">{avaliacao.nome}</h2>
      <p className="mb-4 text-sm text-muted">Horário curto para o cliente conhecer o salão e avaliar o que precisa. Você define quanto tempo ele dura.</p>
      <div className="flex flex-wrap items-end gap-4">
        <div>
          <label className="rotulo" htmlFor="dur-aval">Duração (minutos)</label>
          <input id="dur-aval" type="number" min={5} max={120} step={5} className="input !w-28" value={duracao}
            onChange={(e) => setDuracao(Number(e.target.value))} />
        </div>
        <label className="flex items-center gap-2 pb-2 text-sm">
          <input type="checkbox" checked={ativo} onChange={(e) => setAtivo(e.target.checked)} /> Oferecer aos clientes
        </label>
        <button className="btn-primary" onClick={salvar}>Salvar</button>
        {msg && <span role="status" className="pb-2 text-sm text-[rgb(var(--ok-fg))]">{msg}</span>}
      </div>
      {erro && <p role="alert" className="mt-2 text-sm text-[rgb(var(--bad-fg))]">{erro}</p>}
    </section>
  );
}

export default function ProcedimentosTab({ salaoId, servicos, recarregar }) {
  const [form, setForm] = useState(VAZIO);
  const [editandoId, setEditandoId] = useState(null);
  const [erro, setErro] = useState("");

  const avaliacao = servicos.find((s) => s.eh_avaliacao);
  const grupos = agruparPorCategoria(servicos);

  function editar(servico) {
    setEditandoId(servico.id);
    setForm({
      nome: servico.nome, categoria: servico.categoria, duracao_minutos: servico.duracao_minutos,
      preco: servico.preco, descricao: servico.descricao || "",
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function limpar() {
    setEditandoId(null); setForm(VAZIO); setErro("");
  }

  async function salvar(e) {
    e.preventDefault(); setErro("");
    try {
      if (editandoId) await api.put(`/saloes/servicos/${editandoId}`, form);
      else await api.post(`/saloes/${salaoId}/servicos`, form);
      limpar(); recarregar();
    } catch (err) {
      setErro(extrairMensagemErro(err));
    }
  }

  async function remover(servico) {
    if (!confirm(`Remover "${servico.nome}"? Atendimentos antigos continuam no histórico.`)) return;
    try {
      await api.delete(`/saloes/servicos/${servico.id}`);
      if (editandoId === servico.id) limpar();
      recarregar();
    } catch (err) {
      alert(extrairMensagemErro(err));
    }
  }

  return (
    <div className="space-y-6">
      {avaliacao && <CartaoAvaliacao key={`${avaliacao.id}-${avaliacao.duracao_minutos}`} avaliacao={avaliacao} recarregar={recarregar} />}

      <section className="card">
        <h2 className="titulo mb-4 text-lg">{editandoId ? "Editar procedimento" : "Novo procedimento"}</h2>
        <form onSubmit={salvar} className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className="rotulo" htmlFor="p-nome">Nome</label>
            <input id="p-nome" required className="input" placeholder="Ex.: Escova progressiva" maxLength={120}
              value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} />
          </div>
          <div>
            <label className="rotulo" htmlFor="p-cat">Categoria</label>
            <select id="p-cat" className="input" value={form.categoria} onChange={(e) => setForm({ ...form, categoria: e.target.value })}>
              {CATEGORIAS.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}
            </select>
          </div>
          <div>
            <label className="rotulo" htmlFor="p-dur">Quanto tempo leva? (minutos)</label>
            <input id="p-dur" required type="number" min={5} max={600} step={5} className="input"
              value={form.duracao_minutos} onChange={(e) => setForm({ ...form, duracao_minutos: Number(e.target.value) })} />
            <div className="mt-2 flex flex-wrap gap-1.5">
              {DURACOES_RAPIDAS.map((min) => (
                <button type="button" key={min} className={form.duracao_minutos === min ? "chip-on !py-1 !text-xs" : "chip !py-1 !text-xs"}
                  onClick={() => setForm({ ...form, duracao_minutos: min })}>{min} min</button>
              ))}
            </div>
          </div>
          <div>
            <label className="rotulo" htmlFor="p-preco">Preço (R$)</label>
            <input id="p-preco" required type="number" min={0} step="0.01" className="input"
              value={form.preco} onChange={(e) => setForm({ ...form, preco: e.target.value })} />
          </div>
          <div className="sm:col-span-2">
            <label className="rotulo" htmlFor="p-desc">Descrição (opcional)</label>
            <input id="p-desc" className="input" maxLength={300} placeholder="O cliente vê isto ao escolher"
              value={form.descricao} onChange={(e) => setForm({ ...form, descricao: e.target.value })} />
          </div>
          {erro && <p role="alert" className="text-sm text-[rgb(var(--bad-fg))] sm:col-span-2">{erro}</p>}
          <div className="flex gap-2 sm:col-span-2">
            <button className="btn-primary">{editandoId ? "Salvar alterações" : "Adicionar procedimento"}</button>
            {editandoId && <button type="button" className="btn-outline" onClick={limpar}>Cancelar edição</button>}
          </div>
        </form>
      </section>

      {grupos.map((grupo) => (
        <section key={grupo.id} className="card">
          <h3 className="titulo mb-2 text-base">{grupo.nome}</h3>
          <ul className="divide-y divide-line">
            {grupo.itens.map((s) => (
              <li key={s.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                <div>
                  <p className="font-medium">{s.nome}</p>
                  <p className="text-xs text-muted">{s.duracao_minutos} min · {moeda(s.preco)}{s.descricao ? ` · ${s.descricao}` : ""}</p>
                </div>
                <div className="flex gap-1">
                  <button className="btn-outline btn-sm" onClick={() => editar(s)}>Editar</button>
                  <button className="btn-ghost btn-sm text-[rgb(var(--bad-fg))]" onClick={() => remover(s)}>Remover</button>
                </div>
              </li>
            ))}
          </ul>
        </section>
      ))}
      {grupos.length === 0 && <div className="card text-center text-sm text-muted">Nenhum procedimento cadastrado ainda. Adicione o primeiro acima.</div>}
    </div>
  );
}
