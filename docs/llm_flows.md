# LLM Interactions & Prompt Flows

This document details all Large Language Model (LLM) interactions within the NetBot system. It serves as a reference for understanding how the AI makes decisions, generates content, and processes data.

## Overview
All agents leverage **OpenAI's GPT-4o-mini** via the **Agno** framework. They share a common persona foundation (`docs/persona/persona.md`) but have specialized roles and output schemas.

---

## 1. Social Engagement Agent — Sequential Chain (`core/agent.py` + `core/chains/`)
**Role**: The "Face" of the bot. Uses a 3-layer pipeline to efficiently filter, contextualize, and generate comments.

> For full architecture details with diagrams, see [Sequential Chain Architecture](sequential_chain.md).

### Pipeline: Judge → Context Builder → Ghostwriter

1.  **Layer 1 — The Judge** (`core/chains/judge.py`):
    - Lightweight LLM call (~300 tokens). No persona loaded.
    - Approves/rejects based on topic relevance.
    - Outputs: `JudgeVerdict` (should_engage, category, language).

2.  **Layer 2 — Context Builder** (`core/chains/context_builder.py`):
    - **Pure Python** (no LLM cost). Only runs if Judge approved.
    - Assembles: RAG, Profile Dossier, Engagement Signals, Comments, Style Guide.
    - Outputs: `EngagementContext` (structured data for the Ghostwriter).

3.  **Layer 3 — Ghostwriter** (`core/chains/ghostwriter.py`):
    - Full persona LLM call (~1500 tokens). Only runs if Judge approved.
    - Applies negative constraints, language matching, consistency checks.
    - Outputs: `GhostwriterOutput` (comment_text, confidence_score, reasoning).

4.  **Post-Processing**: Confidence filter (< 70% → skip).
5.  **Final Output**: `ActionDecision` (should_act, content, confidence_score, reasoning).

---

## 2. Editor-in-Chief (`core/editor_chef.py`)
**Role**: The Content Creator. Transforms raw ideas (news, insights) into platform-native posts.

### Flow
1.  **Input**:
    - **Raw Idea**: Title, Summary, Original Text.
    - **Target Platform**: Twitter, Threads, or Dev.to.
2.  **Logic**:
    - Checks business day/time limits.
    - Selects pending idea from DB.
3.  **System Prompt**:
    - Base Persona + "Editor-in-Chief".
    - **Platform Guidelines**:
        - *Twitter*: < 280 chars, punchy, no-bullshit.
        - *Threads*: Conversational, discussion-starter.
        - *Dev.to*: Structured Markdown, technical, clear title.
4.  **Output**: `SocialCopy`
    - `title`: For blog posts.
    - `body`: The actual post text.
    - `tags`: Relevant hashtags/keywords.

---

## 3. Profile Analyst (`core/profile_analyzer.py`)
**Role**: The Psychologist. Analyzes user profiles to guide future interactions.

### Flow
1.  **Input**:
    - **Profile**: Bio, Follower Count.
    - **Activity**: Last 10 posts (truncated).
2.  **Logic**:
    - Triggered when interacting with a "high-value" target or new connection.
3.  **System Prompt**:
    - "Expert social media analyst".
    - Task: Create a deep psychological/professional dossier.
4.  **Output**: `ProfileDossier`
    - `technical_level`: Beginner/Intermediate/Expert.
    - `tone_preference`: e.g., "Sarcastic", "Formal".
    - `interaction_guidelines`: Specific advice (e.g., "Don't use emojis").

---

## 4. News Curator (`scripts/fetch_news.py`)
**Role**: The Gatekeeper. Filters RSS feeds to find relevant tech news.

### Flow
1.  **Input**:
    - **RSS Entry**: Title, Snippet, Source Name.
2.  **Logic**:
    - Dedupes against previously processed URLs.
3.  **System Prompt**:
    - "Gatekeeper & Summarizer".
    - Criteria: Must match interests (AI, Engineering) and be High Quality (No clickbait).
4.  **Output**: `NewsDecision`
    - `approved`: Boolean.
    - `reasoning`: Why it was approved/rejected.
    - `summary`: TL;DR (1 sentence).
    - `key_points`: 3 bullet points.

---

## 5. Project Update Generator (`scripts/generate_project_updates.py`)
**Role**: The Reporter. Turns internal project metadata into public build-in-public updates.

### Flow
1.  **Input**:
    - **Project**: Name, Tech Stack, Recent Challenge.
2.  **System Prompt**:
    - "Project Curator".
    - Style: "No-Bullshit", connect challenge to stack, technical insight.
3.  **Output**: JSON
    - `title`: Punchy title.
    - `content`: 150-300 char update.
    - `reasoning`: Why this is engaging.
