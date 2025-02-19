# File: root_threader.py
# Path: root_threader.py

import threading
from outreach.email_outreach_processor import run_processor

###############################################################################
# GLOBAL CONFIGURATIONS
###############################################################################
GLOBAL_CONFIG = {
    # Path to your JSON file of recipients
    "recipients_dir": "outreach/dormant_customers",

    # Label for emails handled by the EmailAgent
    "outreach_label": "Demo",

    # If True, the EmailAgent will send emails; if False, it will save as drafts
    "send_mode": False, # Reset this to False after every run.

    # Prefix for log filenames (threads will append their name to this)
    "log_file_prefix": "dormant_sales",

    "stop_time": 20 # legacy arg, for when I needed this program to stop at a particular time
}

###############################################################################
# THREAD-SPECIFIC CONFIGS
# Each thread will process a specific slice of the recipients list.
###############################################################################
THREADS_CONFIG = [
    {
        "name": "T1",
        "begin_index": 0,
        "end_index": 1
    },
    {
        "name": "T2",
        "begin_index": 1,
        "end_index": 2
    },
    {
        "name": "T3",
        "begin_index": 2,
        "end_index": 3
    },
    {
        "name": "T4",
        "begin_index":3,
        "end_index": 4
    },
    {
        "name": "T5",
        "begin_index": 4,
        "end_index": 5
    },

]

###############################################################################
# LOGIC
###############################################################################

def main():
    # Extract global settings for easy reuse
    recipients_dir = GLOBAL_CONFIG["recipients_dir"]
    stop_time = GLOBAL_CONFIG["stop_time"]
    outreach_label = GLOBAL_CONFIG["outreach_label"]
    send_mode = GLOBAL_CONFIG["send_mode"]
    log_file_prefix = GLOBAL_CONFIG["log_file_prefix"]

    # Create a list to keep references to all threads
    threads = []

    # Build and start a thread for each slice
    for config in THREADS_CONFIG:
        t = threading.Thread(
            target=run_processor,
            args=(
                config["name"],
                recipients_dir,
                config["begin_index"],
                config["end_index"],
                stop_time,
                outreach_label,
                send_mode,
                log_file_prefix  # Pass the global log file prefix
            ),
            name=config["name"]  # name the thread for easier debugging
        )
        threads.append(t)

    # Start all threads
    for t in threads:
        t.start()

    # Wait for all threads to complete before exiting main
    for t in threads:
        t.join()

    print("All threads have finished.")


if __name__ == "__main__":
    main()