// Aba "Equipe": quem atende (profissionais) e quem administra o salão.
//
// - Profissional: basta o nome. O login (e-mail + senha provisória) é
//   opcional, só para quem quer ver a própria agenda.
// - Administrador: usuário extra com acesso ao painel (solicitações, agenda,
//   clientes, procedimentos). Só o DONO cria e remove administradores.

import { useCallback, useEffect, useState } from "react";
import api, { extrairMensagemErro } from "../../services/api";

function Secao({ titulo, descricao, children }) {
  return (
    <section className="card">
      <h2 className="titulo text-lg">{titulo}</h2>
      <p className="mb-4 text-sm text-muted">{descricao}</p>
      {children}
    </section>
  );
}

function Profissionais({ salaoId, profissionais, recarregar }) {
  const VAZIO = { nome: "", especialidade: "", com_login: false, email: "", telefone: "", senha_provisoria: "" };
  const [form, setForm] = useState(VAZIO);
  const [erro, setErro] = useState("");

  async function adicionar(e) {
    e.preventDefault(); setErro("");
    const { com_login: comLogin, ...dados } = form;
    if (!comLogin) { delete dados.email; delete dados.telefone; delete dados.senha_provisoria; }
    try {
      await api.post(`/saloes/${salaoId}/profissionais`, dados);
      setForm(VAZIO); recarregar();
    } catch (err) {
      setErro(extrairMensagemErro(err));
    }
  }

  async function remover(p) {
    if (!confirm(`Remover ${p.nome} da equipe? Os horários já marcados continuam no histórico.`)) return;
    try {
      await api.put(`/saloes/profissionais/${p.id}`, { ativo: false });
      recarregar();
    } catch (err) {
      alert(extrairMensagemErro(err));
    }
  }

  return (
    <Secao titulo="Profissionais" descricao="Quem atende os clientes. Cada um tem a própria agenda de horários.">
      <ul className="mb-5 divide-y divide-line">
        {profissionais.map((p) => (
          <li key={p.id} className="flex items-center justify-between gap-3 py-3 text-sm">
            <span>
              <span className="font-medium">{p.nome}</span>
              {p.especialidade && <span className="text-muted"> — {p.especialidade}</span>}
              {p.tem_login && <span className="badge-info ml-2">com login</span>}
            </span>
            {profissionais.length > 1 && <button className="btn-ghost btn-sm text-[rgb(var(--bad-fg))]" onClick={() => remover(p)}>Remover</button>}
          </li>
        ))}
      </ul>

      <form onSubmit={adicionar} className="grid gap-3 sm:grid-cols-2">
        <input required className="input" placeholder="Nome" value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} />
        <input className="input" placeholder="Especialidade (opcional)" value={form.especialidade} onChange={(e) => setForm({ ...form, especialidade: e.target.value })} />
        <label className="flex items-center gap-2 text-sm sm:col-span-2">
          <input type="checkbox" checked={form.com_login} onChange={(e) => setForm({ ...form, com_login: e.target.checked })} />
          Dar acesso ao sistema (login) para ver a própria agenda
        </label>
        {form.com_login && (
          <>
            <input required type="email" className="input" placeholder="E-mail" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            <input required className="input" placeholder="WhatsApp" value={form.telefone} onChange={(e) => setForm({ ...form, telefone: e.target.value })} />
            <input required type="password" minLength={6} className="input sm:col-span-2" placeholder="Senha provisória" value={form.senha_provisoria} onChange={(e) => setForm({ ...form, senha_provisoria: e.target.value })} />
          </>
        )}
        {erro && <p role="alert" className="text-sm text-[rgb(var(--bad-fg))] sm:col-span-2">{erro}</p>}
        <button className="btn-primary sm:col-span-2">Adicionar profissional</button>
      </form>
    </Secao>
  );
}

function Administradores({ salaoId, ehDono }) {
  const VAZIO = { nome: "", email: "", telefone: "", senha_provisoria: "" };
  const [lista, setLista] = useState([]);
  const [form, setForm] = useState(VAZIO);
  const [erro, setErro] = useState("");

  const carregar = useCallback(async () => {
    const { data } = await api.get(`/saloes/${salaoId}/administradores`);
    setLista(data);
  }, [salaoId]);

  useEffect(() => { carregar().catch(() => {}); }, [carregar]);

  async function adicionar(e) {
    e.preventDefault(); setErro("");
    try {
      await api.post(`/saloes/${salaoId}/administradores`, form);
      setForm(VAZIO); carregar();
    } catch (err) {
      setErro(extrairMensagemErro(err));
    }
  }

  async function remover(item) {
    if (!confirm(`Remover o acesso de ${item.nome}?`)) return;
    try {
      await api.delete(`/saloes/${salaoId}/administradores/${item.id}`);
      carregar();
    } catch (err) {
      alert(extrairMensagemErro(err));
    }
  }

  return (
    <Secao titulo="Administradores" descricao="Pessoas com acesso ao painel para responder solicitações e cuidar da agenda. Todos recebem aviso quando chega um pedido novo.">
      <ul className="mb-5 divide-y divide-line">
        {lista.map((a) => (
          <li key={a.usuario_id} className="flex items-center justify-between gap-3 py-3 text-sm">
            <span>
              <span className="font-medium">{a.nome}</span>
              <span className="text-muted"> — {a.email}</span>
              {a.eh_dono && <span className="badge-warn ml-2">dono</span>}
            </span>
            {ehDono && !a.eh_dono && <button className="btn-ghost btn-sm text-[rgb(var(--bad-fg))]" onClick={() => remover(a)}>Remover</button>}
          </li>
        ))}
      </ul>

      {ehDono ? (
        <form onSubmit={adicionar} className="grid gap-3 sm:grid-cols-2">
          <input required className="input" placeholder="Nome" value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} />
          <input required type="email" className="input" placeholder="E-mail" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          <input required className="input" placeholder="WhatsApp (recebe os avisos)" value={form.telefone} onChange={(e) => setForm({ ...form, telefone: e.target.value })} />
          <input required type="password" minLength={6} className="input" placeholder="Senha provisória" value={form.senha_provisoria} onChange={(e) => setForm({ ...form, senha_provisoria: e.target.value })} />
          {erro && <p role="alert" className="text-sm text-[rgb(var(--bad-fg))] sm:col-span-2">{erro}</p>}
          <button className="btn-primary sm:col-span-2">Adicionar administrador</button>
        </form>
      ) : (
        <p className="text-sm text-muted">Só o dono do salão pode adicionar ou remover administradores.</p>
      )}
    </Secao>
  );
}

export default function EquipeTab({ salao, profissionais, recarregarProfissionais, ehDono }) {
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Profissionais salaoId={salao.id} profissionais={profissionais} recarregar={recarregarProfissionais} />
      <Administradores salaoId={salao.id} ehDono={ehDono} />
    </div>
  );
}
