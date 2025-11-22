Summary of world_clock.py: World Clock and Pomodoro TUI

This document summarizes the Python application, world_clock.py, which utilizes the rich library to create an interactive, multi-functional Terminal User Interface (TUI) for time management, combining a world clock, a Pomodoro timer, and a stopwatch.

1. Core Application Goals

The primary goal is to provide a comprehensive, real-time, persistent time management dashboard directly within the terminal, allowing the user to manage time zones, focus sessions (Pomodoro), and track arbitrary time intervals (Stopwatch) through simple single-key commands.

2. Technical Architecture (The Rich/Threading Model)

The application uses a crucial architecture built around two threads to achieve non-blocking, real-time updates:

A. Main Thread (Rendering Loop)

Tool: rich.live.Live

Purpose: The main thread is responsible for continuously rendering the application's display at 8 frames per second (refresh_per_second=8).

Function: It calls render_layout(config) repeatedly, displaying the current time, timer status, and dashboard layout.

Alarm Check: Crucially, the main thread continuously checks if the current time matches config["alarm_time"] and updates config["is_alarm_ringing"] if a match is found.

B. Input Thread (get_user_input)

Tool: Standard Python threading and the built-in input() function.

Purpose: This thread runs perpetually in the background, waiting for the user to type a command (like P, R, or A) and press Enter.

Interaction: When a command is received, it updates the shared config dictionary (e.g., toggling the stopwatch).

C. Input Synchronization (The Key Fix)

The application uses the config["awaiting_input"] flag to solve a common TUI threading problem:

Problem: Interactive commands (like setting the alarm time with 'A') must use rich.prompt.Prompt.ask. This function blocks the input thread. If the rendering thread (Live) tries to update the display at the same time, it can cause screen corruption or make the prompt unusable.

Solution: Before calling Prompt.ask (in functions like handle_alarm_set):

The command handler sets config["awaiting_input"] = True.

It calls console.clear() to blank the screen.

The main thread sees the flag is True and temporarily stops rendering.

The prompt runs cleanly.

The flag is reset to False, allowing the main thread to resume rendering the updated dashboard.

3. Core Functions and Features

The application state is managed by a dictionary, config, which is loaded from and saved to world_clock_config.json (for persistent settings).

Feature

Commands

State Variables

Description

World Clock

Z (Change Zone), F (Toggle Format)

main_zone, secondary_zones, is_24_hour_format

Displays the current time in the user's primary time zone and secondary zones. The display format (12h/24h) is toggled with F.

Pomodoro Timer

P (Pause/Resume), R (Reset), T (Set Duration)

timer_remaining_seconds, is_timer_paused, timer_duration_minutes

Implements a countdown timer (default 25 minutes). State is managed precisely by calculating elapsed time since the last action, ensuring accuracy even when paused. T uses an interactive prompt to set a new Pomodoro duration.

Stopwatch

S (Start/Stop), W (Reset)

stopwatch_elapsed_seconds, is_stopwatch_running

Tracks time elapsed continuously. Accuracy is maintained by calculating the difference between successive Live renders and adding that to the elapsed time.

Alarm Clock

A (Set/Silence)

alarm_time, is_alarm_ringing

This was the focus of the recent fix. The application checks the current time against alarm_time every refresh. If they match, is_alarm_ringing is set to True, and the terminal bell sound (\a) is continuously triggered
