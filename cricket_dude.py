from __future__ import annotations

from ast import main
import json
import sys
import time
from dataclasses import dataclass
from typing import Any
import requests
import os
import time
from rich import box
from rich.align import Align
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

# =========================
# PLATFORM INPUT
# =========================

try:
    import select
    import termios
    import tty

    IS_WINDOWS = False

except ImportError:
    import msvcrt

    IS_WINDOWS = True

# =========================
# CONFIG
# =========================

APP_VERSION = "1.5"

REFRESH_SECONDS = 5
REQUEST_TIMEOUT = 10
CACHE_SECONDS = 5

CRICBUZZ_URL = "https://www.cricbuzz.com/cricket-match/live-scores"

USER_AGENT = "cricket-dude/1.1"

console = Console(
    force_terminal=True,
    legacy_windows=False
)

TEAM_COLORS = {
    "RCB": "bright_red",
    "CSK": "bright_yellow",
    "MI": "bright_blue",
    "KKR": "magenta",
    "SRH": "orange1",
    "DC": "bright_cyan",
    "GT": "cyan",
    "RR": "bright_magenta",
    "PBKS": "red",
    "LSG": "bright_cyan",
    "IND": "blue",
    "AUS": "yellow",
    "ENG": "white",
    "PAK": "green",
}

# =========================
# DATA MODEL
# =========================

@dataclass(frozen=True)
class Match:
    description: str
    status: str
    team_one: str
    team_two: str
    team_one_score: str = ""
    team_two_score: str = ""
    is_live: bool = False
    series: str = ""
    match_state: str = ""
    venue: str = ""
    match_id: int | None = None

# =========================
# LOADING SCREEN
# =========================

def show_loading_screen():

    frames = [
        "▰▱▱▱▱▱▱",
        "▰▰▱▱▱▱▱",
        "▰▰▰▱▱▱▱",
        "▰▰▰▰▱▱▱",
        "▰▰▰▰▰▱▱",
        "▰▰▰▰▰▰▱",
        "▰▰▰▰▰▰▰",
    ]

    glow_colors = [
        "bright_green",
        "bright_cyan",
        "bright_magenta",
        "bright_yellow",
    ]

    messages = [
        "Connecting To Cricbuzz Servers",
        "Fetching Live Match Data",
        "Loading Match Center",
        "Preparing Live Scoreboards",
        "Launching Cricket Dude",
    ]

    with Live(screen=True, refresh_per_second=30) as live:

        for message in messages:

            for i in range(20):

                color = glow_colors[i % len(glow_colors)]

                logo = Text(
                    """
 ██████╗██████╗ ██╗ ██████╗██╗  ██╗███████╗████████╗
██╔════╝██╔══██╗██║██╔════╝██║ ██╔╝██╔════╝╚══██╔══╝
██║     ██████╔╝██║██║     █████╔╝ █████╗     ██║
██║     ██╔══██╗██║██║     ██╔═██╗ ██╔══╝     ██║
╚██████╗██║  ██║██║╚██████╗██║  ██╗███████╗   ██║
 ╚═════╝╚═╝  ╚═╝╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝   ╚═╝
                    """,
                    style=f"bold {color}",
                )

                spinner = Spinner("dots", style=color)

                progress = Text(
                    frames[i % len(frames)],
                    style=f"bold {color}",
                    justify="center",
                )

                status = Text.assemble(
                    ("⬤ ", f"bold {color}"),
                    (message, "bold white"),
                )

                footer = Text.assemble(
                    ("LIVE CRICKET EXPERIENCE", "bold white"),
                    (" • ", "dim"),
                    (f"VERSION {APP_VERSION}", f"bold {color}"),
                )

                content = Group(
                    Align.center(logo),
                    Text(""),
                    Align.center(spinner),
                    Text(""),
                    Align.center(status),
                    Text(""),
                    Align.center(progress),
                    Text(""),
                    Align.center(footer),
                )

                panel = Panel(
                    content,
                    border_style=color,
                    padding=(1, 4),
                    title="[bold white]INITIALIZING[/bold white]",
                    subtitle=f"[bold {color}]MATCH ENGINE[/bold {color}]",
                )

                live.update(panel)

                time.sleep(0.06)

# =========================
# PROVIDER
# =========================

class CricbuzzProvider:
    def __init__(self):

        self.session = requests.Session()

        self.session.headers.update({
            "User-Agent": USER_AGENT
        })

        self.cache = None

    def get_matches(self, mode="live"):

        now = time.monotonic()

        if self.cache and now - self.cache[0] < CACHE_SECONDS:
            matches = self.cache[1]

        else:
            try:

                response = self.session.get(
                    CRICBUZZ_URL,
                    timeout=REQUEST_TIMEOUT,
                )

            except requests.RequestException:

                raise ConnectionError(
                    "No internet connection"
                )

            response.raise_for_status()

            matches = self._parse_matches(response.text)

            self.cache = (now, matches)

        if mode == "live":
            return [m for m in matches if m.is_live]

        if mode == "recent":
            return [
                m for m in matches
                if m.match_state.lower() == "complete"
            ]

        if mode == "ipl":
            return [
                m for m in matches
                if "ipl" in m.series.lower()
                or "indian premier league" in m.series.lower()
            ]

        return [
            m for m in matches
            if m.match_state.lower() in {"preview", "upcoming"}
        ]

    def _parse_matches(self, html):

        text = (
            html
            .replace('\\"', '"')
            .replace("\\/", "/")
            .replace("\\n", "\n")
        )

        marker = '"matchesList":{"matches":'

        idx = text.find(marker)

        if idx == -1:
            return []

        start = idx + len(marker)

        depth = 0
        in_string = False
        escaped = False

        end = start

        for i in range(start, len(text)):

            char = text[i]

            if in_string:

                if escaped:
                    escaped = False

                elif char == "\\":
                    escaped = True

                elif char == '"':
                    in_string = False

                continue

            if char == '"':
                in_string = True

            elif char == '[':
                depth += 1

            elif char == ']':
                depth -= 1

                if depth == 0:
                    end = i + 1
                    break

        raw_matches = json.loads(text[start:end])

        matches = []

        for item in raw_matches:

            match = item.get("match", {})
            info = match.get("matchInfo", {})
            score_data = match.get("matchScore", {})

            if not info:
                continue

            t1 = info.get("team1", {}).get("teamSName", "T1")
            t2 = info.get("team2", {}).get("teamSName", "T2")

            s1 = self._format_score(
                score_data.get("team1Score", {})
            )

            s2 = self._format_score(
                score_data.get("team2Score", {})
            )

            state = str(info.get("state") or "")
            
            matches.append(
                Match(
                    description=f"{t1} vs {t2}",
                    status=info.get("status", "Scheduled"),
                    team_one=t1,
                    team_two=t2,
                    team_one_score=s1,
                    team_two_score=s2,
                    is_live=state.lower() not in {
                        "preview",
                        "complete",
                        "upcoming",
                    },
                    series=info.get("seriesName", ""),
                    match_state=state,

                    venue=info.get(
                        "venueInfo",
                        {}
                    ).get(
                        "ground",
                        ""
                    ),

                    match_id=info.get("matchId"),
                )
            )

        return matches

    def _format_score(self, score_dict):
        innings = []

        for innings_data in score_dict.values():

            if (
                isinstance(innings_data, dict)
                and "runs" in innings_data
            ):
                innings.append(innings_data)

        innings.sort(
            key=lambda x: int(x.get("inningsId") or 0)
        )

        parts = []

        for inn in innings:

            runs = inn.get("runs", 0)
            wickets = inn.get("wickets", 0)
            overs = inn.get("overs", 0)

            parts.append(
                f"{runs}/{wickets} ({overs} ov)"
            )

        return " & ".join(parts)

    def get_over_data(self, match_id):

        try:

            import re

            url = (
                "https://www.cricbuzz.com/"
                f"api/html/cricket-match/commentary/{match_id}"
            )

            response = self.session.get(
                url,
                timeout=REQUEST_TIMEOUT
            )

            html = response.text

            balls = re.findall(
                r'class=\"cb-com-ln\">(.*?)<',
                html
            )

            cleaned = []

            for ball in balls[:6]:

                ball = ball.strip()

                if ball:
                    cleaned.append(ball)

            cleaned.reverse()

            return cleaned[:6]

        except Exception:

            return []

# =========================
# KEYBOARD INPUT
# =========================

def get_key():

    if IS_WINDOWS:
        #
        if not msvcrt.kbhit():

            time.sleep(0.05)

            return None

        ch = msvcrt.getch()

        if ch in [b"\x00", b"\xe0"]:

            ch2 = msvcrt.getch()

            return {
                b"H": "\x1b[A",
                b"P": "\x1b[B",
            }.get(ch2)

        if ch == b"\r":
            return "\r"

        if ch == b"\x1b":
            return "\x1b"

        try:
            return ch.decode("utf-8")

        except:
            return None

    else:

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)

        try:
            tty.setraw(fd)

            if select.select([sys.stdin], [], [], 0.05)[0]:

                c = sys.stdin.read(1)

                if c == "\x1b":
                    if select.select([sys.stdin], [], [], 0.05)[0]:
                        c += sys.stdin.read(2)

                return c

        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    return None

# =========================
# MAIN APP
# =========================

class CricketDude:
    def __init__(self):

        self.provider = CricbuzzProvider()

        self.menu_options = [
            "Live Matches",
            "Recent Results",
            "Upcoming Matches",
            "IPL Matches",
            "Exit",
        ]

        self.selected_idx = 0
        self.current_mode = None
        self.current_data = []
        self.last_refresh = time.monotonic()

    def team_text(self, team):

        color = TEAM_COLORS.get(team.upper(), "white")

        return Text(team, style=f"bold {color}")

    def live_dot(self, match):

        if match.is_live:
            return Text(
                "● LIVE",
                style="bold bright_green"
            )

        return Text(
            "○ OFFLINE",
            style="dim"
        )

    def generate_over_log(self, match):

        table = Table.grid(expand=False)

        for _ in range(6):
            table.add_column(width=5)

        balls = []

        if match.is_live and match.match_id:

            balls = self.provider.get_over_data(
                match.match_id
            )

        if not balls:

            balls = ["-", "-", "-", "-", "-", "-"]

        rendered = []

        for ball in balls:

            style = "white"

            value = str(ball).upper()

            if value == "6":
                style = "bold bright_green"

            elif value == "4":
                style = "bold bright_cyan"

            elif value in {"W", "WICKET"}:
                style = "bold bright_red"

            elif value in {"•", "."}:
                style = "bold bright_white"

            rendered.append(
                Panel(
                    Text(
                        str(ball),
                        justify="center",
                        style=style
                    ),
                    border_style=style,
                    padding=(0, 1)
                )
            )

        while len(rendered) < 6:

            rendered.append(
                Panel(
                    "-",
                    border_style="dim"
                )
            )

        table.add_row(*rendered[:6])

        return table

    def make_scoreboard(self, match):

        header = Text.assemble(
            self.team_text(match.team_one),
            "  VS  ",
            self.team_text(match.team_two),
        )

        grid = Table.grid(expand=True)

        grid.add_column(justify="right", ratio=1)
        grid.add_column(justify="center", width=5)
        grid.add_column(justify="left", ratio=1)

        grid.add_row(
            Text(
                match.team_one_score or "Yet to bat",
                style="bold yellow"
            ),

            "⚡",

            Text(
                match.team_two_score or "Yet to bat",
                style="bold yellow"
            ),
        )

        body = Table.grid(padding=1)

        body.add_column(justify="center")

        body.add_row("")
        body.add_row(header)
        body.add_row(self.live_dot(match))
        body.add_row("")

        body.add_row(grid)

        body.add_row("")

        body.add_row(
            Text(
                "🧍 Live batter data loading...",
                style="bold white",
                justify="center"
            )
        )

        body.add_row("")

        body.add_row(
            self.generate_over_log(match)
        )

        if match.series:

            body.add_row("")

            body.add_row(
                Text(
                    match.series,
                    style="bold bright_black",
                    justify="center"
                )
            )

        if match.venue:

            body.add_row(
                Text(
                    f"📍 {match.venue}",
                    style="bold bright_black",
                    justify="center"
                )
            )

        status_style = "bold bright_green"

        status_text = match.status.lower()

        if "rain" in status_text:
            status_style = "bold bright_blue"

        elif "lunch" in status_text:
            status_style = "bold bright_yellow"

        elif "tea" in status_text:
            status_style = "bold bright_magenta"

        elif "stump" in status_text:
            status_style = "bold bright_red"

        elif "break" in status_text:
            status_style = "bold bright_cyan"

        body.add_row("")

        body.add_row(
            Panel(
                Text(
                    match.status,
                    style=status_style,
                    justify="center"
                ),
                border_style=status_style,
                padding=(0, 2)
            )
        )

        return Panel(
            Align.center(body),
            title="[bold bright_green]● LIVE SCOREBOARD[/bold bright_green]",
            border_style="bright_green",
            padding=(1, 2)
        )

    def generate_menu(self):

        layout = Table.grid(expand=True)

        layout.add_column(justify="center")

        logo = Text("""
        ██████╗██████╗ ██╗ ██████╗██╗  ██╗███████╗████████╗
        ██╔════╝██╔══██╗██║██╔════╝██║ ██╔╝██╔════╝╚══██╔══╝
        ██║     ██████╔╝██║██║     █████╔╝ █████╗     ██║
        ██║     ██╔══██╗██║██║     ██╔═██╗ ██╔══╝     ██║
        ╚██████╗██║  ██║██║╚██████╗██║  ██╗███████╗   ██║
        ╚═════╝╚═╝  ╚═╝╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝   ╚═╝

        ██████╗ ██╗   ██╗██████╗ ███████╗
        ██╔══██╗██║   ██║██╔══██╗██╔════╝
        ██║  ██║██║   ██║██║  ██║█████╗
        ██║  ██║██║   ██║██║  ██║██╔══╝
        ██████╔╝╚██████╔╝██████╔╝███████╗
        ╚═════╝  ╚═════╝ ╚═════╝ ╚══════╝
        """, style="bold bright_green")

        subtitle = Text.assemble(
            ("LIVE CRICKET TERMINAL", "bold bright_white"),
            ("  •  ", "dim"),
            (f"VERSION {APP_VERSION}", "bold bright_cyan")
        )

        layout.add_row("")
        layout.add_row(Align.center(logo))
        layout.add_row(Align.center(subtitle))
        layout.add_row("")

        for idx, option in enumerate(self.menu_options):

            selected = idx == self.selected_idx

            if selected:

                menu = Text.assemble(
                    ("▶  ", "bold bright_green"),
                    (option.upper()),
                    ("  ◀", "bold bright_green")
                )

                panel = Panel(
                    Align.center(menu),
                    border_style="bright_green",
                    width=50,
                    padding=(0, 1),
                )

            else:

                menu = Text(
                    option,
                    style="bold white",
                    justify="center"
                )

                panel = Panel(
                    Align.center(menu),
                    border_style="bright_black",
                    width=50,
                    padding=(0, 1),
                )

            layout.add_row("")
            layout.add_row(Align.center(panel))

        layout.add_row("")

        layout.add_row(
            Text(
                "↑ ↓ Navigate   •   ENTER Select   •   ESC Exit",
                style="dim",
                justify="center"
            )
        )

        return Panel(
            Align.center(layout),
            border_style="bright_green",
            padding=(1, 2),
            title="[bold bright_white]MAIN MENU[/bold bright_white]",
            subtitle="[bold bright_black]CRICKET MATCH CENTER[/bold bright_black]"
        )

    def make_header(self, mode):

        grid = Table.grid(expand=True)

        grid.add_column(ratio=1)
        grid.add_column(justify="center")
        grid.add_column(justify="right")

        remaining = max(
            0,
            int(
                REFRESH_SECONDS
                -
                (time.monotonic() - self.last_refresh)
            )
        )

        logo = Text.assemble(
            ("🏏 ", "bold bright_green"),
            ("CRICKET ", "bold black on bright_green"),
            ("DUDE ", "bold black on bright_white"),
            (f"v{APP_VERSION}", "bold bright_cyan")
        )

        mode_text = Text(
            f"{mode.upper()}",
            style="bold bright_white"
        )

        refresh_text = Text.assemble(
            ("⟳ ", "bold bright_green"),
            (
                f"Refreshing in {remaining}s",
                "bold bright_cyan"
            )
        )

        grid.add_row(
            mode_text,
            logo,
            refresh_text
        )

        return Panel(
            grid,
            border_style="bright_green",
            padding=(0, 2)
        )
    
    def make_table(self):

        table = Table(
            expand=True,
            box=box.SIMPLE_HEAD,
        )

        table.add_column("Match", style="cyan", ratio=3)
        table.add_column("Team 1", style="yellow", ratio=2)
        table.add_column("Team 2", style="yellow", ratio=2)
        table.add_column("Status", style="green", ratio=3)

        if not self.current_data:

            table.add_row(
                "No matches found",
                "-",
                "-",
                "Try refreshing",
            )

            return table

        for match in self.current_data:
            #
            if match.is_live:

                status = Text.assemble(
                    ("● ", "bold bright_green"),
                    (match.status, "bold bright_green")
                )

            else:

                status = Text(
                    match.status,
                    style="white"
                )
            #
            table.add_row(
                match.description,

                Text.assemble(
                    self.team_text(match.team_one),
                    "\n",
                    Text(
                        match.team_one_score or "Yet to bat",
                        style="yellow"
                    )
                ),

                Text.assemble(
                    self.team_text(match.team_two),
                    "\n",
                    Text(
                        match.team_two_score or "Yet to bat",
                        style="yellow"
                    )
                ),

                status,
            )

        return table

    def generate_view(self, mode):

        layout = Layout()

        live_matches = [
            m for m in self.current_data
            if m.is_live
        ]

        if live_matches:

            layout.split_column(
                Layout(name="header", size=3),
                Layout(name="featured", size=15),
                Layout(name="body", ratio=1),
                Layout(name="footer", size=3),
            )

            layout["featured"].update(
                self.make_scoreboard(live_matches[0])
            )

        else:

            layout.split_column(
                Layout(name="header", size=3),
                Layout(name="body", ratio=1),
                Layout(name="footer", size=3),
            )

        layout["header"].update(
            self.make_header(mode)
        )

        layout["body"].update(
            self.make_table()
        )

        layout["footer"].update(
            Panel(
                Text(
                    "R Refresh  •  Q Back  •  Live Cricket Terminal",
                    justify="center",
                    style="dim",
                )
            )
        )

        return layout

    def start(self):

        while True:

            if self.current_mode is None:

                with Live(
                    self.generate_menu(),
                    screen=True,
                    refresh_per_second=10,
                ) as live:

                    while self.current_mode is None:

                        live.update(self.generate_menu())

                        key = get_key()

                        if key == "\x1b[A":
                            self.selected_idx = (
                                self.selected_idx - 1
                            ) % len(self.menu_options)

                        elif key == "\x1b[B":
                            self.selected_idx = (
                                self.selected_idx + 1
                            ) % len(self.menu_options)

                        elif key in ["\r", " "]:

                            choice = self.menu_options[
                                self.selected_idx
                            ]

                            if choice == "Exit":
                                return

                            self.current_mode = (
                                choice.split()[0].lower()
                            )

                        elif key == "\x1b":
                            return

            else:
                
                try:

                    self.current_data = self.provider.get_matches(
                        self.current_mode
                    )

                except ConnectionError:

                    self.show_offline_screen()

                    self.current_mode = None

                    continue

                self.last_refresh = time.monotonic()

                with Live(
                    self.generate_view(self.current_mode),
                    screen=True,
                    refresh_per_second=10,
                ) as live:

                    while self.current_mode:

                        if (
                            time.monotonic()
                            -
                            self.last_refresh
                            >
                            REFRESH_SECONDS
                        ):

                            old_data = self.current_data

                            self.current_data = self.provider.get_matches(
                                self.current_mode
                            )

                            self.last_refresh = time.monotonic()

                            if old_data != self.current_data:

                                live.update(
                                    Panel(
                                        Text(
                                            "▲ SCORE UPDATED",
                                            style="bold bright_green blink",
                                            justify="center",
                                        ),
                                        border_style="bright_green",
                                    )
                                )

                                time.sleep(0.2)

                        live.update(
                            self.generate_view(
                                self.current_mode
                            )
                        )

                        key = get_key()

                        if key in ["q", "Q", "\x1b"]:
                            self.current_mode = None

                        elif key in ["r", "R"]:

                            self.current_data = self.provider.get_matches(
                                self.current_mode
                            )

                            self.last_refresh = time.monotonic()

                            live.update(
                                self.generate_view(
                                    self.current_mode
                                )
                            )

                        time.sleep(0.05)

    def show_offline_screen(self):

        error_logo = Text("""
    ██████╗██████╗ ██╗ ██████╗██╗  ██╗███████╗████████╗
    ██╔════╝██╔══██╗██║██╔════╝██║ ██╔╝██╔════╝╚══██╔══╝
    ██║     ██████╔╝██║██║     █████╔╝ █████╗     ██║
    ██║     ██╔══██╗██║██║     ██╔═██╗ ██╔══╝     ██║
    ╚██████╗██║  ██║██║╚██████╗██║  ██╗███████╗   ██║
    ╚═════╝╚═╝  ╚═╝╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝   ╚═╝

    ██████╗ ██╗   ██╗██████╗ ███████╗
    ██╔══██╗██║   ██║██╔══██╗██╔════╝
    ██║  ██║██║   ██║██║  ██║█████╗
    ██║  ██║██║   ██║██║  ██║██╔══╝
    ██████╔╝╚██████╔╝██████╔╝███████╗
    ╚═════╝  ╚═════╝ ╚═════╝ ╚══════╝
    """, style="bold bright_red")

        message = Text.assemble(
            ("📡 NO INTERNET CONNECTION\n\n", "bold bright_red"),
            (
                "Cricket Dude requires an active internet connection\n"
                "to fetch live scores, commentary and match data.\n\n",
                "bold white"
            ),
            (
                "Please check your connection and try again.",
                "bold bright_black"
            )
        )

        content = Group(
            Align.center(error_logo),
            Text(""),
            Align.center(message)
        )

        panel = Panel(
            content,
            border_style="bright_red",
            padding=(1, 4),
            title="[bold bright_red]OFFLINE MODE[/bold bright_red]"
        )

        console.clear()

        console.print(panel)

        console.input(
            "\n[bold bright_green]Press ENTER to continue...[/]"
        )
        
def main():

    import sys
    import subprocess

    if "--child" not in sys.argv:

        subprocess.Popen(
            [
                "powershell",
                "-NoExit",
                "-Command",
                (
                    "$host.UI.RawUI.WindowTitle = "
                    "'Cricket Dude v1.5'; "

                    "cricket-dude --child"
                )
            ],
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )

        sys.exit()

    try:

        show_loading_screen()

        CricketDude().start()

    except KeyboardInterrupt:

        console.print(
            "\n[bold red]Goodbye![/bold red]"
        )

if __name__ == "__main__":
    main()