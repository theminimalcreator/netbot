"""
SocialAgent — Sequential Chain Orchestrator

Orchestrates the 3-layer engagement pipeline:
  Layer 1: Judge         → Should we engage? (lightweight LLM)
  Layer 2: ContextBuilder → Assemble RAG, dossier, signals (pure Python)
  Layer 3: Ghostwriter   → Generate the comment (full persona LLM)
"""
from typing import Optional
from config.settings import settings
from core.logger import logger, NetBotLoggerAdapter
from core.models import SocialPost, ActionDecision
from core.knowledge_base import NetBotKnowledgeBase
from core.profile_analyzer import ProfileAnalyzer
from core.chains.judge import Judge
from core.chains.context_builder import ContextBuilder
from core.chains.ghostwriter import Ghostwriter


class SocialAgent:
    def __init__(self):
        self.logger = NetBotLoggerAdapter(logger, {'stage': 'C', 'status_code': 'BRAIN'})
        self.knowledge_base = NetBotKnowledgeBase()

        # Sequential Chain Layers
        self.judge = Judge()
        self.context_builder = ContextBuilder(
            knowledge_base=self.knowledge_base,
            profile_analyzer=ProfileAnalyzer()
        )
        self.ghostwriter = Ghostwriter()

        self.logger.info("🧠 SocialAgent initialized (Sequential Chain: Judge → Context → Writer)")

    def decide_and_comment(self, post: SocialPost, client=None) -> ActionDecision:
        """
        Main entry point — runs the 3-layer sequential chain.

        Args:
            post: The social media post to analyze.
            client: Optional platform client (used by ContextBuilder for profile dossier).

        Returns:
            ActionDecision with the final decision and comment.
        """
        try:
            # ━━━ LAYER 1: THE JUDGE ━━━
            self.logger.info(f"━━━ Layer 1/3: Judge ━━━ Post {post.id}")
            verdict = self.judge.evaluate(post)

            if not verdict.should_engage:
                self.logger.info(f"🚫 Judge rejected post {post.id}: {verdict.reasoning}")
                return ActionDecision(
                    should_act=False,
                    confidence_score=0,
                    reasoning=f"[Judge Rejected] {verdict.reasoning}",
                    action_type="skip",
                    platform=post.platform
                )

            # ━━━ LAYER 2: CONTEXT BUILDER ━━━
            self.logger.info(f"━━━ Layer 2/3: Context Builder ━━━ Post {post.id}")
            context = self.context_builder.build(post, verdict, client=client)

            # ━━━ LAYER 3: THE GHOSTWRITER ━━━
            self.logger.info(f"━━━ Layer 3/3: Ghostwriter ━━━ Post {post.id}")
            output = self.ghostwriter.write(context)

            # ━━━ POST-PROCESSING ━━━
            should_act = True

            # Confidence filter
            if output.confidence_score < 70:
                self.logger.warning(f"⚠️ Confidence too low ({output.confidence_score}%). Skipping.")
                should_act = False
                output.reasoning = f"[Low Confidence {output.confidence_score}%] {output.reasoning}"

            # Empty comment guard
            if not output.comment_text.strip():
                self.logger.warning("⚠️ Empty comment generated. Skipping.")
                should_act = False
                output.reasoning = f"[Empty Comment] {output.reasoning}"

            self.logger.info(
                f"🎯 Final Decision: Act={should_act} | "
                f"Conf={output.confidence_score}% | "
                f"Category={verdict.category.value} | "
                f"Lang={verdict.language}"
            )

            return ActionDecision(
                should_act=should_act,
                confidence_score=output.confidence_score,
                content=output.comment_text,
                reasoning=output.reasoning,
                action_type="comment",
                platform=post.platform
            )

        except Exception as e:
            self.logger.error(f"Agent Malfunction: {e}")
            return ActionDecision(should_act=False, reasoning=f"Error: {e}")
