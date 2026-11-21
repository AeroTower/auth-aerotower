# Testes do serviço de auth

**Responsável pelos casos formais:** Rafael · **Cobertura:** 99,5% (meta da disciplina: 90%) · **98 testes**

Cobre os três programas do repositório: a API (`api/`), o worker (`worker/`) e o script de fábrica (`scripts/`).

| Tipo | Pastas | Testes | O que confere |
|---|---|---:|---|
| Unitário | `*/tests/unitarios/` | 47 | código do adesivo, token de sessão, login Google, publicação no RabbitMQ, regras do worker, script de fábrica |
| Integração | `*/tests/integracao/` | 18 | rotas + banco; **script de fábrica chamando a API por HTTP de verdade**; página de saúde do worker |
| Funcional | `api/tests/funcionais/` | 9 | fluxos de login e vínculo como o app usa |
| Aceitação | `api/tests/aceitacao/` | 5 | história "vincular a torre com o código do adesivo", em BDD (`vincular_torre.feature`) |
| Desempenho | `api/tests/desempenho/` | 4 | 5.000 tokens, 20.000 códigos sem repetição, pico de 100 vínculos, listagem com 200 torres |
| Segurança | `api/tests/seguranca/` | 15 | hash do código, força bruta, token forjado, chave de admin, login de desenvolvimento em produção, injeção |

## Como rodar

**Terminal** (na raiz do repositório)
```bash
pip install -r api/requirements.txt -r worker/requirements.txt -r requirements-dev.txt
pytest --cov                     # tudo, com cobertura (falha abaixo de 90%)
pytest -m aceitacao              # só um tipo: unitario, integracao, funcional, aceitacao, desempenho, seguranca
pytest --cov --cov-report=html   # relatório navegável em htmlcov/index.html
```

**PyCharm**
1. Abra a **raiz** do repositório como projeto (não a pasta `api`).
2. *Settings › Tools › Python Integrated Tools › Testing › Default test runner*: **pytest**.
3. Instale as três listas de dependências acima no interpretador do projeto.
4. Botão direito na raiz › **Run 'pytest in auth-aerotower'**; para a cobertura, **More Run/Debug › Run with Coverage**.

**GitHub**: o job `testes` do workflow `azure.yml` roda em todo pull request e **antes de cada deploy**. Se um teste falhar ou a cobertura cair abaixo de 90%, a Azure não recebe a versão nova. A aba *Actions* mostra a tabela por tipo, e *Artifacts › evidencias-testes-auth* traz o relatório HTML.

## Casos de teste formais (1 de cada tipo)

Plataforma de todos: Python 3.11, pytest 9, Ubuntu (GitHub Actions) e Windows (PyCharm).

### AU-UNI-01 · Unitário · Código do adesivo com formato errado
| Campo | Valor |
|---|---|
| Cenário | A função `valido()` recebe códigos digitados de jeitos diferentes |
| Pré-requisitos | Nenhum (função isolada) |
| Passos | Chamar `valido(codigo)` para cada dado |
| Dados | `K9X2-7QHM` · `K9X27QHM` · `K9X2-7QH` (curto) · `K9X2-70HM` (tem 0, fora do alfabeto) |
| Esperado | Válido, válido, inválido, inválido |
| Obtido | Conforme esperado |
| Status | ✅ Sucesso |
| Teste | `api/tests/unitarios/test_codigo.py::test_valido_rejeita_codigos_errados` |

### AU-INT-01 · Integração · Script de fábrica cadastra a torre na API
| Campo | Valor |
|---|---|
| Cenário | Na fábrica, o script cadastra uma placa e depois troca o código do adesivo |
| Pré-requisitos | API rodando num servidor local (uvicorn) com `ADMIN_API_KEY`; RabbitMQ substituído por dublê |
| Passos | 1. `provisionar_torre.py --kit completo --torre-id at-24dcc3a1b2c4`. 2. `provisionar_torre.py --torre-id AT-24DCC3A1B2C4 --novo-codigo` |
| Dados | Torre `AT-24DCC3A1B2C4`, kit completo |
| Esperado | Eventos `torre.cadastrada` e `torre.desvinculada`; adesivo PNG gerado; `torres.csv` com 2 linhas e **sem o código** |
| Obtido | Conforme esperado |
| Status | ✅ Sucesso |
| Teste | `api/tests/integracao/test_script_fabrica_http.py::test_fabrica_cadastra_gera_adesivo_e_troca_codigo` |

### AU-FUN-01 · Funcional · Regras 1 pessoa = 1 torre e 1 torre = 1 dono
| Campo | Valor |
|---|---|
| Cenário | Maria vincula uma torre, tenta uma segunda, João tenta a dela, Maria desvincula e João vincula |
| Pré-requisitos | Duas torres cadastradas; login de desenvolvimento ligado |
| Passos | Sequência de `POST /torre/vincular`, `POST /auth/dev` e `DELETE /torre/{id}/vinculo` |
| Dados | Código em minúsculas e sem hífen; apelido "Varanda" |
| Esperado | 200 → 400 ("já possui") → 409 → 200 → 200; eventos com a versão certa |
| Obtido | Conforme esperado |
| Status | ✅ Sucesso |
| Teste | `api/tests/funcionais/test_fluxo_vinculo.py::test_regras_um_para_um_e_eventos` |

### AU-ACE-01 · Aceitação (BDD) · Código do adesivo vincula a torre
| Campo | Valor |
|---|---|
| Cenário | *Dado* uma torre do kit "pro" que saiu da fábrica e a Ana logada; *quando* ela digita o código com o apelido "Varanda"; *então* a torre aparece na conta dela e o Backend é avisado |
| Pré-requisitos | História de usuário "Vincular a torre à minha conta com o código do adesivo" |
| Passos | Executados pelos passos em português de `vincular_torre.feature` |
| Dados | Código gerado na fábrica; apelido "Varanda" |
| Esperado | `GET /auth/me` com a torre e o apelido; evento `torre.vinculada` com o dono |
| Obtido | Conforme esperado (e os outros 4 cenários da história também passaram) |
| Status | ✅ Sucesso |
| Teste | `api/tests/aceitacao/vincular_torre.feature` |

### AU-DES-01 · Desempenho (spike) · Pico de ativações no dia da entrega
| Campo | Valor |
|---|---|
| Cenário | Um lote de 100 torres é entregue e os 100 clientes vinculam em seguida |
| Pré-requisitos | 100 torres cadastradas e 100 usuários logados |
| Passos | 100 `POST /torre/vincular` em sequência, medindo o tempo |
| Dados | Um código diferente por pessoa |
| Esperado | Todas as respostas 200, em menos de 15 s (limite folgado) |
| Obtido | 100 de 100 com 200, em menos de 1,5 s |
| Status | ✅ Sucesso |
| Teste | `api/tests/desempenho/test_desempenho_auth.py::test_pico_de_ativacoes_no_dia_de_entrega` |

### AU-SEG-01 · Segurança · Tentativa de adivinhar o código do adesivo
| Campo | Valor |
|---|---|
| Cenário | Um usuário logado chuta códigos para pegar a torre de alguém |
| Pré-requisitos | Pelo menos uma torre cadastrada |
| Passos | 200 `POST /torre/vincular` com códigos aleatórios no formato certo |
| Dados | Códigos de 8 caracteres do alfabeto do adesivo (31⁸ ≈ 850 bilhões de combinações) |
| Esperado | Nenhum acerto e nenhum evento publicado |
| Obtido | 0 acertos, 0 eventos |
| Status | ✅ Sucesso |
| Teste | `api/tests/seguranca/test_seguranca_auth.py::test_tentativa_de_adivinhar_codigo` |
