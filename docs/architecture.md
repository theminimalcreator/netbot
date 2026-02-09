# 🤖 NetBot Architecture

**Version:** 2.0 (Multi-Platform Support)  
**Role:** Human Engagement Automation  
**Stack:** Python, Playwright, Agno (Phidata), OpenAI GPT-4o-mini, Supabase.

## 1. Product Overview

**NetBot** is an autonomous agent designed to interact on social media platforms (currently Instagram, with support for others) by simulating human behavior.

Unlike traditional bots, this system uses **Multimodal AI (Vision + Text)** to "see" the post/image and read the content, generating contextual comments indistinguishable from a human.

### 🎯 Objectives (KPIs)
*   **Daily Goal:** ~10 high-quality interactions (adjustable per platform).
*   **Quality:** 0% generic comments (spam).
*   **Safety:** Operates within limits using a real browser to avoid detection.

## 2. System Architecture

The architecture is **modular** and **event-driven**, separating the "Brain" (Agent) from the "Body" (Network Clients).

```mermaid
graph TD
    A[Orchestrator (Main)] -->|Loop| B(Discovery Strategy)
    B -->|Candidates| C{Agent Analysis}
    C -->|Retrieve History| K[(Knowledge Base)]
    K -->|Context| C
    C -->|No| D[Skip]
    C -->|Yes| E[Action Decision]
    E -->|Execute| F[Social Network Client]
    F -->|Log & Embed| G[(Supabase)]
```

## 3. Core Components

### 🧠 Core Layer (`core/`)
*   **`agent.py`:** The centralized AI brain. Uses **Agno** and **GPT-4o** to analyze content and decide on actions. It is platform-agnostic.
*   **`knowledge_base.py`:** Manages the **RAG (Retrieval-Augmented Generation)** system. Uses `pgvector` to store and retrieve past interactions, allowing the agent to learn from history.
*   **`models.py`:** Unified data models (`SocialPost`, `SocialAuthor`, `ActionDecision`) that normalize data from different platforms into a common format.
*   **`interfaces.py`:** Abstract Base Classes (ABCs) defining the contract for new networks:
    *   `SocialNetworkClient`: Methods like `login()`, `like_post()`, `post_comment()`.
    *   `DiscoveryStrategy`: Methods to find content (`find_candidates()`).
*   **`database.py`:** Handles persistence to Supabase. Includes atomic operations via RPC (e.g., `increment_daily_stats`) to prevent race conditions during concurrent interactions.

### 🔌 Network Layer (`core/networks/`)
Each platform is a self-contained module implementing the Core Interfaces.

#### Instagram Module (`core/networks/instagram/`)
*   **`client.py`:** Implements `SocialNetworkClient` using **Playwright**.
    *   Handles Session Management (`browser_state/`).
    *   Performs DOM-level interactions (clicks, typing).
*   **`discovery.py`:** Implements `DiscoveryStrategy`.
    *   Routes between **VIP List** (70%) and **Hashtags** (30%).

## 4. Workflows

### 🕵️ Discovery
The `DiscoveryStrategy` selects posts to interact with.
1.  **VIP Mode:** Checks profiles from `config/vip_list.json`.
2.  **Discovery Mode:** Searches tags from `config/hashtags.json`.
3.  **Filtering:** Ignores old posts, own posts, or already interacted posts.

### 👁️ Context & Analysis
The `SocialNetworkClient` extracts:
*   **Visuals:** Image URLs.
*   **Text:** Caption, Author Name.
*   **Context:** Recent comments (for sentiment/context).

### 🤖 Decision & Execution
1.  **Agent** receives the standardized `SocialPost`.
2.  **RAG Context:** Agent queries `NetBotKnowledgeBase` (pgvector) to find similar past interactions for tone consistency and memory.
3.  **LLM** analyzes alignment with the Persona and provided context.
4.  **Output:** Structured `ActionDecision` (ACT or SKIP).
5.  **Client** executes the action (Like/Comment) using human-like delays (Jitter).
6.  **Persistence:** Action is logged in `interactions` and daily counts are incremented atomically via RPC.

## 5. Folder Structure

```plaintext
/netbot
│
├── /config                 # Configuration (VIPs, Hashtags, Settings)
├── /core
│   ├── /networks           # Platform Implementations
│   │   └── /instagram      # Instagram Module
│   │       ├── client.py
│   │       └── discovery.py
│   ├── agent.py            # AI Logic
│   ├── database.py         # Storage
│   ├── interfaces.py       # Abstract Contracts
│   ├── models.py           # Data Types
│   └── logger.py           # Logging
│
├── main.py                 # Application Entry Point
└── ...
```

## 6. Safety & Limits

| Risk | Mitigation |
| :--- | :--- |
| **Shadowban** | Strict daily limits per platform. |
| **Detection** | Human-like delays (Jitter), real browser automation. |
| **Logic** | Agent validates content safety before commenting. |
