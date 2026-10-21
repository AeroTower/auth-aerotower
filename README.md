# 🌿 AeroTower — Sistema de Autenticação e Automação IoT (`auth-aerotower`)

Este repositório contém a infraestrutura backend do sistema **AeroTower**, responsável pela gestão de utilizadores (via **Google OAuth2**), validação das regras de negócio de vinculação de torres e processamento assíncrono para o ecossistema de Internet das Coisas (IoT).

A arquitetura adota um padrão híbrido **Gateway + Event-Driven Worker**, garantindo alta performance na interface do utilizador e desacoplamento do processamento de hardware.
---


---

## 🔍 Explicação Detalhada dos Serviços

---

### 🟢 SERVIÇO A — API Gateway (`servico_a_api`)

O **Serviço A** é a porta de entrada síncrona da aplicação. Desenvolvido em **FastAPI**, o seu principal objetivo é responder às requisições do cliente web/mobile com latência mínima, garantindo a validação imediata da identidade e das regras de negócio.

#### Responsabilidades Principais:

1. **Autenticação Flexível com Google OAuth2**:
   - **ID Token (JWT)**: Tenta validar diretamente o token JWT via biblioteca oficial `google-auth` (utilizado no ecossistema mobile ou web pop-up).
   - **Fallback Access Token**: Caso o cliente web envie um *Access Token* proveniente do *Implicit Flow* do Google OAuth2, a API faz o fallback síncrono para a API **Google UserInfo** (`https://www.googleapis.com/oauth2/v3/userinfo`) para recuperar e validar o e-mail do utilizador com segurança.

2. **Validação Síncrona das Regras de Negócio (Mapeamento 1:1)**:
   - **Restrição de Utilizador (1 Utilizador ➔ 1 Torre)**: Garante que um e-mail autenticado não consiga cadastrar mais de uma torre simultaneamente. Se o e-mail já possuir uma torre associada, a API rejeita a requisição imediatamente com **HTTP 400 Bad Request**.
   - **Restrição de Dispositivo (1 Torre ➔ 1 Utilizador)**: Impede que um token/código de torre que já pertence a um utilizador seja reivindicado por outro. Retorna **HTTP 409 Conflict**.
   - *Por que a validação é feita no Serviço A?* Para permitir que o aplicativo Flutter apresente um feedback de erro instantâneo no botão do formulário (via `SnackBar`), sem redirecionar o utilizador para o Dashboard indevidamente.

3. **Despacho de Eventos (*Message Producer*)**:
   - Assim que o vínculo passa nas regras de validação síncrona, o Serviço A serializa a intenção no formato JSON e publica-a na fila `vincular_torre` do **RabbitMQ** usando mensagens persistentes (`delivery_mode = 2`).

#### Rotas do Serviço A:
* `GET /`: Healthcheck geral do serviço e status de configuração de ambiente.
* `GET /test`: Endpoint simplificado de diagnóstico.
* `POST /auth/google`: Recebe o token do Google, autentica o utilizador e informa se ele já possui uma AeroTower associada.
* `POST /torre/vincular`: Processa a validação síncrona das regras de negócio e publica o evento de vínculo no RabbitMQ.

---

### 🔵 SERVIÇO B — Worker de Automação e IoT (`servico_b_worker`)

O **Serviço B** é o componente assíncrono que roda em segundo plano. Desenvolvido em **Python** puro com o driver **Pika**, ele consome as mensagens enfileiradas pelo Serviço A no RabbitMQ e executa tarefas de longa duração e integração técnica com o hardware.

#### Responsabilidades Principais:

1. **Consumo Assíncrono Orientado a Eventos**:
   - Escuta continuamente a fila `vincular_torre` do RabbitMQ sem expor portas HTTP externas.
   - Utiliza confirmação manual de mensagens (`basic_ack`) para garantir que nenhuma tarefa seja perdida caso o container seja reiniciado abruptamente.

2. **Provisionamento de Dispositivos (IoT Onboarding)**:
   - Quando recebe um evento de vínculo aprovado, o Worker gera as credenciais e chaves de acesso para o microcontrolador **ESP32** instalado na torre física.
   - Configura os tópicos e permissões de comunicação no broker **MQTT** (HiveMQ / Mosquitto).

3. **Ingestão de Telemetria de Sensores**:
   - Coleta e processa dados contínuos transmitidos pelos sensores da torre (temperatura/umidade do ar via SHT3x, pH, condutividade elétrica e nível de reservatório).
   - Armazena as séries temporais em bases de dados otimizadas (ex: InfluxDB ou PostgreSQL).

4. **Motor de Automação e Regras de Cultivo**:
   - Controla o acionamento de atuadores em tempo real: ciclos de pulverização das bombas aeropónicas, timers da iluminação LED e dosagem de soluções nutritivas.

5. **Gerenciador de Alertas e Notificações**:
   - Executa rotinas de verificação de anomalias em segundo plano (ex: queda súbita no nível de água ou falha na bomba) e dispara notificações push/e-mail para o utilizador.

---

## 📋 Regras de Negócio do Sistema
• Um utilizador NÃO PODE ter mais de uma torre associada.
• Uma torre NÃO PODE pertencer a mais de um utilizador.
