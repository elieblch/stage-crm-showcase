"""
Tâche de vérification et envoi des relances programmées.
"""

import logging
from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.services.follow_up_tasks.check_pending_follow_ups")
def check_pending_follow_ups():
    """Vérifie les relances à envoyer et les programme."""
    logger.info("🔔 Vérification des relances en attente...")

    # TODO:
    # 1. Requêter follow_ups WHERE is_sent=False AND scheduled_at <= now()
    # 2. Pour chaque relance, envoyer le mail via Gmail API
    # 3. Marquer is_sent=True, sent_at=now()
    # 4. Ajouter un ApplicationEvent

    logger.info("🔔 Relances vérifiées")
    return {"status": "follow_ups_checked"}
