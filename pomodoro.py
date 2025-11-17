import argparse
import time
import json
import os
import sys
from datetime import timedelta
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
from rich.layout import Layout
from rich.panel import Panel

# --- Configuration ---
LOG_FILE = "pomodoro_log.json"
API_KEY = "" 

# --- Utility Functions ---

def load_progress():
    """Loads total work time from the log file."""
    try:
        with open(LOG_FILE, 'r') as f:
            data = json.load(f)
            return data.get('total_work_seconds', 0)
    except (FileNotFoundError, json.JSONDecodeError):
        return 0

def save_progress(new_work_seconds):
    """Saves updated total work time to the log file."""
    total_seconds = load_progress() + new_work_seconds
    data = {'total_work_seconds': total_seconds}
    with open(LOG_FILE, 'w') as f:
        json.dump(data, f, indent=4)
    return total_seconds

def play_alert():
    """
    Plays an alert sound using the terminal bell character.
    This is the most reliable method in WSL.
    """
    sys.stdout.write('\007')
    sys.stdout.flush()
    print("\n[Alert] Phase complete!")

def make_layout() -> Layout:
    """Define the overall layout for Rich."""
    layout = Layout(name="root")
    layout.split(
        Layout(name="header", size=3),
        Layout(name="main"),
        Layout(name="footer", size=5)
    )
    return layout

def update_header(layout: Layout, phase: str, duration_minutes: int):
    """Update the header with current phase information."""
    color = "bold yellow" if phase == "Work" else "bold green"
    header_content = f"[{color}]Pomodoro Timer CLI[/]\n[white]{phase} Phase: {duration_minutes} Minutes[/]"
    layout["header"].update(Panel(header_content, title="🍅 Session Info", border_style="dim"))

def update_footer(layout: Layout, total_seconds: int):
    """Update the footer with total tracked work time."""
    total_time = str(timedelta(seconds=total_seconds))
    footer_content = f"[bold cyan]Total Tracked Work Time: {total_time}[/]"
    layout["footer"].update(Panel(footer_content, title="📊 Progress Log", border_style="dim"))

def run_timer(duration_seconds: int, phase: str, layout: Layout):
    """Runs the rich animated countdown for a specific phase."""
    task_columns = [
        TextColumn("[bold magenta]{task.description}", justify="right"),
        BarColumn(bar_width=None),
        "[progress.percentage]{task.percentage:>3.0f}%",
        "•",
        TimeRemainingColumn(),
        "•",
        TextColumn("[green]{task.completed}/{task.total}s"),
    ]
    console = Console()
    with Progress(*task_columns, console=console, transient=True) as progress:
        task = progress.add_task(f"[bold white]{phase} Countdown...", total=duration_seconds)
        while not progress.finished:
            progress.update(task, advance=1)
            time.sleep(1)

def main():
    parser = argparse.ArgumentParser(description="Customizable Pomodoro Timer CLI (with Rich visualization and logging).")
    
    # Fix: use dest="work_duration" and dest="break_duration" to avoid Python keyword conflicts
    parser.add_argument('-w', '--work', dest="work_duration", type=int, default=25,
                        help="Duration of the work session in minutes (default: 25).")
    
    parser.add_argument('-b', '--break', dest="break_duration", type=int, default=5,
                        help="Duration of the break session in minutes (default: 5).")
                        
    args = parser.parse_args()

    work_duration = args.work_duration
    break_duration = args.break_duration 

    work_seconds = work_duration * 60
    break_seconds = break_duration * 60

    console = Console()
    layout = make_layout()
    
    total_tracked_seconds = load_progress()
    update_footer(layout, total_tracked_seconds)
    console.print(layout)

    try:
        # Work Phase
        update_header(layout, "Work", work_duration)
        run_timer(work_seconds, "Work", layout)
        total_tracked_seconds = save_progress(work_seconds)
        update_footer(layout, total_tracked_seconds)
        console.print(Panel("[bold yellow]🚨 WORK TIME COMPLETE! Take a break.[/]", border_style="yellow"))
        play_alert()

        time.sleep(2) 

        # Break Phase
        update_header(layout, "Break", break_duration)
        run_timer(break_seconds, "Break", layout)
        console.print(Panel("[bold green]✅ BREAK TIME COMPLETE! Ready for the next session.[/]", border_style="green"))
        play_alert()

    except KeyboardInterrupt:
        console.print("\n[bold red]Timer interrupted. Session stopped.[/]")
        
    finally:
        console.print(layout) 

if __name__ == "__main__":
    main()
