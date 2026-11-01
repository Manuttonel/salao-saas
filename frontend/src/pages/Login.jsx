// Página de login / cadastro, com a escolha de tema (Unisex, Glow ou Dark).
//
// No cadastro só é possível escolher "cliente" ou "dono" — administradores e
// profissionais recebem o acesso do dono do salão (veja EquipeTab).
// Depois de entrar, a pessoa vai para o painel certo conforme o papel.

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { salvarSessao, extrairMensagemErro } from "../services/api";
import SeletorTema from "../components/SeletorTema";
import { useTema } from "../context/TemaContext";

export const ROTA_POR_PAPEL = {
  dono: "/dashboard",
  administrador: "/dashboard",
  profissional: "/profissional",
  cliente: "/agenda",
};

export default function Login() {
  const navigate = useNavigate();
  const { tema, adotarDaConta } = useTema();
  const [modo, setModo] = useState("login"); // "login" | "cadastro"
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState("");

  const [form, setForm] = useState({ nome: "", email: "", senha: "", telefone: "", papel: "cliente" });
  const atualizar = (campo, valor) => setForm((atual) => ({ ...atual, [campo]: valor }));

  async function enviar(evento) {
    evento.preventDefault();
    setErro("");
    setCarregando(true);

    try {
      const endpoint = modo === "login" ? "/auth/login" : "/auth/registrar";
      // No cadastro, a conta já nasce com o tema que a pessoa estava vendo.
      const payload = modo === "login" ? { email: form.email, senha: form.senha } : { ...form, tema };
      const { data } = await api.post(endpoint, payload);

      salvarSessao(data.usuario, data.access_token);
      adotarDaConta(data.usuario);
      navigate(ROTA_POR_PAPEL[data.usuario.papel] || "/login");
    } catch (e) {
      setErro(extrairMensagemErro(e));
    } finally {
      setCarregando(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="grid w-full max-w-3xl gap-6 md:grid-cols-[1fr_300px]">
        <div className="card">
          <h1 className="titulo text-2xl text-brand-600">Salão SaaS</h1>
          <p className="mb-6 mt-1 text-sm text-muted">
            {modo === "login" ? "Entre na sua conta" : "Crie sua conta"}
          </p>

          <form onSubmit={enviar} className="space-y-3">
            {modo === "cadastro" && (
              <>
                <input type="text" placeholder="Nome completo" required className="input" autoComplete="name"
                  value={form.nome} onChange={(e) => atualizar("nome", e.target.value)} />
                <input type="tel" placeholder="WhatsApp com DDD (ex: 11 99999-8888)" required className="input" autoComplete="tel"
                  value={form.telefone} onChange={(e) => atualizar("telefone", e.target.value)} />
                <select className="input" value={form.papel} onChange={(e) => atualizar("papel", e.target.value)}>
                  <option value="cliente">Sou cliente</option>
                  <option value="dono">Sou dono de salão/barbearia</option>
                </select>
              </>
            )}

            <input type="email" placeholder="E-mail" required className="input" autoComplete="email"
              value={form.email} onChange={(e) => atualizar("email", e.target.value)} />
            <input type="password" placeholder="Senha" required minLength={6} className="input"
              autoComplete={modo === "login" ? "current-password" : "new-password"}
              value={form.senha} onChange={(e) => atualizar("senha", e.target.value)} />

            {erro && <p role="alert" className="text-sm text-[rgb(var(--bad-fg))]">{erro}</p>}

            <button type="submit" disabled={carregando} className="btn-primary w-full">
              {carregando ? "Aguarde..." : modo === "login" ? "Entrar" : "Criar conta"}
            </button>
          </form>

          <button className="mt-4 w-full text-center text-sm text-brand-600 hover:underline"
            onClick={() => { setErro(""); setModo(modo === "login" ? "cadastro" : "login"); }}>
            {modo === "login" ? "Não tem conta? Criar agora" : "Já tenho conta, entrar"}
          </button>
        </div>

        <div className="card h-fit">
          <SeletorTema inline />
        </div>
      </div>
    </div>
  );
}
