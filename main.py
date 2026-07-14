"""Tides – NOAA tide prediction chart as a Flet app.

Run on desktop:   flet run main.py
Build for phone:  flet build apk   (Android)
                  flet build ipa   (iOS, requires macOS)
"""

from datetime import date, datetime, timedelta
import xml.etree.ElementTree as ET

import matplotlib

matplotlib.use("svg")  # non-interactive backend required for Flet / mobile

import matplotlib.pyplot as plt
import numpy as np
import requests

import flet as ft
from flet.matplotlib_chart import MatplotlibChart

# ---------------------------------------------------------------- constants

NOAA_URL = (
    "https://tidesandcurrents.noaa.gov/api/datagetter"
    "?begin_date={date}&range={hours}&station={station}"
    "&product=predictions&datum=mllw&units=english"
    "&time_zone=lst_ldt&application=grandview&format=xml"
)
STATION = "9410230"

# view layout: portrait shows 1 day (1:2.2 aspect), landscape shows 4 days (2.2:1)
PORTRAIT_DAYS = 1
LANDSCAPE_DAYS = 4
PORTRAIT_TICK_HOURS = 3
LANDSCAPE_TICK_HOURS = 3
PORTRAIT_FIGSIZE = (4.5, 9.9)  # 1 : 2.2
LANDSCAPE_FIGSIZE = (9.9, 4.5)  # 2.2 : 1
SWIPE_THRESHOLD = 50  # logical px of horizontal drag that counts as a swipe
NOW_LINE_COLOR = (0.2, 1.0, 0.4)  # RGB floats 0–1; brighter green so it reads on the blue fill
NOW_LINE_WIDTH = 1.5  # points

QUARTER_DAY = timedelta(hours=6)
HALF_DAY = timedelta(hours=12)
FULL_DAY = timedelta(days=1)

# ---------------------------------------------------------------- helpers


def total_minutes(td: timedelta) -> float:
    return td.total_seconds() / 60


def concise_hour_label(minute: int) -> str:
    """e.g. 360 (06:00) -> '6a'"""
    label = datetime.strftime(datetime(1900, 1, 1) + timedelta(minutes=minute), "%I%p")
    if label.startswith("0"):
        label = label[1:]
    return label.replace("AM", "a").replace("PM", "p")


# ---------------------------------------------------------------- data


_tide_cache: dict = {}  # (iso_date, days) -> (times, levels)


def fetch_tides(start: datetime, days: int):
    """Fetch NOAA predictions; return (times_in_minutes, levels_in_feet)."""
    key = (start.date().isoformat(), days)
    if key in _tide_cache:
        return _tide_cache[key]

    url = NOAA_URL.format(
        date=start.date().isoformat().replace("-", ""),
        hours=days * 24,
        station=STATION,
    )
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()

    root = ET.fromstring(resp.text)
    times, levels = [], []
    for wl in root.iter("pr"):
        t = datetime.strptime(wl.attrib["t"], "%Y-%m-%d %H:%M")
        times.append(total_minutes(t - start))
        levels.append(float(wl.attrib["v"]))

    if not times:
        raise ValueError("NOAA returned no prediction data")
    _tide_cache[key] = (times, levels)
    return times, levels


def night_segments(range_days: int):
    """Line segments shading 6p–6a as 'night' (high) and 6a–6p as 'day' (low)."""
    xs, ys = [], []
    seg_start = -QUARTER_DAY
    end = timedelta(days=range_days)
    while seg_start < end:
        ys.extend([7, 7, -2, -2])
        t = seg_start
        xs.append(total_minutes(t))
        t += HALF_DAY
        xs.append(total_minutes(t))
        xs.append(total_minutes(t))
        t += HALF_DAY
        xs.append(total_minutes(t))
        seg_start += FULL_DAY
    return xs, ys


# ---------------------------------------------------------------- plotting


def build_figure(start: datetime, times, levels, days: int, portrait: bool):
    figsize = PORTRAIT_FIGSIZE if portrait else LANDSCAPE_FIGSIZE
    tick_hours = PORTRAIT_TICK_HOURS if portrait else LANDSCAPE_TICK_HOURS
    fig, ax = plt.subplots(figsize=figsize)

    end_minute = days * 24 * 60
    ax.set_xlim(0, end_minute)
    ax.set_ylim(-2, 7)
    if days == 1:
        title = datetime.strftime(start, "%A %B %d")
    else:
        end = start + timedelta(days=days - 1)
        title = f"{start:%a %b %d} \u2013 {end:%a %b %d}"
    ax.set_title(title, loc="left")
    ax.set_ylabel("water level")

    # tick marks and time-axis labels
    tick_locs = np.arange(0, end_minute + 1, tick_hours * 60)
    tick_labels = [concise_hour_label(60 * 24)]  # '12a' at the zero-minute
    tick_labels += [concise_hour_label(int(m)) for m in tick_locs[1:]]
    ax.set_xticks(tick_locs)
    ax.set_xticklabels(tick_labels)
    ax.set_yticks(np.arange(-2, 8))
    ax.grid(axis="x")

    # night shading (bottom), 1-foot reference band above it, tide curve on top
    night_x, night_y = night_segments(days)
    ax.fill_between(night_x, -2, night_y, color="lightgray", zorder=0)
    ax.fill_between([0, end_minute], 0, [1, 1], color="lightblue", zorder=0.5)
    ax.plot(times, levels)
    ax.fill_between(times, 0, levels)

    # current-time marker: vertical green line, only if 'now' is in this window
    now_minute = total_minutes(datetime.now() - start)
    if 0 <= now_minute <= end_minute:
        ax.axvline(
            now_minute,
            color=NOW_LINE_COLOR,
            linewidth=NOW_LINE_WIDTH,
            zorder=3,
        )

    fig.tight_layout()
    return fig


# ---------------------------------------------------------------- app


def main(page: ft.Page):
    page.title = "Tides"
    page.padding = 10

    anchor = date.today()  # first day of the visible window

    status = ft.Text(visible=False, color=ft.Colors.RED)
    progress = ft.ProgressRing(visible=False, width=24, height=24)
    chart_holder = ft.Container(expand=True, alignment=ft.alignment.center)

    def is_portrait() -> bool:
        return (page.height or 600) > (page.width or 800)

    def days_shown() -> int:
        return PORTRAIT_DAYS if is_portrait() else LANDSCAPE_DAYS

    def load(e=None):
        progress.visible = True
        status.visible = False
        page.update()
        try:
            days = days_shown()
            start = datetime(anchor.year, anchor.month, anchor.day)
            times, levels = fetch_tides(start, days)
            fig = build_figure(start, times, levels, days, is_portrait())
            chart_holder.content = MatplotlibChart(fig, expand=True)
            plt.close(fig)
        except requests.RequestException as ex:
            status.value = f"Network error – check your connection.\n{ex}"
            status.visible = True
        except Exception as ex:
            status.value = f"Error: {ex}"
            status.visible = True
        progress.visible = False
        page.update()

    def go(direction: int):
        """Move the window back/forward by one view-width (1 or 4 days)."""
        nonlocal anchor
        anchor += timedelta(days=direction * days_shown())
        load()

    # ---- swipe navigation: accumulate horizontal drag, decide on release
    drag_dx = 0.0

    def on_pan_start(e):
        nonlocal drag_dx
        drag_dx = 0.0

    def on_pan_update(e):
        nonlocal drag_dx
        drag_dx += e.delta_x

    def on_pan_end(e):
        if drag_dx > SWIPE_THRESHOLD:
            go(-1)  # swipe right -> earlier
        elif drag_dx < -SWIPE_THRESHOLD:
            go(1)  # swipe left -> later

    swiper = ft.GestureDetector(
        content=chart_holder,
        drag_interval=10,
        on_pan_start=on_pan_start,
        on_pan_update=on_pan_update,
        on_pan_end=on_pan_end,
        expand=True,
    )

    # ---- rebuild when the window flips between portrait and landscape
    last_orientation = is_portrait()

    def on_resized(e):
        nonlocal last_orientation
        if is_portrait() != last_orientation:
            last_orientation = is_portrait()
            load()

    page.on_resized = on_resized

    page.appbar = ft.AppBar(
        title=ft.Text("Tides"),
        actions=[
            ft.IconButton(ft.Icons.CHEVRON_LEFT, tooltip="Earlier", on_click=lambda e: go(-1)),
            ft.IconButton(ft.Icons.REFRESH, tooltip="Refresh", on_click=load),
            ft.IconButton(ft.Icons.CHEVRON_RIGHT, tooltip="Later", on_click=lambda e: go(1)),
        ],
    )
    page.add(
        ft.Column(
            [ft.Row([progress]), status, swiper],
            expand=True,
        )
    )
    load()


ft.app(main)
