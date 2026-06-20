from arq import cron, create_pool
from arq.connections import RedisSettings

from app.config import settings
from app.workers.jobs.booking_reminder import booking_reminder
from app.workers.jobs.collect_constraints import collect_constraints, send_constraint_dm
from app.workers.jobs.execute_booking import execute_booking
from app.workers.jobs.expire_event import expire_event
from app.workers.jobs.run_decision_engine import run_decision_engine
from app.workers.jobs.send_proposal import send_proposal_to_group


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    functions = [
        collect_constraints,
        send_constraint_dm,
        run_decision_engine,
        send_proposal_to_group,
        execute_booking,
        expire_event,
        booking_reminder,
    ]
    # Cron Concierge : relance des réservations non confirmées, toutes les 30 min.
    cron_jobs = [
        cron(booking_reminder, minute={0, 30}, run_at_startup=False),
    ]
    max_jobs = 20
    job_timeout = 300


async def get_arq_pool():
    return await create_pool(RedisSettings.from_dsn(settings.redis_url))
