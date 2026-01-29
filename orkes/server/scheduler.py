
import schedule
import time
import threading

def job():
    print("I'm working...")

def run_scheduler():
    schedule.every(10).seconds.do(job)
    while True:
        schedule.run_pending()
        time.sleep(1)

def start_scheduler():
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()
