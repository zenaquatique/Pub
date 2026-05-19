"""Planificateur APScheduler — lance la routine marketing quotidiennement."""
import logging
import signal
import sys
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from config import POSTING_HOUR, POSTING_MINUTE
from agent import run_marketing_session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

scheduler = BlockingScheduler(timezone="Europe/Paris")


def daily_marketing_job() -> None:
    logger.info("=== Routine marketing quotidienne démarrée (%s) ===", datetime.now().isoformat())
    try:
        rapport = run_marketing_session()
        logger.info("=== Routine terminée ===\n%s", rapport)
    except Exception:
        logger.exception("Erreur pendant la routine marketing")


def _shutdown(signum, frame):
    logger.info("Signal %d reçu — arrêt du planificateur.", signum)
    scheduler.shutdown(wait=False)
    sys.exit(0)


def main() -> None:
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    trigger = CronTrigger(hour=POSTING_HOUR, minute=POSTING_MINUTE, timezone="Europe/Paris")
    scheduler.add_job(daily_marketing_job, trigger, id="daily_marketing", replace_existing=True)

    logger.info(
        "Planificateur démarré — routine quotidienne à %02d:%02d (Europe/Paris).",
        POSTING_HOUR, POSTING_MINUTE,
    )

    # Lancement immédiat au démarrage pour valider la configuration
    logger.info("Exécution immédiate au démarrage…")
    daily_marketing_job()

    scheduler.start()


if __name__ == "__main__":
    main()
