# 🤖 NetBot: The "Digital Twin" Framework

> **Autonomous Digital Presence Engineering powered by Multimodal AI & RAG.**

The **NetBot** is a high-level autonomous agent designed to act as a **Digital Twin**. It doesn't just "post" or "comment"—it understands context through Vision AI, maintains technical authority via RAG, and simulates human-like interaction to scale presence without losing authenticity.

This project is **Open Source** and serves as a laboratory for **Modular Agentic Workflows**.

---

## 🏗️ System Architecture

NetBot follows a **Modular & Event-Driven** design, strictly separating the "Brain" (AI Logic) from the "Body" (Platform Clients). This ensures the core intelligence remains agnostic to the social network being used.

### User-Mimicry Flow
```mermaid
graph TD
    subgraph "Core Logic"
        Agent[SocialAgent]
        RAG[(Knowledge Base)]
        Profile[Profile Analyzer]
        Editor[Editor Chef]
    end

    subgraph "Actions"
        Disc[Discovery] --> Analysis
        Analysis[Agent Decision] -->|Interact| Comment[Comment/Like]
        Curate[News/Projects] --> Editor -->|Publish| Post[New Post]
    end

    Analysis <--> RAG
    Analysis <--> Profile
```

### Core Components:
* **🧠 The Brain (`core/agent.py`):** Centralized AI powered by **Agno** for reacting and parsing interactions.
* **🌊 Content Cascade (`scripts/content_orchestrator.py`):** The V2 core engine. A sequential multi-agent pipeline:
  * *Strategists*: `StrategicRoadmapper`, `WeeklyTactician`, `DailyBriefingAgent`
  * *Makers*: `VisualDesigner`, `SlideContentGenerator`, `Copywriter`
* **🎨 Rendering Engine (`core/cascade/renderer.py`):** Custom `Pillow` implementation to dynamically generate beautiful, brand-aligned Instagram Carousels.
* **🦾 Network Clients (`core/publishers/` & `core/networks/`):** Implementation of publication and discovery. V2 uses **Playwright** (`PlaywrightInstagramPublisher`) to simulate real human browser behavior to bypass API constraints.
* **📊 Persistence (`core/database.py`):** Supabase integration for logging, tracking content queues, managing storage buckets, and Telegram approvals.

---

## 🧠 Intelligence & Vision

We currently use **GPT-4o-mini** for development and testing as it is the most cost-effective option for validating complex agentic flows.

> **⚠️ Engineering Note:** For production environments where high-fidelity visual analysis and deep technical nuance are required, I recommend using more robust models (such as the full **GPT-4o** or later versions) to ensure the highest quality of interaction.

---

## 🗺️ Roadmap: The Journey to a Digital Twin
The project is structured in versions, steadily moving from a basic bot to a complete autonomous "Digital Twin".

### ✅ V1: The Foundation & Social Intelligence (Completed)
**Focus:** Infrastructure, Safety, Multimodal Vision, and Memory.
* **Modular Architecture:** Support for multiple clients (`core/networks/`).
* **Vision AI:** Agent capable of "seeing" images to generate context-aware responses.
* **RAG Engine:** Semantic search integration for the agent to consult "How would I answer this?".
* **Audience Awareness:** *Profile Scraper* + *Dossier Generator* to analyze an author's tone and background for personalized context injection.
* **Multi-Platform:** Support for **Instagram**, **Twitter (X)**, and **Threads** (Text-Only Mode).

### ✅ V1.5: The Specialist (Completed)
**Focus:** Technical Authority.
* **Dev.to Client:** Reading long-form technical articles and generating insightful comments.
* **Deep Reading:** Enhanced RAG to process long texts.

### ✅ V2: The Creator & Content Cascade (Completed)
**Focus:** Active content generation and autonomous publishing.
* **The Strategists:** Monthly and Weekly planning AI.
* **The Makers:** Daily execution AI (Designers, Copywriters).
* **Automated Rendering:** Generating visual assets via Pillow.
* **Approval Flow:** Human-in-the-loop Telegram integration.
* **Playwright Publishing:** Seamless, headless UI automation for Instagram.

### 📅 V3: Reddit
**Focus:** Niche Community Engagement & Karma Farming.
* **Reddit Client:** Interaction in smaller subreddits.

### 📅 V4: Enterprise
**Focus:** B2B & Career.
* **LinkedIn Client:** Ultra-secure navigation for professional networking.

---

## 🛠️ Tech Stack
* **Python 3.10+**
* **Agno Framework:** Agent orchestration.
* **Playwright:** Resilient browser automation.
* **Supabase:** PostgreSQL + `pgvector` for semantic memory.

---

## 🚀 Getting Started & Persona Setup

### 1. Installation
```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure Your Digital Twin (Persona)
The bot's behavior is driven by a specific persona document:
1. Create a folder: `docs/persona/`.
2. Copy `docs/template-persona.md` into that folder.
3. Fill it with your specific traits, technical background, and tone.
4. Save it as `docs/persona/persona.md`.

### 3. Environment & Run
Set your keys in `.env` (refer to `.env.example`) and start the orchestrator:
```bash
python main.py
```

---

⚠️ Disclaimer
This is an educational tool. Automating social accounts violates most ToS and may lead to account suspension. Use it to study AI orchestration and browser automation at your own risk.

Build with me. Contributions and PRs are welcome!