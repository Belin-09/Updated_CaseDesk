from apscheduler.schedulers.background import BackgroundScheduler
import uuid
from routers.upload import run_folder_scan

def run_daily_scan():
    """
    Trigger the background folder scan daily.
    """
    root_path = r"\\192.168.30.6\Forensic Lab\Case_data"
    scan_id = str(uuid.uuid4())
    print(f"Triggering daily auto-update scan for {root_path} (ID: {scan_id})")
    
    # Run the existing scan logic in a fire-and-forget manner
    # It runs in a ThreadPoolExecutor inside run_folder_scan.
    try:
        run_folder_scan(root_path, "system-auto", scan_id)
    except Exception as e:
        print(f"Daily auto-update scan failed to start: {e}")

def start_scheduler():
    scheduler = BackgroundScheduler()
    # Run every day at 10:00 AM
    scheduler.add_job(run_daily_scan, 'cron', hour=10, minute=0)
    scheduler.start()
    print("Auto-update scheduler started: daily at 10:00 AM")
