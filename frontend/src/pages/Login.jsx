// Página de login / cadastro.
//
// Um único formulário alterna entre "Entrar" e "Criar conta". No
// cadastro, só é possível escolher os papéis "dono" ou "cliente" — o
// papel "profissional" é criado pelo dono do salão (veja
// backend/app/routes/salao_routes.py, rota convidar_profissional).
//
// Depois de logar, redireciona para o dashboard certo de acordo com o
// papel do usuário retornado pela API.

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { salvarSessao, extrairMensagemErro } from "../services/api";

const ROTA_POR_PAPEL = {
  dono: "/dashboard",
  profissional: "/profissional",
  cliente: "/agenda",
};

export default function Login() {
  const navigate = useNavigate();
  const [modo, setModo] = useState("login"); // "login" | "cadastro"
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState("");

  const [form, setForm] = useState({
    nome: "",
    email: "",
    senha: "",
    telefone: "",
    papel: "cliente",
  });

  function atualizarCampo(campo, valor) {
    setForm((atual) => ({ ...atual, [campo]: valor }));
  }

  async function enviar(evento) {
    evento.preventDefault();
    setErro("");
    setCarregando(true);

    try {
      const endpoint = modo === "login" ? "/auth/login" : "/auth/registrar";
      const payload =
        modo === "login" ? { email: form.email, senha: form.senha } : form;

      const resposta = await api.post(endpoint, payload);
      const { usuario, access_token } = resposta.data;

      salvarSessao(usuario, access_token);
      navigate(ROTA_POR_PAPEL[usuario.papel] || "/login");
    } catch (e) {
      setErro(extrairMensagemErro(e));
    } finally {
      setCarregando(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-sm bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h1 className="text-xl font-semibold text-brand-700 mb-1">Salão SaaS</h1>
        <p className="text-sm text-gray-500 mb-6">
          {modo === "login" ? "Entre na sua conta" : "Crie sua conta"}
        </p>

        <form onSubmit={enviar} className="space-y-3">
          {modo === "cadastro" && (
            <>
              <input
                type="text"
                placeholder="Nome completo"
                required
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
                value={form.nome}
                onChange={(e) => atualizarCampo("nome", e.target.value)}
              />
              <input
                type="tel"
                placeholder="Telefone (com DDD e país, ex: 5511999998888)"
                required
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
                value={form.telefone}
                onChange={(e) => atualizarCampo("telefone", e.target.value)}
              />
              <select
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
                value={form.papel}
                onChange={(e) => atualizarCampo("papel", e.target.value)}
              >
                <option value="cliente">Sou cliente</option>
                <option value="dono">Sou dono de salão/barbearia</option>
              </select>
            </>
          )}

          <input
            type="email"
            placeholder="E-mail"
            required
            className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
            value={form.email}
            onChange={(e) => atualizarCampo("email", e.target.value)}
          />
          <input
            type="password"
            placeholder="Senha"
            required
            minLength={6}
            className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
            value={form.senha}
            onChange={(e) => atualizarCampo("senha", e.target.value)}
          />

          {erro && <p className="text-sm text-red-600">{erro}</p>}

          <button
            type="submit"
            disabled={carregando}
            className="w-full bg-brand-600 hover:bg-brand-700 disabled:opacity-60 text-white rounded-md py-2 text-sm font-medium transition"
          >
            {carregando ? "Aguarde..." : modo === "login" ? "Entrar" : "Criar conta"}
          </button>
        </form>

        <button
          className="w-full text-center text-sm text-brand-600 hover:underline mt-4"
          onClick={() => setModo(modo === "login" ? "cadastro" : "login")}
        >
          {modo === "login" ? "Não tem conta? Criar agora" : "Já tenho conta, entrar"}
        </button>
      </div>
    </div>
  );
}
