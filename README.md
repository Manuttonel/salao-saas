# Salão SaaS

Sistema multi-perfil (dono, profissional, cliente) para salões de beleza e
barbearias: agendamento com prevenção automática de conflitos de horário,
cobrança recorrente da assinatura da plataforma via Mercado Pago (com
webhooks), lembretes e confirmações via WhatsApp, e rotinas em segundo
plano (APScheduler) para verificar assinaturas vencidas e disparar
lembretes de agendamento.

Este projeto foi construído e **testado de ponta a ponta** (backend com
`pytest`, frontend testado manualmente no navegador: cadastro, login,
criação de salão/serviço/profissional, agendamento com bloqueio de
conflito, cancelamento e página de assinatura).

## Stack

- **Backend:** Python 3.11+, Flask, SQLAlchemy, PostgreSQL, APScheduler,
  SDK do Mercado Pago, JWT (Flask-JWT-Extended).
- **Frontend:** React 18 + Vite, Tailwind CSS, Axios, React Router.
- **Banco:** PostgreSQL (driver `psycopg` v3 — veja nota abaixo).

> **Nota sobre o driver do PostgreSQL:** o enunciado original pedia
> `psycopg2-binary`, mas em Python 3.13+/3.14 no Windows não há wheel
> pré-compilado dele ainda (só compila com o Visual C++ Build Tools
> instalado). Por isso o projeto usa `psycopg[binary]` (psycopg v3), que
> tem wheels prontos para Windows e é 100% compatível com
> Flask-SQLAlchemy — só muda o prefixo da URL de conexão, de
> `postgresql://` para `postgresql+psycopg://` (já configurado em
> `backend/app/config.py` e nos arquivos `.env.example`). Se você estiver
> em Python 3.11/3.12, pode trocar para `psycopg2-binary` no
> `requirements.txt` e ajustar a URL de volta para `postgresql://`, se
> preferir.

## Estrutura de pastas

```
salao-saas/
├── backend/
│   ├── app/
│   │   ├── models/        # Usuario, Salao, Servico, Profissional, Cliente, Agendamento, Assinatura...
│   │   ├── routes/        # auth, salao, agendamento, pagamento, webhook
│   │   ├── services/      # mercado_pago_service, whatsapp_service, agendador_service
│   │   └── scheduler/     # jobs.py (APScheduler)
│   ├── migrations/        # geradas pelo Flask-Migrate (Alembic)
│   ├── tests/              # pytest (auth, agendamento, health)
│   ├── requirements.txt
│   ├── .env.example
│   └── run.py
├── frontend/
│   ├── src/
│   │   ├── pages/          # Login, DashboardDono, DashboardProfissional, AgendaCliente, Assinatura
│   │   ├── components/     # Navbar, ProtectedRoute
│   │   └── services/api.js # cliente Axios com JWT automático
│   ├── package.json
│   ├── vite.config.js
│   └── .env.example
├── docker-compose.yml
└── README.md
```

## Opção A — Rodar com Docker (mais simples)

Pré-requisito: [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado e aberto.

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
docker-compose up --build
```

- Backend: http://localhost:5000
- Frontend: http://localhost:5173
- O banco `db` já sobe configurado e o backend aplica as migrações
  automaticamente antes de iniciar (`flask db upgrade && python run.py`).

Preencha as chaves do Mercado Pago/WhatsApp em `backend/.env` quando for
usar essas integrações de verdade (veja a seção de variáveis abaixo).

## Opção B — Rodar localmente (sem Docker)

### 1. Instalar os pré-requisitos

- **Python 3.11+**: https://www.python.org/downloads/ (marque "Add
  python.exe to PATH" no instalador).
- **Node.js 20 LTS**: https://nodejs.org/
- **PostgreSQL**: https://www.postgresql.org/download/ — durante a
  instalação, defina uma senha para o usuário `postgres` e anote-a.

### 2. Criar os bancos de dados

Com o PostgreSQL instalado, abra um terminal e rode (ajuste o usuário se
necessário):

```bash
psql -U postgres -c "CREATE DATABASE salao_saas;"
psql -U postgres -c "CREATE DATABASE salao_saas_test;"
```

### 3. Backend

```bash
cd backend
python -m venv venv

# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

Abra `backend/.env` e ajuste pelo menos `DATABASE_URL` com a senha do seu
PostgreSQL (formato `postgresql+psycopg://postgres:SUA_SENHA@localhost:5432/salao_saas`).

Gere e aplique as migrações (primeira vez):

```bash
flask db init
flask db migrate -m "modelos iniciais"
flask db upgrade
```

Rode os testes (opcional, mas recomendado):

```bash
pytest
```

Suba o servidor:

```bash
python run.py
```

A API sobe em **http://localhost:5000** (`GET /api/health` para checar).

### 4. Frontend

Em outro terminal:

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

O frontend sobe em **http://localhost:5173**.

## Variáveis de ambiente (`.env`)

### `backend/.env`

| Variável | Para que serve | Onde obter |
|---|---|---|
| `SECRET_KEY`, `JWT_SECRET_KEY` | Chaves de segurança do Flask/JWT | Gere qualquer string aleatória longa (ex.: `python -c "import secrets; print(secrets.token_hex(32))"`) |
| `DATABASE_URL` | Conexão com o PostgreSQL | `postgresql+psycopg://usuario:senha@host:porta/banco` |
| `MERCADOPAGO_ACCESS_TOKEN`, `MERCADOPAGO_PUBLIC_KEY` | Cobrança recorrente | Crie uma aplicação em https://www.mercadopago.com.br/developers/panel e use as credenciais de **teste** enquanto desenvolve |
| `MERCADOPAGO_WEBHOOK_SECRET` | Valida que o webhook realmente veio do Mercado Pago | Painel do Mercado Pago → Webhooks → "Assinatura secreta" |
| `MERCADOPAGO_WEBHOOK_URL` | URL pública que o Mercado Pago chama ao mudar status de pagamento | Em dev, exponha `localhost:5000` com [ngrok](https://ngrok.com/) ou similar |
| `WHATSAPP_PROVIDER` | `meta_cloud_api` ou `evolution_api` | Veja comentários em `backend/app/services/whatsapp_service.py` |
| `WHATSAPP_MODO_SIMULACAO` | Se `true`, mensagens só são logadas no console (não enviadas) | Deixe `true` enquanto não tiver credenciais reais de WhatsApp |

Sem preencher as chaves do Mercado Pago/WhatsApp, o sistema continua
funcionando normalmente para desenvolvimento — as chamadas de pagamento
retornam um erro amigável explicando o que falta, e as mensagens de
WhatsApp são simuladas (aparecem no log do backend, ex.:
`[WHATSAPP SIMULADO] Para 5511999998888: ...`).

### `frontend/.env`

| Variável | Para que serve |
|---|---|
| `VITE_API_URL` | URL base da API (`http://localhost:5000/api` por padrão) |

## Como o sistema foi validado nesta entrega

- **Backend:** suíte `pytest` com 5 testes passando, incluindo um teste
  de ponta a ponta que garante que dois clientes não conseguem reservar
  o mesmo horário do mesmo profissional (regra de negócio mais crítica
  do sistema).
- **Frontend:** testado manualmente no navegador, contra o backend real
  (não mockado): cadastro de dono e cliente, login, criação de salão,
  cadastro de serviço e profissional, cálculo de horários livres,
  criação de agendamento, bloqueio de horários conflitantes,
  cancelamento (pelo cliente e pelo profissional), e página de
  assinatura (com erro tratado corretamente quando as chaves do Mercado
  Pago não estão configuradas).

## Tarefas entregues nesta versão

**Backend**
- Models completos: `Usuario` (com papéis dono/profissional/cliente),
  `Salao`, `Servico`, `Profissional`, `Indisponibilidade`, `Cliente`,
  `Agendamento`, `Assinatura`.
- Autenticação JWT com controle de papel por rota (`papel_requerido`).
- CRUD de salão, serviços e profissionais (convite pelo dono).
- Cálculo de horários disponíveis e prevenção de conflito de agenda
  (com trava de linha no banco para evitar corrida em cliques
  simultâneos).
- Cancelamento de agendamento (cliente, profissional ou dono).
- Assinatura recorrente via Mercado Pago (criação, consulta,
  cancelamento) + webhook com validação de assinatura HMAC.
- Bloqueio do painel do dono/profissional quando a assinatura vence
  (cliente final continua enxergando a própria agenda).
- Jobs do APScheduler: verificação diária de assinaturas vencidas +
  lembretes de agendamento (24h e 1h antes) a cada 15 minutos.
- Serviço de WhatsApp com dois provedores (Meta Cloud API / Evolution
  API) e modo de simulação para desenvolvimento sem custo.
- Testes automatizados (`pytest`).

**Frontend**
- Login/cadastro (dono e cliente) com redirecionamento por papel.
- Dashboard do dono: criação de salão, cadastro de serviços e
  profissionais, listagem/cancelamento de agendamentos, banner de
  status da assinatura.
- Dashboard do profissional: agenda própria, marcação de
  indisponibilidade, cancelamento.
- Página do cliente: escolha de salão/serviço/profissional/data,
  horários livres calculados em tempo real, agendamento e cancelamento.
- Página de assinatura: status atual e botão para ir ao checkout do
  Mercado Pago.
- Rotas protegidas por papel (`ProtectedRoute`).

## O que fica para uma próxima entrega (fora do escopo pedido)

- Fluxo de troca de senha provisória do profissional no primeiro
  acesso.
- Tela de detalhes/edição de um agendamento existente (hoje só
  cria/cancela).
- Paginação e filtros mais avançados nas listagens.
- Deploy em produção (o `docker-compose.yml` entregue é voltado para
  desenvolvimento local).
