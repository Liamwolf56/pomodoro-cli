import datetime
import time
import os
import sys
import threading
import json
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Rich Imports
try:
    from rich.console import Console
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.text import Text
    from rich.columns import Columns
    from rich.live import Live
    from rich.prompt import Prompt
    from rich import box
    from rich.style import Style
    from rich.table import Table
except ImportError:
    # If Rich is not installed, the application cannot run.
    print("Rich library not found. Please install it using: pip install rich")
    sys.exit(1)

# --- Configuration and State Management ---

CONFIG_FILE = "world_clock_config.json"
# Global console object initialized in main()
console = None

def load_config():
    """Loads configuration and state from a JSON file."""
    # Note: The timer functionality here serves as the core Pomodoro component.
    default_config = {
        "main_zone": "Africa/Johannesburg",
        "secondary_zones": ["Europe/London", "America/New_York", "Asia/Tokyo"],
        "timer_duration_minutes": 25,
        "is_timer_paused": True,
        "timer_start_time": None,
        "timer_remaining_seconds": 25 * 60,
        "stopwatch_start_time": None,
        "stopwatch_elapsed_seconds": 0,
        "is_stopwatch_running": False,
        "alarm_time": None, # Format "HH:MM"
        "is_alarm_ringing": False,
        "is_24_hour_format": True,
        "show_help": False,
        "last_render_time": time.time(),
        "awaiting_input": False, # Flag to indicate if an interactive prompt is blocking the input thread
    }

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                # Ensure all default keys exist in case of partial load
                return {**default_config, **config}
        except (json.JSONDecodeError, IOError):
            # Fallback to default if file is corrupted
            return default_config
    return default_config

def save_config(config):
    """Saves the current configuration to a JSON file."""
    # We only save persistent settings (user preferences), not dynamic state.
    data_to_save = {
        "main_zone": config.get("main_zone"),
        "secondary_zones": config.get("secondary_zones"),
        "timer_duration_minutes": config.get("timer_duration_minutes"),
        "is_24_hour_format": config.get("is_24_hour_format"),
    }
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(data_to_save, f, indent=4)
    except IOError as e:
        if console:
            console.log(f"[bold red]Error saving config:[/bold red] {e}")


# --- Utility Functions ---

def format_time_duration(seconds):
    """Converts seconds into HH:MM:SS format."""
    seconds = int(seconds)
    if seconds < 0:
        seconds = 0
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def validate_timezone(zone_name):
    """Checks if a given timezone name is valid using Python's zoneinfo library."""
    try:
        ZoneInfo(zone_name)
        return True
    except ZoneInfoNotFoundError:
        return False

# --- Command Handlers (Interactive Prompts) ---
# These functions modify the config and use Prompt.ask, requiring the awaiting_input flag

def handle_zone_change(config, console):
    """Interactively changes the main time zone."""
    config["awaiting_input"] = True # Set flag immediately
    console.clear() # Clear the Live display completely

    console.print(Panel(
        Text("Change Time Zone", justify="center", style="bold cyan"),
        title="[bold cyan]Configuration[/]",
        border_style="cyan"
    ))

    new_zone = Prompt.ask(
        Text("Enter the new main time zone (e.g., Africa/Johannesburg, Europe/Paris)"),
        console=console,
        default=config["main_zone"]
    ).strip()

    if not new_zone:
        console.print("[yellow]Time zone change cancelled.[/]")
    elif validate_timezone(new_zone):
        config["main_zone"] = new_zone
        save_config(config)
        console.print(f"[bold green]Main Time Zone updated to:[/bold green] [cyan]{new_zone}[/cyan]")
    else:
        console.print(f"[bold red]Error:[/bold red] Time zone '[red]{new_zone}[/red]' is not valid. Please use IANA format (e.g., 'America/New_York').")

    Prompt.ask("\n[dim]Press ENTER to resume the clock...[/]", console=console, show_choices=False, default="")
    config["awaiting_input"] = False # Reset flag


def handle_timer_change(config, console):
    """Interactively changes the countdown timer duration (Pomodoro length)."""
    config["awaiting_input"] = True # Set flag immediately
    console.clear() # Clear the Live display completely

    console.print(Panel(
        Text("Change Timer Duration", justify="center", style="bold magenta"),
        title="[bold magenta]Countdown Timer (Pomodoro)[/]",
        border_style="magenta"
    ))

    try:
        new_duration_str = Prompt.ask(
            Text("Enter new timer duration in minutes (e.g., 5, 30)"),
            console=console,
            default=str(config["timer_duration_minutes"])
        ).strip()

        if not new_duration_str:
            console.print("[yellow]Timer duration change cancelled.[/]")
            return

        new_duration = int(new_duration_str)
        if new_duration <= 0:
            raise ValueError("Duration must be a positive number.")

        config["timer_duration_minutes"] = new_duration
        config["timer_remaining_seconds"] = new_duration * 60
        config["is_timer_paused"] = True
        config["timer_start_time"] = time.time() - (new_duration * 60) # Set start time cleanly
        save_config(config)
        console.print(f"[bold green]Timer duration updated to:[/bold green] [magenta]{new_duration} minutes[/magenta]. (Timer reset and paused)")

    except ValueError:
        console.print(f"[bold red]Error:[/bold red] Invalid input. Please enter a whole number of minutes.")

    Prompt.ask("\n[dim]Press ENTER to resume the clock...[/]", console=console, show_choices=False, default="")
    config["awaiting_input"] = False # Reset flag


def handle_alarm_set(config, console):
    """Interactively sets a new alarm time or cancels a ringing alarm."""
    if config.get("is_alarm_ringing"):
        config["is_alarm_ringing"] = False
        config["alarm_time"] = None
        # We don't set awaiting_input here because we aren't using Prompt.ask, 
        # and the main thread needs to resume quickly to update the display.
        console.print("[bold green]Alarm canceled and reset. Press ENTER to resume the clock.[/]")
        time.sleep(1) 
        return

    config["awaiting_input"] = True # Set flag immediately
    console.clear() # Clear the Live display completely

    console.print(Panel(
        Text("Set Alarm Time", justify="center", style="bold blue"),
        title="[bold blue]Alarm Clock[/]",
        border_style="blue"
    ))

    current_time_str = datetime.datetime.now(ZoneInfo(config["main_zone"])).strftime("%H:%M")

    new_alarm_time = Prompt.ask(
        Text(f"Enter new alarm time (HH:MM 24h format, currently {current_time_str}) or leave blank to cancel current alarm"),
        console=console,
        default=""
    ).strip()

    if not new_alarm_time:
        if config["alarm_time"]:
            config["alarm_time"] = None
            console.print("[bold green]Current alarm canceled.[/]")
        else:
            console.print("[yellow]Alarm setting cancelled.[/]")

        Prompt.ask("\n[dim]Press ENTER to resume the clock...[/]", console=console, show_choices=False, default="")
        config["awaiting_input"] = False
        return

    # Basic HH:MM validation (00:00 to 23:59)
    if re.match(r"^([01]\d|2[0-3]):([0-5]\d)$", new_alarm_time):
        config["alarm_time"] = new_alarm_time
        console.print(f"[bold green]Alarm set for:[/bold green] [blue]{new_alarm_time}[/blue] in zone [cyan]{config['main_zone']}[/cyan].")
    else:
        console.print("[bold red]Error:[/bold red] Invalid time format. Please use HH:MM (24-hour).")

    Prompt.ask("\n[dim]Press ENTER to resume the clock...[/]", console=console, show_choices=False, default="")
    config["awaiting_input"] = False # Reset flag


# --- Rendering Helpers (Rich Components) ---

def get_main_clock_panel(config):
    """Generates the main time panel based on the configuration."""
    # Ensure ZoneInfo lookup is safe
    try:
        tz = ZoneInfo(config["main_zone"])
    except ZoneInfoNotFoundError:
        return Panel(
            Text(f"ERROR: Invalid Time Zone: {config['main_zone']}", style="bold red"),
            title="[bold red]MAIN CLOCK ERROR[/]",
            border_style="red",
            box=box.HEAVY
        )

    now = datetime.datetime.now(tz)
    date_str = now.strftime("%A, %d %B %Y")

    time_format = "%H:%M:%S" if config["is_24_hour_format"] else "%I:%M:%S %p"
    time_str = now.strftime(time_format)

    # Big, stylized time display
    time_text = Text(time_str, style=Style(color="yellow", bold=True), justify="center")

    # Status/Alerts
    if config.get("is_alarm_ringing"):
        status_text = Text(f"!!! ALARM RINGING !!! Press 'A' + ENTER to silence.", style="bold blink red reverse", justify="center")
    elif config["alarm_time"]:
        status_text = Text(f"Alarm Set: {config['alarm_time']}", style="bold blue", justify="center")
    else:
        status_text = Text(f"Main Zone: {config['main_zone']}", style="bold cyan", justify="center")

    panel_content = Text.assemble(
        Text(date_str, style="dim white", justify="center"), "\n",
        time_text, "\n",
        status_text
    )

    return Panel(
        panel_content,
        title="[bold yellow]MAIN CLOCK[/]",
        border_style="yellow",
        box=box.HEAVY
    )

def get_secondary_clocks_panel(config):
    """Generates a panel showing secondary time zones."""
    tz_list = config.get("secondary_zones", [])

    if not tz_list:
        return Panel(
            Text("No secondary time zones configured.", style="dim"),
            title="[bold white]Other Zones[/]",
            border_style="dim"
        )

    table = Table(
        title="",
        show_header=False,
        padding=(0, 1),
        style="white",
        box=None
    )

    for zone_name in tz_list:
        try:
            tz = ZoneInfo(zone_name)
            now = datetime.datetime.now(tz)

            time_format = "%H:%M" if config["is_24_hour_format"] else "%I:%M %p"
            time_str = now.strftime(time_format)

            # Extract common name part (e.g., 'New York' from 'America/New_York')
            parts = zone_name.split('/')
            display_name = parts[-1].replace('_', ' ')

            table.add_row(
                Text(display_name, style="bold"),
                Text(time_str, style="green")
            )
        except ZoneInfoNotFoundError:
            table.add_row(
                Text(zone_name, style="bold red"),
                Text("INVALID", style="bold red")
            )

    return Panel(
        table,
        title="[bold white]Other Zones[/]",
        border_style="white",
        box=box.ROUNDED
    )

def get_timer_panel(config):
    """Generates the countdown timer and stopwatch panels."""

    now = time.time()

    # --- Countdown Timer Logic (Pomodoro) ---
    if not config["is_timer_paused"] and config["timer_start_time"] is not None:
        elapsed = now - config["timer_start_time"]
        total_duration = config["timer_duration_minutes"] * 60

        # Calculate new remaining time based on time elapsed since last start/unpause
        config["timer_remaining_seconds"] = max(0, total_duration - elapsed)

    remaining_seconds = config["timer_remaining_seconds"]

    if remaining_seconds <= 0:
        # Timer finished state
        status = Text("COMPLETE", style="bold blink red reverse")
        time_display = Text("00:00", style="bold red")
        config["is_timer_paused"] = True
        config["timer_remaining_seconds"] = 0
    else:
        status_style = "bold yellow" if config["is_timer_paused"] else "bold magenta"
        status_text = "PAUSED" if config["is_timer_paused"] else "RUNNING"
        status = Text(f"{status_text} (P to toggle, R to reset)", style=status_style)
        time_display = Text(format_time_duration(remaining_seconds), style="bold yellow")

    timer_panel = Panel(
        Text.assemble(
            time_display, "\n",
            status, "\n",
            Text(f"(Duration: {config['timer_duration_minutes']} min | T to change)", style="dim magenta")
        ),
        title="[bold magenta]COUNTDOWN (POMODORO)[/]",
        border_style="magenta",
        box=box.ROUNDED
    )

    # --- Stopwatch Logic ---
    if config["is_stopwatch_running"]:
        # If running, update elapsed time based on the time passed since the last render
        time_diff = now - config["last_render_time"]
        config["stopwatch_elapsed_seconds"] += time_diff

    elapsed_seconds = config["stopwatch_elapsed_seconds"]

    sw_status_style = "bold white" if config["is_stopwatch_running"] else "dim white"
    sw_status_text = "RUNNING" if config["is_stopwatch_running"] else "STOPPED"

    sw_panel = Panel(
        Text.assemble(
            Text(format_time_duration(elapsed_seconds), style="bold green"), "\n",
            Text(f"{sw_status_text} (S to toggle, W to reset)", style=sw_status_style)
        ),
        title="[bold green]STOPWATCH[/]",
        border_style="green",
        box=box.ROUNDED
    )

    # Update last render time for precise time tracking
    config["last_render_time"] = now

    return Columns([timer_panel, sw_panel], expand=True, equal=True)

def get_help_panel():
    """Returns the detailed help panel using a Rich Table for structure (Fixing Markup Errors)."""

    table = Table(
        title="Application Controls & Instructions",
        title_style="bold red",
        show_header=False,
        box=box.MINIMAL,
        padding=(0, 2)
    )

    # Add columns (Command, Action)
    table.add_column("Command", justify="left", style="bold")
    table.add_column("Action", justify="left")

    # --- Countdown Timer ---
    table.add_row(Text("[bold underline magenta]Countdown Timer (Pomodoro)[/]", style="bold magenta"), "")
    table.add_row(Text("[magenta]P[/magenta] + ENTER", style="bold"), "Pause/Resume the countdown timer.")
    table.add_row(Text("[magenta]R[/magenta] + ENTER", style="bold"), "Reset the countdown timer to its initial duration.")
    table.add_row(Text("[magenta]T[/magenta] + ENTER", style="bold"), "Change the timer duration (sets new time in minutes).")
    table.add_row() # Spacer

    # --- Stopwatch ---
    table.add_row(Text("[bold underline green]Stopwatch[/]", style="bold green"), "")
    table.add_row(Text("[green]S[/green] + ENTER", style="bold"), "Start or Stop (pause) the stopwatch.")
    table.add_row(Text("[green]W[/green] + ENTER", style="bold"), "Reset the stopwatch to zero.")
    table.add_row() # Spacer

    # --- Alarm Clock ---
    table.add_row(Text("[bold underline blue]Alarm Clock[/]", style="bold blue"), "")
    table.add_row(Text("[blue]A[/blue] + ENTER", style="bold"), "Set new alarm (HH:MM) / Silence ringing alarm.")
    table.add_row() # Spacer

    # --- Configuration & Clock ---
    table.add_row(Text("[bold underline cyan]Configuration & Clock[/]", style="bold cyan"), "")
    table.add_row(Text("[cyan]Z[/cyan] + ENTER", style="bold"), "Change the main time zone.")
    table.add_row(Text("[cyan]F[/cyan] + ENTER", style="bold"), "Toggle 12-hour (AM/PM) / 24-hour time format.")
    table.add_row(Text("[cyan]H[/cyan] + ENTER", style="bold"), "Hide this detailed help screen.")
    table.add_row(Text("[red]Q[/red] + ENTER", style="bold"), "Quit the application and save config.")

    return Panel(
        table,
        title="[bold red]Application Controls & Instructions[/]",
        border_style="red",
        box=box.HEAVY_HEAD
    )

def render_layout(config):
    """Assembles and returns the full Rich Layout, handling alarm checks and ringing."""

    # Check Alarm State before rendering
    if config["alarm_time"] and not config.get("is_alarm_ringing"):
        try:
            tz = ZoneInfo(config["main_zone"])
            now = datetime.datetime.now(tz)
            current_time_str = now.strftime("%H:%M")
            if current_time_str == config["alarm_time"]:
                config["is_alarm_ringing"] = True
                # --- ALARM ACTIVATION ---
                # When the alarm triggers, print the console bell character for sound.
                print('\a', end='', flush=True)

        except ZoneInfoNotFoundError:
            pass # Safety check for invalid main zone

    # --- CONTINUOUS RINGING ---
    # If the alarm is currently ringing, continuously send the console bell signal.
    if config.get("is_alarm_ringing"):
        # This will run 8 times per second until the user presses 'A' + ENTER.
        print('\a', end='', flush=True)

    layout = Layout(name="root")

    # 1. Handle Help Screen State
    if config.get("show_help"):
        layout.split(
            Layout(name="header", size=3),
            Layout(name="main")
        )
        layout["header"].update(Panel(
            Text("Press ENTER to resume the clock...", justify="center"),
            title="[bold dim]Help Displayed[/]",
            border_style="dim"
        ))
        # This now uses the robust Table implementation
        layout["main"].update(get_help_panel())
        return layout

    # 2. Main Content Layout
    layout.split(
        Layout(name="header", size=3),
        Layout(name="clocks"),
        Layout(name="timers")
    )

    # Header for status/initial message
    if config.get("init_message"):
        header_text = config["init_message"]
        config["init_message"] = None # Clear message after first display

    elif config.get("is_alarm_ringing"):
        header_text = Text("🚨 ALARM! Press 'A' + ENTER to silence.", style="bold blink red reverse", justify="center")
    else:
        header_text = Text(f"Main Zone: {config['main_zone']} | Pomodoro Timer: {config['timer_duration_minutes']} min. Press 'H' + Enter for help.", justify="center", style="dim")

    layout["header"].update(Panel(
        header_text,
        title="[bold yellow]⏰ Status[/]",
        border_style="yellow",
        box=box.MINIMAL
    ))

    # Clocks
    layout["clocks"].split_row(
        Layout(name="main_clock", ratio=2),
        Layout(name="secondary_clocks", ratio=1)
    )

    layout["clocks"]["main_clock"].update(get_main_clock_panel(config))
    layout["clocks"]["secondary_clocks"].update(get_secondary_clocks_panel(config))

    # Timers/Stopwatch
    layout["timers"].update(get_timer_panel(config))

    return layout


# --- Main Application Loop (Input and Threading) ---

def get_user_input(config, console, event):
    """Reads single-character commands from stdin in a separate thread."""
    while not event.is_set():
        try:
            # Block input reading if an interactive prompt is already running
            if config.get("awaiting_input"):
                time.sleep(0.5)
                continue

            # Use raw input for command entry
            next_action = input().strip().lower()

            if not next_action:
                # If user just pressed ENTER, and help was showing, hide it.
                if config.get("show_help"):
                    config["show_help"] = False
                continue

            # Process single character commands
            command = next_action[0].upper()

            if command == 'P': # Countdown Pause/Resume
                if config["timer_remaining_seconds"] > 0:
                    config["is_timer_paused"] = not config["is_timer_paused"]
                    if not config["is_timer_paused"]:
                        # Recalculate start time based on current remaining time
                        total_duration = config["timer_duration_minutes"] * 60
                        config["timer_start_time"] = time.time() - (total_duration - config["timer_remaining_seconds"])

            elif command == 'R': # Countdown Reset
                config["is_timer_paused"] = True
                config["timer_remaining_seconds"] = config["timer_duration_minutes"] * 60
                config["timer_start_time"] = time.time() - config["timer_remaining_seconds"]

            elif command == 'T': # Countdown Change Duration (Interactive)
                handle_timer_change(config, console)

            elif command == 'S': # Stopwatch Start/Stop
                config["is_stopwatch_running"] = not config["is_stopwatch_running"]

            elif command == 'W': # Stopwatch Reset
                config["is_stopwatch_running"] = False
                config["stopwatch_elapsed_seconds"] = 0

            elif command == 'A': # Alarm Set/Silence (Interactive)
                handle_alarm_set(config, console)

            elif command == 'Z': # Change Main Zone (Interactive)
                handle_zone_change(config, console)

            elif command == 'F': # Toggle Format
                config["is_24_hour_format"] = not config["is_24_hour_format"]
                save_config(config)

            elif command == 'H': # Help
                config["show_help"] = not config["show_help"]

            elif command == 'Q': # Quit
                event.set()
                break

        except EOFError:
            event.set()
        except Exception:
            # Ignore other input errors silently to keep the clock running
            pass


def main():
    """Main function to run the interactive clock application."""
    global console
    console = Console()

    # 1. Load Configuration
    config = load_config()

    # 2. Set Initial Message
    config["init_message"] = f"Starting Clock. Main Zone: {config['main_zone']}. Pomodoro Timer: {config['timer_duration_minutes']} min. Press 'H' + Enter for help."

    # 3. Setup non-blocking input thread
    stop_event = threading.Event()
    input_thread = threading.Thread(target=get_user_input, args=(config, console, stop_event), daemon=True)
    input_thread.start()

    # 4. Start Live Rich Display
    try:
        # 8 refreshes per second for smooth timer/stopwatch updates
        with Live(render_layout(config), refresh_per_second=8, screen=True, console=console) as live:
            while not stop_event.is_set():
                # Only update the screen if the app is NOT awaiting user input via a Prompt
                if not config.get("awaiting_input"):
                    live.update(render_layout(config))
                time.sleep(0.125)

    except KeyboardInterrupt:
        # Graceful exit if Ctrl+C is pressed
        pass

    # 5. Cleanup
    stop_event.set()
    input_thread.join(timeout=1)
    save_config(config)

    console.clear()
    console.print(f"[bold green]Configuration saved.[/] Time Manager closed. Goodbye!")


if __name__ == "__main__":
    main()
