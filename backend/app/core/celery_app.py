from celery import Celery
from celery.schedules import crontab
from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "stage_crm",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.services.scraping_tasks",
        "app.services.newsletter_tasks",
        "app.services.follow_up_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Paris",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# ── Tâches planifiées ─────────────────────────────────────
celery_app.conf.beat_schedule = {
    # Scan quotidien des offres — tous les jours à 6h du matin
    "daily-scraping": {
        "task": "app.services.scraping_tasks.run_daily_scraping",
        "schedule": crontab(hour=6, minute=0),
    },
    # Newsletter quotidienne — tous les jours à 8h
    "daily-newsletter": {
        "task": "app.services.newsletter_tasks.send_daily_newsletter",
        "schedule": crontab(hour=8, minute=0),
    },
    # Vérification des relances à envoyer — toutes les 2h
    "check-follow-ups": {
        "task": "app.services.follow_up_tasks.check_pending_follow_ups",
        "schedule": crontab(minute=0, hour="*/2"),
    },
    # Vérification des cookies d'intégration — tous les 3 jours
    "check-integration-cookies": {
        "task": "app.services.scraping_tasks.check_integration_cookies",
        "schedule": crontab(hour=9, minute=0, day_of_week="*/3"),
    },
}
