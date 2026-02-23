# 🗺️ Roadmap Atualizado: NetBot "Digital Twin"

**Status do Projeto:** 🟢 Em Produção (V2)
**Visão:** Validar a "Alma" do bot com memória de longo prazo, inteligência social (análise de perfil) e publicação autônoma multimídia (V2).

---

## ✅ PoC: A Fundação (Onde Estamos)
**Status:** **Concluído & Funcional**
**Foco:** Infraestrutura Modular, Segurança e Visão Computacional.

* **Arquitetura:**
    * [x] **Design Modular:** Estrutura definida para suportar múltiplos clientes (`core/networks`).
    * [x] **Database:** Integração com Supabase para logs de interação e limites diários.
* **Rede (Instagram):**
    * [x] **Client Playwright:** Navegação humana, gestão de sessão e cookies.
    * [x] **Vision AI:** Agente capaz de "ver" imagens para gerar contexto.
    * [x] **Discovery:** Estratégia Híbrida (VIPs + Hashtags) implementada.

---

## 🚧 V1: The "Digital Twin" & Social Intelligence (O Foco Agora)
**Foco:** Implementar o "Cérebro" (RAG + Análise de Perfil) e expandir o "Corpo" (Threads/X).

### 1. O Cérebro (Knowledge Base & RAG)
*Transformar o bot de um "GPT Genérico" para o "Seu Gêmeo Digital".*
* **Funcionalidades:**
    * [x] **RAG Engine (`core/knowledge_base.py`):** Sistema de busca semântica (`pgvector`) para o Agente consultar "Como o Guilherme responderia isso?".
    * [x] **Agent Update:** Atualizar o `core/agent.py` para consultar a `KnowledgeBase` antes de chamar a OpenAI.
    * [x] **Database Optimization:** Migração para operações atômicas (RPC) no Supabase para evitar condições de corrida (Race Conditions).

### 2. A Empatia (Audience Awareness) **[NOVO]**
*Entender quem está do outro lado para adaptar o tom (Code Switching).*
* **Funcionalidades:**
    * [x] **Profile Scraper:** Criar método no Playwright para extrair Bio + Últimos 10 Posts/Comentários do perfil alvo (VIP ou Descoberta).
    * [x] **Dossier Generator:** Usar LLM para analisar esses 10 posts e gerar um resumo JSON:
        * *Ex: "Perfil Técnico, valoriza Clean Code, tom sarcástico. Evite emojis excessivos."*
    * [x] **Context Injection:** Injetar esse "Dossier" no prompt do Agente para que a resposta seja personalizada para aquele interlocutor específico.

### 3. O Corpo (Expansão de Texto)
*Adaptação para redes onde a imagem é secundária.*
* **Redes:** 🧵 **Threads** e ✖️ **X (Twitter)**.
* **Funcionalidades:**
    * [x] **Refatoração:** Organizar estrutura de pastas para `core/networks/instagram`, `twitter`, etc.
    * [x] **Twitter Client:** Criar `core/networks/twitter` herdando da interface base.
    * [x] **Threads Client:** Criar `core/networks/threads`.
    * [x] **Text-Only Mode:** Calibrar o Agente para funcionar bem apenas com texto.

---

## 📅 V1.5: O Especialista (Comunidades)
**Foco:** Interpretação de textos longos e construção de autoridade técnica.

* **Redes:** 💻 **Dev.to** e 🤖 **Reddit**.
* **Funcionalidades:**
    * [x] **Dev.to Client:** Ler artigos técnicos e gerar comentários complementares.
    * [x] **Deep Reading:** Melhorar o RAG para lidar com artigos longos.

---

## ✅ V2: O Criador & Content Cascade
**Foco:** Deixar de reagir e começar a publicar carrosséis e posts multimidia nativos e automatizados.

* **Arquitetura (Cascade Engine):**
    * [x] **The Strategists:** Agentes de planejamento Mensal (`StrategicRoadmapper`), Semanal (`WeeklyTactician`) e Diário (`DailyBriefingAgent`).
    * [x] **The Makers:** Agentes de produção (`VisualDesigner`, `SlideContentGenerator`, `Copywriter`).
* **Visual Engine:**
    * [x] **PillowRenderer:** Motor dinâmico implementado para desenhar os Carrosséis 4:5 internos (Bg Color, radial gradient, e fontes dinâmicas baseadas em marca).
* **Automação UI & Workflow:**
    * [x] **Human-in-the-Loop:** Aprovação de publicação (Makers) enviada via Telegram.
    * [x] **Playwright Instagram Publisher:** Injeção direta de assets em um browser headless via Playwright para driblar restrições da Graph API do Instagram.

---

## 📅 V3: Reddit
**Foco:** Interagir no Reddit.

* **Redes:** Reddit.
* **Funcionalidades:**
    * [ ] **Reddit Client:** "Karma Farming" em subs pequenos.

---

## 📅 V4: Enterprise (High Ticket)
**Foco:** Negócios e Carreira (B2B).

* **Rede:** 👔 **LinkedIn**.
* **Funcionalidades:**
    * [ ] **LinkedIn Client:** Navegação ultra-segura.
    * [ ] **Human-in-the-Loop:** Aprovação humana obrigatória.
    * [ ] **Gestão de DMs:** Triagem de leads.

---

### 📝 Próximos Passos Técnicos (Prioridade V3)

1.  **Observability LangFuse:** Integrar telemetria nativa no pipeline de LangGraph/Agno.
2.  **Expansão Playwright:** Adaptar o mesmo `PlaywrightPublisher` que brilha no Instagram para postar nas outras redes (LinkedIn, Threads, Twitter).
3.  **Human-in-the-Loop em massa:** Fazer o Telegram Gateway permitir agendamento em batch (Schedule queue).