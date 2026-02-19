import sys
import time
import subprocess
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class RestartHandler(FileSystemEventHandler):
    def __init__(self, script_path):
        self.script_path = script_path
        self.process = None
        self.restart()

    def restart(self):
        if self.process:
            print(f"[Watcher] Stopping process {self.process.pid}...")
            self.process.terminate()
            self.process.wait()
        
        print(f"[Watcher] Starting {self.script_path}...")
        self.process = subprocess.Popen([sys.executable, self.script_path])

    def on_modified(self, event):
        if event.is_directory:
            return
        
        filename = event.src_path
        if filename.endswith(".py") or filename.endswith(".yaml") or filename.endswith(".env"):
             # Ignore common noise
            if "__pycache__" in filename or ".git" in filename or "logs" in filename:
                return
            
            print(f"[Watcher] Change detected in {filename}")
            self.restart()

if __name__ == "__main__":
    script_to_run = "main.py"
    
    if not os.path.exists(script_to_run):
        print(f"Error: {script_to_run} not found.")
        sys.exit(1)

    event_handler = RestartHandler(script_to_run)
    observer = Observer()
    observer.schedule(event_handler, path=".", recursive=True)
    observer.start()

    print(f"[Watcher] Watching for changes to restart {script_to_run}...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        if event_handler.process:
            event_handler.process.terminate()
    observer.join()
