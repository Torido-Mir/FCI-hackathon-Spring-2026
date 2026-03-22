from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from collectors import CMHCCollector, StatsCanCollector
from config import settings
from database import SessionLocal


def run_statscan_collection():
    """Job to run StatsCan data collection."""
    db = SessionLocal()
    try:
        collector = StatsCanCollector(db)
        records, error = collector.run()
        if error:
            print(f"StatsCan collection error: {error}")
        else:
            print(f"StatsCan collection complete: {records} records added")
    finally:
        db.close()


def run_cmhc_collection():
    """Job to run CMHC data collection."""
    db = SessionLocal()
    try:
        collector = CMHCCollector(db)
        records, error = collector.run()
        if error:
            print(f"CMHC collection error: {error}")
        else:
            print(f"CMHC collection complete: {records} records added")
    finally:
        db.close()


def create_scheduler() -> BackgroundScheduler:
    """Create and configure the scheduler."""
    scheduler = BackgroundScheduler()

    # StatsCan building permits - run on 15th of each month at 9 AM
    # (Data is typically released ~45 days after month end)
    scheduler.add_job(
        run_statscan_collection,
        CronTrigger(day=15, hour=9, minute=0),
        id="statscan_monthly",
        name="StatsCan Building Permits Collection",
        replace_existing=True,
    )

    # CMHC housing starts - run on 15th of each month at 10 AM
    scheduler.add_job(
        run_cmhc_collection,
        CronTrigger(day=15, hour=10, minute=0),
        id="cmhc_monthly",
        name="CMHC Housing Starts Collection",
        replace_existing=True,
    )

    # CMHC rental vacancy - run annually in December (after Rental Market Report)
    scheduler.add_job(
        run_cmhc_collection,
        CronTrigger(month=12, day=15, hour=10, minute=0),
        id="cmhc_annual_vacancy",
        name="CMHC Rental Vacancy Collection",
        replace_existing=True,
    )

    return scheduler


# Global scheduler instance
scheduler: BackgroundScheduler | None = None


def start_scheduler():
    """Start the scheduler if enabled."""
    global scheduler
    if settings.enable_scheduler and scheduler is None:
        scheduler = create_scheduler()
        scheduler.start()
        print("Scheduler started")


def stop_scheduler():
    """Stop the scheduler."""
    global scheduler
    if scheduler is not None:
        scheduler.shutdown()
        scheduler = None
        print("Scheduler stopped")


def get_scheduled_jobs() -> list[dict]:
    """Get list of scheduled jobs."""
    if scheduler is None:
        return []

    jobs = []
    for job in scheduler.get_jobs():
        jobs.append(
            {
                "id": job.id,
                "name": job.name,
                "next_run_time": str(job.next_run_time) if job.next_run_time else None,
            }
        )
    return jobs
