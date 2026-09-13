import os
import time
import sqlite3
import psutil
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.console import Console

DB_NAME = "network_traffic.db"

def init_db():

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS process_traffic (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            process_name TEXT,
            pid INTEGER,
            bytes_sent INTEGER,
            bytes_recv INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def log_traffic_to_db(process_data):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        for proc in process_data:
            cursor.execute('''
                INSERT INTO process_traffic (process_name, pid, bytes_sent, bytes_recv)
                VALUES (?, ?, ?, ?)
            ''', (proc['name'], proc['pid'], proc['bytes_sent'], proc['bytes_recv']))
        conn.commit()
        conn.close()
    except Exception:
        pass

def get_process_network_traffic():
    processes = []
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            connections = proc.net_connections()
            if connections:
                io_counters = proc.io_counters()
                processes.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'] or 'Unknown',
                    'bytes_sent': getattr(io_counters, 'write_bytes', 0),
                    'bytes_recv': getattr(io_counters, 'read_bytes', 0)
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    processes.sort(key=lambda x: (x['bytes_sent'] + x['bytes_recv']), reverse=True)
    return processes[:10]

def build_dashboard(processes, net_io_1, net_io_2, time_delta):
    table = Table(title="Top Network Consuming Processes", expand=True)
    table.add_column("PID", style="cyan", justify="right")
    table.add_column("Process Name", style="bold green")
    table.add_column("Sent Data (Total)", style="magenta")
    table.add_column("Received Data (Total)", style="blue")

    bytes_sent_sec = (net_io_2.bytes_sent - net_io_1.bytes_sent) / time_delta if time_delta > 0 else 0
    bytes_recv_sec = (net_io_2.bytes_recv - net_io_1.bytes_recv) / time_delta if time_delta > 0 else 0

    upload_str = f"{bytes_sent_sec / 1024:.2f} KB/s"
    download_str = f"{bytes_recv_sec / 1024:.2f} KB/s"

    for proc in processes:
        table.add_row(
            str(proc['pid']),
            proc['name'],
            f"{proc['bytes_sent'] / (1024 * 1024):.2f} MB",
            f"{proc['bytes_recv'] / (1024 * 1024):.2f} MB"
        )

    summary = f"[bold white]Live Traffic Speed:[/bold white] ⬆ Upload: [magenta]{upload_str}[/magenta] | ⬇ Download: [blue]{download_str}[/blue]"
    return Panel(table, title=summary, border_style="bold bright_blue")

def main():
    init_db()
    console = Console()
    console.print("[bold yellow][*] Starting Terminal Network Traffic Monitor... (Press Ctrl+C to stop)[/bold yellow]\n")

    last_io = psutil.net_io_counters()
    last_time = time.time()

    try:
        with Live(console=console, refresh_per_second=1) as live:
            while True:
                time.sleep(1)
                current_time = time.time()
                current_io = psutil.net_io_counters()
                time_delta = current_time - last_time

                processes = get_process_network_traffic()
                dashboard = build_dashboard(processes, last_io, current_io, time_delta)
                
                live.update(dashboard)
                log_traffic_to_db(processes)

                last_io = current_io
                last_time = current_time

    except KeyboardInterrupt:
        console.print("\n[bold red][!] Monitoring stopped. Logs stored in 'network_traffic.db'.[/bold red]")

if __name__ == "__main__":
    main()