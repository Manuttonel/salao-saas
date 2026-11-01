# Salão SaaS

Sistema para salões de beleza e barbearias. O cliente **solicita** um horário
(pelo site ou pelo WhatsApp), os administradores do salão **aceitam ou
recusam**, e só o horário aceito fica indisponível para os outros clientes.

## O que o sistema faz

| Quem | O que faz |
|---|---|
| **Cliente** | Escolhe salão, procedimento (ou **Marcar Avaliação**), dia (só os disponíveis), profissional e horário, e envia a solicitação. Acompanha o status e recebe confirmação por WhatsApp. |
| **Dono / administradores** (vários usuários) | Recebem as solicitações em tempo real, aceitam ou recusam, marcam no calendário os dias disponíveis, cadastram procedimentos com o tempo de cada um, controlam clientes e a equipe. O dono também gerencia administradores e a assinatura. |
| **Profissional** (opcional, com login) | Vê a própria agenda e bloqueia horários. |
| **Bot de WhatsApp** | O cliente conversa pelo WhatsApp (menu → procedimento → dia → horário → confirmar) e o pedido chega na mesma fila de solicitações do painel. |

Destaques:

- **Solicitação com aceite:** o pedido nasce *pendente* e **não bloqueia** a
  agenda. Ao aceitar, vira *confirmado* e o horário some para os demais. Se
  dois pedidos disputam o mesmo horário, o painel avisa ("Disputa horário") e
  só o primeiro aceite vale.
- **Procedimentos por categoria** (cabelo, unhas, estética, barba, outros), cada
  um com **duração própria** — é ela que reserva o intervalo certo na agenda.
- **Marcar Avaliação:** procedimento especial de duração curta, que o
  administrador define. Já vem criado em todo salão.
- **Dias disponíveis no calendário:** o administrador clica nos dias para
  marcá-los como disponíveis/indisponíveis (com horário próprio, se quiser).
  Há também o modo "atender somente nos dias que eu marcar".
- **Controle de clientes (CRM):** fichas com observações e histórico. Nascem
  do cadastro manual, do site ou do WhatsApp (reconhecidas pelo telefone).
- **Temas escolhidos por cada pessoa:** **Unisex** (neutro, com cor à escolha),
  **Glow** (claro, rosé e dourado, sofisticado) e **Dark** (preto, vermelho e
  azul-marinho). A escolha fica salva na conta.
- **Cobrança** da assinatura do salão via Mercado Pago (com webhook), lembretes
  de WhatsApp 24 h e 1 h antes, e bloqueio do painel se a assinatura vencer
  (o cliente final continua usando a agenda).

## Stack

- **Backend:** Python 3.11+, Flask, SQLAlchemy, PostgreSQL, APScheduler, Mercado Pago, JWT.
- **Frontend:** React 18 + Vite, Tailwind CSS, Axios, React Router.
- **Banco:** PostgreSQL com driver `psycopg` v3 (URL no formato `postgresql+psycopg://`;
  endereços `postgres://` e `postgresql://` de hospedagens são convertidos sozinhos).

## Estrutura

```
salao-saas/
├── backend/
│   ├── app/
│   │   ├── models/      # usuario, salao (+Servico, DiaAgenda), profissional, cliente, agendamento, assinatura, conversa_whatsapp
│   │   ├── routes/      # auth, salao, agendamento, cliente, pagamento, webhook
│   │   ├── services/    # agendador, whatsapp, bot_whatsapp, cliente, mercado_pago
│   │   └── scheduler/   # jobs (lembretes, vencimentos, expiração de pedidos)
│   ├── migrations/      # Alembic
│   ├── tests/           # pytest (30 testes)
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/       # Login, DashboardDono (painel), DashboardProfissional, AgendaCliente, Assinatura
│   │   ├── components/  # Navbar, Calendario, SeletorTema, admin/* (uma aba por arquivo)
│   │   ├── context/     # TemaContext
│   │   └── services/    # api, tema, formatar
│   └── vercel.json
├── docker-compose.yml   # desenvolvimento local
└── render.yaml          # backend + banco em produção (Render)
```

## Rodar localmente

Pré-requisitos: Python 3.11+, Node 20+, PostgreSQL (ou Docker Desktop).

```bash
# 1) bancos
psql -U postgres -c "CREATE DATABASE salao_saas;"
psql -U postgres -c "CREATE DATABASE salao_saas_test;"

# 2) backend
cd backend
python -m venv venv
venv\Scripts\activate            # Linux/Mac: source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env             # ajuste DATABASE_URL com a sua senha
flask db upgrade                 # cria/atualiza as tabelas
pytest                           # opcional
python run.py                    # http://localhost:5000

# 3) frontend (outro terminal)
cd frontend
npm install
cp .env.example .env
npm run dev                      # http://localhost:5173
```

Com Docker: `cp backend/.env.example backend/.env && cp frontend/.env.example frontend/.env && docker-compose up --build`.

> No VS Code, **não use o botão ▶ "Run Python File"**: ele ignora o `venv`.
> Ative o venv e rode `python run.py` no terminal.

Fluxo para experimentar: crie uma conta de **dono**, cadastre o salão, abra
**Procedimentos**, e em outra janela crie uma conta de **cliente** para
solicitar um horário. Em **Configurações → Bot de WhatsApp** há um simulador
para conversar com o bot sem precisar de celular.

## Variáveis de ambiente

### `backend/.env`

| Variável | Para que serve |
|---|---|
| `SECRET_KEY`, `JWT_SECRET_KEY` | Chaves de segurança. Gere com `python -c "import secrets; print(secrets.token_hex(32))"`. **Em produção o servidor se recusa a iniciar com os valores de exemplo.** |
| `DATABASE_URL` | Conexão com o PostgreSQL |
| `FRONTEND_URL` | Site(s) autorizados a chamar a API (CORS). Vários, separados por vírgula |
| `SCHEDULER_ATIVO` | Liga os jobs em segundo plano. Deixe `true` em um único processo |
| `MERCADOPAGO_ACCESS_TOKEN`, `MERCADOPAGO_PUBLIC_KEY`, `MERCADOPAGO_WEBHOOK_SECRET`, `MERCADOPAGO_WEBHOOK_URL` | Cobrança. Crie uma aplicação em https://www.mercadopago.com.br/developers/panel (use credenciais de **teste** no início) |
| `WHATSAPP_PROVIDER` | `evolution_api` ou `meta_cloud_api` |
| `WHATSAPP_MODO_SIMULACAO` | `true` = mensagens só aparecem no log (nada é enviado) |
| `WHATSAPP_WEBHOOK_TOKEN` | Segredo que o bot exige na URL do webhook (`?token=...`) |
| `WHATSAPP_EVOLUTION_*`, `WHATSAPP_META_*` | Credenciais do provedor escolhido |

Sem as chaves do Mercado Pago/WhatsApp tudo funciona em desenvolvimento: a
cobrança devolve um erro explicando o que falta e o WhatsApp é simulado.

### `frontend/.env`

| Variável | Para que serve |
|---|---|
| `VITE_API_URL` | Endereço da API, terminando em `/api` (ex.: `https://salao-api.onrender.com/api`) |

## Conectar o bot ao WhatsApp

1. Em **Configurações → Bot de WhatsApp** copie o endereço do webhook do salão.
2. Cole no provedor: **Evolution API** (webhook da instância, evento
   `MESSAGES_UPSERT`) ou **Meta Cloud API** (webhook do app).
3. Defina `WHATSAPP_WEBHOOK_TOKEN` no servidor e acrescente `?token=SEU_TOKEN`
   ao endereço do webhook.
4. Preencha as credenciais do provedor e coloque `WHATSAPP_MODO_SIMULACAO=false`.

## Publicar (GitHub + Vercel + backend)

A **Vercel hospeda o frontend**. O backend (Flask com banco PostgreSQL e
tarefas agendadas) precisa de um servidor sempre ligado — a Vercel não serve
para isso. O repositório já traz o `render.yaml` para publicar o backend e o
banco no Render (o `backend/Dockerfile` também serve para Railway, Fly.io etc.).

1. **GitHub:** envie o código (`git push`). Os arquivos `.env` nunca vão: estão no `.gitignore`.
2. **Backend no Render:** *New → Blueprint*, escolha este repositório. Preencha
   `FRONTEND_URL` com o endereço do site na Vercel. As migrações rodam sozinhas
   a cada deploy. Anote o endereço gerado (ex.: `https://salao-api.onrender.com`).
   > O plano gratuito "dorme" após 15 min sem uso e então **não envia os
   > lembretes de WhatsApp nem recebe mensagens do bot**. Para uso real use um plano pago.
3. **Frontend na Vercel:** *Add New → Project*, importe o repositório, defina
   **Root Directory = `frontend`** e a variável `VITE_API_URL` =
   `https://SEU-BACKEND/api`. Cada `git push` publica de novo.
4. **Domínio próprio:** Vercel → *Settings → Domains* → adicione o domínio e
   aponte o DNS como a Vercel indicar. Depois inclua o domínio em `FRONTEND_URL` no backend.

## Testes

`pytest` roda 30 testes (precisa do banco `salao_saas_test`): login e
permissões, solicitação → aceite/recusa, bloqueio de horário só após
confirmação, disputa entre pedidos, vários administradores, calendário
(dias marcados e modo "só dias marcados"), duração da avaliação, controle de
clientes, preferência de tema e a conversa completa do bot de WhatsApp.
