import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime

async def my_task():
    print("Task running")

async def main():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(my_task, IntervalTrigger(seconds=2), id="test1", next_run_time=None)
    scheduler.add_job(my_task, IntervalTrigger(seconds=2), id="test2")
    scheduler.start()
    
    for job in scheduler.get_jobs():
        print(f"Job {job.id} next run: {job.next_run_time}")

asyncio.run(main())
