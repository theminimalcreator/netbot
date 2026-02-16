# 🗺️ Roadmap Atualizado: NetBot "Digital Twin"

**Status do Projeto:** 🟡 Em Transição (V1 → V1.1)
**Visão:** Validar a "Alma" do bot com memória de longo prazo, inteligência social (análise de perfil) e expansão para redes de texto.

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

## ✅ V2: O Criador (Content Machine)
**Foco:** Deixar de reagir e começar a publicar (Agente Ativo).

* **Redes:** Todas as anteriores.
* **Funcionalidades:**
    * [x] **Trend Watcher:** Monitorar RSS feeds de tecnologia (`scripts/fetch_news.py`).
    * [x] **Agente Autor:** Gerar updates de projetos pessoais (`scripts/generate_project_updates.py`).
    * [x] **Editor Chef:** Transformar ideias em posts nativos para cada rede (`core/editor_chef.py`).

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

### 📝 Próximos Passos Técnicos (Prioridade V1)

1.  **Database:** Ativar `vector` no Supabase.
2.  **Profile Analyzer:** Criar o script que pega os 10 últimos posts de um usuário.
3.  **Knowledge Base:** Implementar a classe de RAG.