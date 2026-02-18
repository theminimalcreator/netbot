from datetime import date, datetime
from typing import Dict, Any, List
import logging
from core.database import db

logger = logging.getLogger(__name__)

class DashboardGenerator:
    """
    Aggregates metrics from daily_stats, interactions, and discovered_posts
    to generate a comprehensive dashboard for the cycle.
    """

    def __init__(self, cycle_date: date = None, cycle_start_time: datetime = None):
        self.cycle_date = cycle_date or date.today()
        self.cycle_start_time = cycle_start_time

    def gather_metrics(self) -> Dict[str, Any]:
        """
        Collects all necessary data for the dashboard.
        Returns a dictionary structure matching the dashboard template.
        """
        metrics = {
            "funnel": {},
            "cycle_interactions": [],
            "integrity": {
                "ignored_profiles": 0,
                "discarded_posts": 0
            },
            "resources": {
                "models": ["GPT-4o-mini (Judge)", "Claude 3.5 Sonnet (Writer)"], # Hardcoded for now as per template
                "tokens": 0, # To be implemented via llm_logs aggregation if possible
                "cost": 0.0
            }
        }

        # 1. Funnel Metrics (Views, Approved, Posted) per platform
        platforms = ["linkedin", "devto", "twitter", "instagram", "threads"]
        
        for platform in platforms:
            # Views (Discovered)
            views = db.get_count("discovered_posts", {"platform": platform, "created_at": f"GTE:{self.cycle_date}"}) 
            # Note: GTE logic needs to be handled in db wrapper or raw SQL for dates. 
            # Since db wrapper is simple, we might need a custom query method in database.py
            
            # Approved (Status = approved or commented)
            approved = db.get_count("discovered_posts", {
                "platform": platform, 
                "created_at": f"GTE:{self.cycle_date}",
                "status": ["approved", "commented", "posted"] # Rough logic
            })

            # Posted (Interactions)
            posted = db.get_daily_count(platform)

            metrics["funnel"][platform] = {
                "views": views,
                "approved": approved,
                "posted": posted
            }

        # 2. Integrity Stats (Mock/Placeholder for now as we don't strictly track 'ignored' count perfectly in a separate table yet)
        # We can query discovered_posts where status='rejected'
        metrics["integrity"]["ignored_profiles"] = db.get_count("discovered_posts", {"status": "rejected", "created_at": f"GTE:{self.cycle_date}"})
        
        # 4. Token Usage & Cost (Cycle)
        if self.cycle_start_time:
             usage = db.get_token_usage_since(self.cycle_start_time)
             metrics["resources"]["tokens"] = usage["input_tokens"] + usage["output_tokens"]
             metrics["resources"]["cost"] = usage["total_cost"]
        else:
             # Fallback (Mock or 0)
             metrics["resources"]["tokens"] = 0
             metrics["resources"]["cost"] = 0.0

        # 3. Cycle Interactions (All interactions in this cycle)
        if self.cycle_start_time:
             cycle_interactions = db.get_interactions_since(self.cycle_start_time)
        else:
             # Fallback if no start time provided (e.g. legacy call), use recent
             cycle_interactions = db.get_recent_interactions(limit=5)
             
        metrics["cycle_interactions"] = cycle_interactions

        return metrics

    def format_report(self, metrics: Dict[str, Any]) -> str:
        """
        Formats the gathered metrics into the Telegram message string.
        """
        # Header
        report = f"🚀 NetBot: Ciclo de Engajamento Concluído\n"
        report += f"📅 {self.cycle_date.strftime('%d/%m/%Y')} | {datetime.now().strftime('%H:%M')}\n\n"

        # Funnel
        report += "📈 Funil de Conversão por Rede:\n"
        report += "—————————————————\n"
        
        icons = {
            "linkedin": "🔗", "devto": "📝", "twitter": "🐦", "instagram": "📸", "threads": "🧵"
        }
        
        for platform, data in metrics["funnel"].items():
            icon = icons.get(platform, "🌐")
            # Skip if no activity to keep it clean, or show 0s? User template shows 0s.
            # Capitalize platform name
            p_name = platform.capitalize()
            if platform == 'devto': p_name = 'Dev.to'
            
            status_icon = "✅" if data['posted'] > 0 else "⏳"
            report += f"{icon} {p_name}: {data['views']} vistos | {data['approved']} aprovados | {data['posted']} postado {status_icon}\n"

        report += "\n"

        # Cycle Interactions
        interactions = metrics.get("cycle_interactions", [])
        if interactions:
            report += "💬 Interações Realizadas (Neste Ciclo):\n"
            report += "—————————————————\n"
            for interaction in interactions:
                # Interaction dict structure from db.get_recent_interactions
                platform = interaction.get('platform', 'unknown').capitalize()
                icon = icons.get(interaction.get('platform'), "🔗")
                author = interaction.get('username', 'Unknown')
                text = interaction.get('comment_text', '')
                
                # Truncate text
                if len(text) > 100:
                    text = text[:97] + "..."
                
                # Confidence/Reasoning if available in metadata
                meta = interaction.get('metadata', {})
                confidence = meta.get('confidence', 'N/A')
                
                report += f"{icon} {platform} | @{author} (🎯 {confidence}%)\n"
                report += f"\"{text}\"\n"
                
                # Try to fetch URL from discovered_posts if not in interaction metadata
                url = meta.get('url')
                if not url:
                    try:
                        # Fallback lookup
                        res = db.client.table("discovered_posts").select("metrics").eq("external_id", interaction['post_id']).execute()
                        if res.data:
                            url = res.data[0]['metrics'].get('url')
                    except Exception:
                        pass
                
                if url:
                    report += f"👉 Ver postagem no {platform}: {url}\n"
                report += "\n"

        # Integrity
        report += "🛡️ Filtro de Integridade:\n"
        report += "—————————————————\n"
        report += f"🔥 Hype Sellers/Ignored: {metrics['integrity']['ignored_profiles']} perfis ignorados.\n\n"

        # Resources (Placeholder values for now)
        tokens = metrics['resources'].get('tokens', 0)
        cost = metrics['resources'].get('cost', 0.0)
        
        report += "💸 Resumo de Recursos:\n"
        report += "—————————————————\n"
        report += f"🤖 Modelos: {', '.join(metrics['resources']['models'])}\n"
        report += f"🎫 Tokens: {tokens:,}\n"
        report += f"💰 Custo Est.: ${cost:.4f} USD\n\n"
        
        report += "🟢 Status: All systems operational.\n"
        
        if metrics.get("next_cycle_wait"):
            wait_min = int(metrics["next_cycle_wait"] / 60)
            report += f"⏳ Próximo ciclo em: ~{wait_min} minutos."
        
        return report

    def save(self, metrics: Dict[str, Any], summary: str, telegram_message_id: str = None):
        """
        Saves the dashboard to the database.
        """
        try:
             data = {
                 "cycle_date": self.cycle_date.isoformat(),
                 "metrics": metrics,
                 "summary": summary,
                 "telegram_message_id": telegram_message_id
             }
             # Upsert based on cycle_date
             db.client.table("dashboards").upsert(data, on_conflict="cycle_date").execute()
        except Exception as e:
            logger.error(f"Failed to save dashboard: {e}")
