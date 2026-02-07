# 🤖 Instagram AI Persona (MVP)

**Versão:** 1.0 (Alpha - Testnet)  
**Role:** Automação de Engajamento Humano  
**Stack:** Python, Instagrapi, Agno (Phidata), OpenAI GPT-4o-mini, Supabase.

## 1. Visão Geral do Produto

O **Instagram AI Persona** é um agente autônomo projetado para interagir (comentar) em posts de terceiros, simulando o comportamento, tom de voz e visão de um usuário humano específico.

Diferente de bots tradicionais que comentam baseados apenas em hashtags ("Nice pic!"), este sistema utiliza **IA Multimodal (Visão + Texto)** para "enxergar" a foto e ler a legenda, gerando comentários contextuais impossíveis de distinguir de um humano.

### 🎯 Objetivos (KPIs)
*   **Meta Diária:** 10 interações de alta qualidade (Segunda a Sexta).
*   **Qualidade:** 0% de comentários genéricos (spam).
*   **Segurança:** Manter a conta segura operando dentro dos limites da API não-oficial.

## 2. Arquitetura do Sistema

O fluxo de dados segue uma pipeline linear com persistência de estado.

```mermaid
graph TD
    A -->|Gatilho| B[1. Discovery]
    B -->|Post Candidato| C[2. Preparation]
    C -->|Contexto Completo| D[3. Brain (Agno Agent)]
    D -->|Structured Output| E[4. Execution (Instagrapi)]
    E -->|Sucesso| F[5. Persistência (SQLite)]
```

## 3. Detalhamento das Etapas (Pipeline)

### 🕵️ Etapa 1: Discovery (Descoberta & Roteamento)
**Objetivo:** Selecionar onde interagir, balanceando manutenção de networking e descoberta de novos perfis.

*   **Lógica de Roteamento (70/30):**
    *   **70% (VIPs):** Lista fixa de ~100 perfis (amigos, influencers, leads).
    *   **30% (Discovery):** Lista de Hashtags de nicho (ex: `#pythondev`, `#indiehacker`).
*   **Filtros de Qualidade:**
    *   Ignorar posts com > 3 dias (evita parecer stalker).
    *   Ignorar perfis privados.
    *   Ignorar posts já interagidos (Check no SQLite).
    *   **Nas Hashtags:** Selecionar apenas "Top Posts" (evita spam da aba "Recentes").

### 👁️ Etapa 2: Preparation (Preparação de Contexto)
**Objetivo:** Agrupar as informações necessárias para o Agente.

*   **Entrada:** Objeto `Media` do Instagrapi.
*   **Contexto Visual:**
    *   Identificar URL da imagem/capa (O Agno baixa/processa automaticamente).
*   **Contexto Social:**
    *   Baixar os últimos 5-10 comentários para análise de sentimento.
*   **Contexto Textual:**
    *   Legenda limpa (Sanitizada).

### 🧠 Etapa 3: The Brain (Núcleo de IA - Agno Agent)
**Objetivo:** Gerar o comentário usando um Agente Autônomo (Agno Framework). O Agente recebe a imagem e a legenda, processa com GPT-4o e retorna uma saída estruturada.

*   **Agente (Agno/Phidata):**
    *   Substitui chamadas manuais da OpenAI por um Agente estruturado.
    *   **Modelo:** `gpt-4o-mini` (Vision/Omni).
*   **Persona & Instruções:**
    *   Mantém o tom: Casual, Brasileiro, Breve.
    *   **Configuração Centralizada:** Todos os prompts (System Message, regras) ficam em `config/prompts.yaml` para fácil ajuste sem mexer no código.
    *   Instruções injetadas no System Prompt do Agente.
*   **Structured Output (Pydantic):**
    *   O Agente não retorna texto solto. Ele retorna um objeto JSON estrito:
    ```python
    class PostAction(BaseModel):
        should_comment: bool = Field(..., description="Se deve comentar ou ignorar (SKIP)")
        comment_text: str = Field(..., description="O texto do comentário (sem hashtags)")
        reasoning: str = Field(..., description="Breve motivo da decisão")
    ```
*   **Regras Anti-Bloqueio (Hard Constraints):**
    *   Proibido usar hashtags na resposta.
    *   Proibido pedir para seguir (CTA).
    *   Máximo de 1 emoji.
    *   Comentar sobre elementos visuais da foto (prova de humanidade).
*   **Validação de Segurança:**
    *   Se o Agente detectar conteúdo sensível (Luto, Tragédia, Política Extrema), `should_comment` será `False`.

### 🤖 Etapa 4: Execution (Instagrapi API)
**Objetivo:** Efetuar a ação na plataforma simulando um dispositivo móvel.

*   **Tecnologia:** Biblioteca `instagrapi` (emula um Samsung Galaxy S23).
*   **Gestão de Sessão (Crítico):**
    *   Login realizado apenas uma vez.
    *   Sessão salva em `session.json`.
    *   Execuções subsequentes reutilizam os cookies/tokens para evitar "Suspicious Login".
*   **Humanização (Jitter):**
    *   **Random Sleep:** Pausa aleatória (5s a 15s) entre "ler" o post e "comentar".
    *   **Simulação de digitação:** (backend delay).

### 💾 Etapa 5: Persistência (Memória)
**Objetivo:** Evitar duplicidade e controlar limites.

*   **Banco de Dados:** Supabase.
*   **Schema:**
    *   `interaction_log`: Registra `post_id`, `username`, `comment_text`, `timestamp`.
    *   `daily_counter`: Controla se já atingiu as 10 interações do dia.

### 📜 Etapa 6: Logging & Monitoring
**Objetivo:** Rastreabilidade total das ações do robô.

*   **Console (Stdout):** Logs detalhados (INFO/DEBUG) para acompanhar em tempo real o que o robô está pensando/fazendo. Ex: `[INFO] Analisando Post 123...`, `[DEBUG] SkipReason: Conteúdo sensível`.
*   **Arquivo (.log):** Salva os mesmos logs do console em arquivo `app.log` para debug posterior.
*   **Banco de Dados:** Supabase (PostgreSQL). Apenas ações de SUCESSO e estatísticas diárias.

## 4. Estrutura de Pastas (Sugestão)

```plaintext
/instagram-ai-persona
│
├── /config
│   ├── vip_list.json       # Lista de usuários alvo
│   ├── hashtags.json       # Lista de tags alvo
│   └── prompts.yaml        # [NEW] Central de Prompts (Persona & Regras)
│
├── /core
│   ├── discovery.py        # Lógica de seleção de posts
│   ├── brain.py            # Integração OpenAI (GPT-4o)
│   ├── instagram_client.py # Wrapper do Instagrapi (Login/Session)
│   ├── database.py         # Conexão SQLite
│   └── logger.py           # [NEW] Configuração de Logs (Console + Arquivo)
│
├── main.py                 # Arquivo principal (Orquestrador)
├── requirements.txt        # Dependências (instagrapi, openai, etc)
├── .env                    # Chaves de API (OpenAI, User/Pass)
└── README.md               # Este arquivo
```

## 5. Requisitos de Instalação

### Dependências Python
```bash
pip install instagrapi openai pillow schedule python-dotenv
```

### Variáveis de Ambiente (.env)
```ini
OPENAI_API_KEY="sk-..."
IG_USERNAME="sua_conta_teste"
IG_PASSWORD="sua_senha_teste"
```

## 6. Gestão de Risco & Limites (Safety)

| Risco | Probabilidade | Mitigação Implementada |
| :--- | :--- | :--- |
| **Shadowban** | Média | Limite rígido de 10 comments/dia. Conteúdo variado gerado por IA (sem repetição). |
| **Bloqueio de Login** | Alta | Reuso de sessão (`session.json`). Não logar/deslogar repetidamente. |
| **Detecção de Bot** | Média | Uso de IA Vision para comentários contextuais. Delays aleatórios (Jitter). |
| **Banimento de IP** | Alta (em Cloud) | **Recomendação:** Rodar localmente (seu PC) ou usar Proxy 4G Residencial. Nunca usar IP de Datacenter (AWS/DigitalOcean). |