# 🌿 AeroTower — Serviço de Autenticação (`auth-aerotower`)

Identidade das pessoas (login Google), vínculo pessoa ↔ torre e cadastro de
fábrica das torres. Padrão **API Gateway + Worker orientado a eventos**, com
RabbitMQ entre os dois.

```
App Flutter ──HTTPS──▶ Serviço A (API)  ──evento torre.*──▶ RabbitMQ ──▶ Serviço B (worker)
     │                    │ Postgres (usuarios, torres)                       │
     │                    └─ emite o token de sessão (JWT)                     │ PUT /internal/torres/{id}
     └──── mesmo token ─────────────────────────────▶ Backend (telemetria, bomba) ◀┘
```

## Serviço A — API (`api/`)

| Rota | Quem chama | O que faz |
|---|---|---|
| `POST /auth/google` `{token}` | app | Confere o token do Google (ID token no celular, access token na web) e devolve `token` de sessão + `possui_torre` / `torre_id` |
| `POST /auth/dev` `{id}` | app em desenvolvimento | Login sem Google. Só com `AUTH_MODO_DEV=true` |
| `GET /auth/me` | app | Usuário logado e suas torres |
| `POST /torre/vincular` `{codigo, apelido?}` | app (Bearer) | Aplica as regras de negócio e vincula |
| `DELETE /torre/{id}/vinculo` | app (Bearer) | Desvincula (o adesivo volta a valer para o próximo dono) |
| `POST /admin/torres` `{torreId, kit}` | script de fábrica (`X-Admin-Key`) | Cadastra a placa e gera o código do adesivo |
| `POST /admin/torres/{id}/novo-codigo` | fábrica | Adesivo perdido: troca o código e desvincula |
| `GET /admin/torres` | fábrica | Lista tudo |
| `POST /admin/sincronizar` | operação | Reenvia o estado de todas as torres (Backend com banco novo) |

### Regras de negócio

- Um usuário **não pode** ter mais de `MAX_TORRES_POR_USUARIO` torres (hoje 1) → **400**.
- Uma torre **não pode** pertencer a mais de um usuário → **409**.
- Só vincula quem está logado, e só com um código que saiu da fábrica. O
  código é aleatório (não deriva do MAC) e o banco guarda apenas o hash.

## Serviço B — Worker (`worker/`)

Consome `torre.*` da exchange `aerotower.eventos` (fila `backend.torres`) e
leva o estado de cada torre ao Backend.

- **ack manual**: a mensagem só sai da fila depois que o Backend confirmou;
- Backend fora do ar → espera e devolve a mensagem para a fila;
- evento com dado ruim → fila de falhas `backend.torres.falhas` (dead letter);
- cada evento traz o **estado completo + versão**: reprocessar é seguro e
  evento atrasado é ignorado pelo Backend.

## Rodar

```bash
cp .env.example .env        # preencha
docker compose up --build   # rabbitmq + postgres + api + worker
```

API em http://localhost:8000/docs, painel do RabbitMQ em http://localhost:15672 (guest/guest).

Testes: `cd api && pytest` e `cd worker && pytest`.

Fábrica: `python scripts/provisionar_torre.py --kit pro --porta COM5` (ver o cabeçalho do script).

## Variáveis

| Variável | Serviço | Para quê |
|---|---|---|
| `GOOGLE_CLIENT_IDS` | A | Client IDs aceitos (web, Android, iOS) |
| `JWT_SEGREDO` | A | Assina o token. **Mesmo valor no Backend** |
| `DATABASE_URL` | A | Postgres (SQLite local se vazio) |
| `RABBITMQ_URL` | A e B | `amqp://usuario:senha@host:5672/vhost` |
| `ADMIN_API_KEY` | A | Script de fábrica |
| `MAX_TORRES_POR_USUARIO` | A | Regra de negócio (padrão 1) |
| `AUTH_MODO_DEV` | A | Libera `/auth/dev`. Nunca em produção |
| `CORS_ORIGENS` | A | Domínios do app e da loja |
| `BACKEND_URL` | B | Endereço do Backend |
| `SERVICO_API_KEY` | B | Chave da rota interna. **Mesmo valor no Backend** |

## Correções em relação à versão anterior

1. **Vínculo sem login.** O e-mail vinha no corpo da requisição: qualquer
   pessoa vinculava qualquer torre a qualquer e-mail. Agora o dono é quem
   está logado (token no header).
2. **Código inventado.** Qualquer texto virava torre. Agora só vale código
   gerado no cadastro de fábrica.
3. **Token de outro app.** O fallback de access token aceitava tokens
   emitidos para qualquer site; o ID token não conferia o app quando
   `GOOGLE_CLIENT_ID` estava vazio. Agora os dois conferem o `aud`.
4. **Dados em memória** (dicionário duplicado na API e no worker) →
   Postgres, e o worker não guarda estado.
5. **Evento perdido em silêncio.** Falha no RabbitMQ era só impressa e a API
   respondia sucesso. Agora o vínculo é desfeito e o app recebe 503.
6. **E-mail como identidade** → `sub` da conta Google (não muda).
7. Pasta `venv/` (2.732 arquivos) e `__pycache__` removidos do Git.
