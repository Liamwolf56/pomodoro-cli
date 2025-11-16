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
API_KEY = "" # The API key is not used for local Python script logic, but kept for consistency if it were an interactive LLM app.

# --- Utility Functions ---

def load_progress():
    """Loads total work time from the log file."""
    try:
        with open(LOG_FILE, 'r') as f:
            data = json.load(f)
            return data.get('total_work_seconds', 0)
    except (FileNotFoundError, json.JSONDecodeError):
        # File doesn't exist or is corrupted, start fresh
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
    Plays an alert sound.
    Tries playsound first (requires 'pip install playsound' and a system-level sound library).
    Falls back to the terminal bell character (\007) if playsound fails or is not installed.
    """
    try:
        # NOTE: playsound is often problematic in WSL environments without proper setup.
        # If it doesn't work, comment out this block and rely on the bell character.
        # This requires an actual sound file path, which isn't provided here, so we'll use a placeholder structure.
        # If you install playsound and have a .wav file, uncomment this:
        # from playsound import playsound
        # playsound('/path/to/your/alert.mp3', block=False)
        
        # Simple terminal bell fallback (guaranteed to work in most terminals)
        sys.stdout.write('\007')
        sys.stdout.flush()
        
    except Exception as e:
        # Fallback to the terminal bell character
        sys.stdout.write('\007')
        sys.stdout.flush()
        print(f"\n[Alert] Playsound failed (or is not installed/configured). Using terminal bell: {e}")

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


# --- Main Timer Logic ---

def run_timer(duration_seconds: int, phase: str, layout: Layout):
    """Runs the rich animated countdown for a specific phase."""
    
    # Custom columns for the progress bar display
    task_columns = [
        TextColumn("[bold magenta]{task.description}", justify="right"),
        BarColumn(bar_width=None),
        "[progress.percentage]{task.percentage:>3.0f}%",
        "•",
        TimeRemainingColumn(),
        "•",
        TextColumn("[green]{task.completed}/{task.total}s"),
    ]

    with Progress(*task_columns, console=Console()) as progress:
        task = progress.add_task(f"[bold white]{phase} Countdown...", total=duration_seconds)

        while not progress.finished:
            # Update the layout display
            layout["main"].update(progress)
            
            progress.update(task, advance=1)
            time.sleep(1)


def main():
    """Parses arguments, initializes components, and runs the Pomodoro sequence."""
    
    parser = argparse.ArgumentParser(description="Customizable Pomodoro Timer CLI (with Rich visualization and logging).")
    parser.add_argument('-w', '--work', type=int, default=25,
                        help="Duration of the work session in minutes (default: 25).")
    parser.add_argument('-b', '--break', type=int, default=5,
                        help="Duration of the break session in minutes (default: 5).")
    args = parser.parse_args()

    work_duration = args.work
    break_duration = args.break
    
    work_seconds = work_duration * 60
    break_seconds = break_duration * 60

    console = Console()
    layout = make_layout()
    
    # Initial status display
    total_tracked_seconds = load_progress()
    update_footer(layout, total_tracked_seconds)
    console.print(layout)

    try:
        # --- Work Phase ---
        update_header(layout, "Work", work_duration)
        run_timer(work_seconds, "Work", layout)
        
        # Log and alert after work
        total_tracked_seconds = save_progress(work_seconds)
        update_footer(layout, total_tracked_seconds)
        console.print(Panel("[bold yellow]🚨 WORK TIME COMPLETE! Take a break.[/]", border_style="yellow"))
        play_alert()

        # --- Break Phase ---
        update_header(layout, "Break", break_duration)
        run_timer(break_seconds, "Break", layout)
        
        # Alert after break
        console.print(Panel("[bold green]✅ BREAK TIME COMPLETE! Ready for the next session.[/]", border_style="green"))
        play_alert()

    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        console.print("\n[bold red]Timer interrupted. Session stopped.[/]")
        
    finally:
        console.print(layout) # Show final state of the log

if __name__ == "__main__":
    main()
