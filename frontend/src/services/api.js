// -*- Cliente HTTP centralizado (Axios) -*-
//
// Toda chamada à API do backend passa por esta instância, que já:
//   1. Aponta para VITE_API_URL (definido no .env do frontend).
//   2. Anexa automaticamente o token JWT salvo no localStorage em cada
//      requisição (via interceptor de request).
//   3. Redireciona para /login se a API responder 401 (token expirado
//      ou inválido) — assim nenhuma página precisa tratar isso na mão.

import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:5000/api",
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (resposta) => resposta,
  (erro) => {
    if (erro.response?.status === 401) {
      localStorage.removeItem("access_token");
      localStorage.removeItem("usuario");
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(erro);
  }
);

// Endereço base da API (também mostrado ao administrador para configurar o
// webhook do WhatsApp).
export const URL_BASE_API = api.defaults.baseURL;

export default api;

// --- Funções auxiliares de autenticação, usadas pelas páginas ---

export function salvarSessao(usuario, token) {
  localStorage.setItem("access_token", token);
  localStorage.setItem("usuario", JSON.stringify(usuario));
}

export function obterUsuarioLogado() {
  const bruto = localStorage.getItem("usuario");
  return bruto ? JSON.parse(bruto) : null;
}

export function encerrarSessao() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("usuario");
}

// Extrai uma mensagem de erro amigável de uma resposta de erro do Axios.
export function extrairMensagemErro(erro) {
  return erro.response?.data?.erro || "Ocorreu um erro inesperado. Tente novamente.";
}
