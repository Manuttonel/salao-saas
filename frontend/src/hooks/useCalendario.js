// Carrega e navega o calendário mensal de um salão (GET /saloes/<id>/calendario).
// Usado pelo cliente (escolher o dia) e pelo administrador (marcar dias).

import { useCallback, useEffect, useState } from "react";
import api from "../services/api";

export default function useCalendario(salaoId) {
  const hoje = new Date();
  const [ano, setAno] = useState(hoje.getFullYear());
  const [mes, setMes] = useState(hoje.getMonth() + 1);
  const [dias, setDias] = useState([]);
  const [carregando, setCarregando] = useState(false);

  const recarregar = useCallback(async () => {
    if (!salaoId) {
      setDias([]);
      return;
    }
    setCarregando(true);
    try {
      const { data } = await api.get(`/saloes/${salaoId}/calendario`, {
        params: { mes: `${ano}-${String(mes).padStart(2, "0")}` },
      });
      setDias(data.dias);
    } catch {
      setDias([]);
    } finally {
      setCarregando(false);
    }
  }, [salaoId, ano, mes]);

  useEffect(() => {
    recarregar();
  }, [recarregar]);

  function mudarMes(delta) {
    const novo = new Date(ano, mes - 1 + delta, 1);
    setAno(novo.getFullYear());
    setMes(novo.getMonth() + 1);
  }

  return { ano, mes, dias, carregando, mudarMes, recarregar };
}
