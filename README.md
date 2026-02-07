# 🤖 NetBot - Instagram AI Persona

> **Automated Engagement Agent powered by GPT-4o Vision & Agno Framework.**

**NetBot** é um agente autônomo inteligente projetado para interagir no Instagram simulando comportamento humano. Diferente de bots tradicionais que usam APIs privadas (arriscado) ou comentários genéricos, o NetBot "olha" para o post, entende o contexto (legenda + imagem) e gera comentários relevantes e autênticos.

## ✨ Funcionalidades Principais

- **🧠 Inteligência Multimodal (Vision + Text):** Usa `GPT-4o` (via framework **Agno**) para analisar a imagem e a legenda do post antes de interagir.
- **🕵️ Navegação Human-Like (Playwright):**
  - Usa um **navegador real** (Chromium) para navegar no Instagram.
  - Clica, digita e faz scroll como um humano.
  - Mantém **cookies de sessão** para evitar logins constantes e suspeitas.
- **🎯 Discovery Híbrido Inteligente:**
  - **70% VIP List:** Foca em perfis de alta relevância definidos por você.
  - **30% Hashtags:** Explora novos conteúdos em nichos específicos.
- **🛡️ Segurança & Anti-Ban:**
  - **Limites Diários:** Controlados via banco de dados para não exceder taxas seguras.
  - **Jitter (Intervalos Aleatórios):** Pausas variáveis entre ações (ex: 10-50 min) para parecer natural.
  - **Verificação de Duplicidade:** Nunca interage no mesmo post duas vezes.
- **☁️ Supabase Integration:** Armazena logs de interação, estatísticas diárias e erros na nuvem.

---

## 🏗️ Arquitetura do Projeto

O projeto é modular e separado em responsabilidades claras:

- **`core/agent.py` (O Cérebro):** Onde a mágica da IA acontece. Define a "Persona" do bot e usa a OpenAI para decidir *se* deve comentar e *o que* comentar.
- **`core/instagram_client.py` (O Corpo):** Controla o navegador via Playwright. Lida com seletores CSS, login, extração de dados da página e execução de ações (Like/Comment).
- **`core/discovery.py` (O Explorador):** Define a estratégia de busca de posts (VIPs vs Hashtags) e filtra candidatos inválidos.
- **`core/database.py` (A Memória):** Gerencia a persistência de dados no Supabase.
- **`main.py` (O Maestro):** Loop principal que orquestra os ciclos de interação e gerencia o tempo de repouso.

---

## 🛠️ Tecnologias

- **Python 3.10+**
- **[Agno Framework](https://github.com/agno-agi/agno):** Orquestração de Agentes AI.
- **[Playwright](https://playwright.dev/):** Automação de navegador moderna e resiliente.
- **[Supabase](https://supabase.com/):** Database (PostgreSQL) as a Service.
- **OpenAI GPT-4o-mini:** Modelo de linguagem e visão.

---

## 🚀 Instalação e Uso

### 1. Pré-requisitos
- Python 3.10+
- Conta no OpenAI (API Key)
- Projeto no Supabase (URL e Key)

### 2. Configuração
1. Clone o repositório.
2. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```
3. Configure o `.env` (use `.env.example` como base):
   ```bash
   OPENAI_API_KEY=sk-...
   SUPABASE_URL=https://...
   SUPABASE_KEY=ey...
   IG_USERNAME=seu_usuario
   IG_PASSWORD=sua_senha
   ```

### 3. Personalização
- **VIPs:** As listas de perfis VIP e Hashtags ficam em `config/`.
- **Persona:** Edite os prompts em `config/prompts.yaml` (se existir) ou diretamente no `core/agent.py` para mudar a personalidade do bot.

### 4. Executando
```bash
python main.py
```

> **Nota:** Por padrão, o bot pode iniciar em modo `DRY_RUN` (apenas simulação, sem comentar de verdade). Verifique o `config/settings.py` para ajustar.

---

## ⚠️ Disclaimer

Este projeto é **educacional**. O uso de automação em redes sociais (bots) viola os Termos de Serviço do Instagram e pode levar ao bloqueio da sua conta. **Use por sua conta e risco.**
