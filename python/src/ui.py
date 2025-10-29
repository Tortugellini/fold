import asyncio
import contextlib
import numpy as np
from nicegui import ui

from utils.buffer import RollingBuffer
from datasources.testtone import TestTone
from datasources.serial_pcm16 import SerialPCM16LE
from datasources.tcp_pcm16 import TCPPCM16LE

SAMPLE_RATE = 8000
CHUNK = 256
ROLLING_SECONDS = 5
WINDOW_SAMPLES = int(ROLLING_SECONDS * SAMPLE_RATE)

rb = RollingBuffer(WINDOW_SAMPLES)
source = TestTone()
running = False
task = None
dark_mode = True
chart = None
status_label = None
rms_label = None
mean_label = None


def make_waveform_option():
    x = list(range(WINDOW_SAMPLES))
    return {
        'title': {'text': 'Live Waveform', 'left': 'center'},
        'grid': {'left': 40, 'right': 10, 'top': 40, 'bottom': 30},
        'xAxis': {'type': 'category', 'data': x, 'axisLabel': {'show': False}},
        'yAxis': {'type': 'value', 'min': -1.1, 'max': 1.1},
        'series': [{
            'type': 'line',
            'data': [0]*WINDOW_SAMPLES,
            'showSymbol': False,
            'animation': False,
            'lineStyle': {'width': 1.5},
            'areaStyle': {'opacity': 0.1},
        }],
    }


async def toggle_theme():
    global dark_mode
    dark_mode = not dark_mode
    ui.dark_mode(dark_mode)


async def start_stream(mode, port, baud, host, tcpport):
    """Start button handler."""
    global running, source, task
    if running:
        return

    # choose source
    if mode == 'Serial':
        source = SerialPCM16LE(port or "COM5", int(baud) if baud else 115200)
    elif mode == 'TCP':
        source = TCPPCM16LE(host or "192.168.4.1", int(tcpport) if tcpport else 1234)
    else:
        source = TestTone()

    await source.start()
    running = True
    status_label.set_text("Status: 🟢 Connected")
    task = asyncio.create_task(update_loop(chart))


async def stop_stream():
    global running, task
    running = False
    if task and not task.done():
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    task = None
    status_label.set_text("Status: 🔴 Stopped")
    chart.options['series'][0]['data'] = [0] * WINDOW_SAMPLES
    chart.update()
    await source.stop()


async def update_loop(chart_ref):
    """Efficient, slot-safe update loop."""
    global running
    read_dt   = 1/200.0
    render_dt = 1/10.0

    last_render = asyncio.get_event_loop().time()
    t_last = last_render
    frames = 0
    await asyncio.sleep(0.3)

    try:
        while running:
            data = await source.read_chunk(CHUNK)
            rb.extend(data)

            # statistics once per second
            frames += 1
            now = asyncio.get_event_loop().time()
            if now - t_last >= 1.0:
                fps = frames / (now - t_last)
                mean = float(np.mean(data))
                rms  = float(np.sqrt(np.mean(data**2)))
                # schedule label updates on the main thread
                ui.timer(0, lambda m=mean, r=rms, f=fps:
                         update_metrics(m, r, f), once=True)
                frames = 0
                t_last = now

            # render at lower rate
            if now - last_render >= render_dt:
                arr = rb.np()[-WINDOW_SAMPLES:]
                chart_ref.options['series'][0]['data'] = arr.tolist()
                chart_ref.update()
                last_render = now

            await asyncio.sleep(read_dt)

    except asyncio.CancelledError:
        pass
    except Exception as e:
        ui.timer(0, lambda msg=str(e):
                 status_label.set_text(f"Status: ⚠️ Error ({msg})"), once=True)
        await asyncio.sleep(1)


def update_metrics(mean, rms, fps):
    """Called on UI thread via ui.timer to avoid slot errors."""
    mean_label.set_text(f"Mean: {mean:+.4f}")
    rms_label.set_text(f"RMS:  {rms:+.4f}")
    status_label.set_text(f"Status: 🟢 Connected ({fps:.1f} Hz feed)")



@ui.page('/')
def main_page():
    global chart, status_label, mean_label, rms_label

    with ui.header().classes('items-center justify-between'):
        ui.label('Microcontroller Audio Monitor').classes('text-xl font-medium')
        with ui.row().classes('items-center gap-3'):
            mode = ui.toggle(['Test', 'Serial', 'TCP'], value='Test')
            port_in = ui.input(placeholder='COM port').props('dense').classes('w-44').bind_visibility_from(mode, 'value', lambda v: v=='Serial')
            baud_in = ui.input(placeholder='Baud').props('dense').classes('w-28').bind_visibility_from(mode, 'value', lambda v: v=='Serial')
            host_in = ui.input(placeholder='Host').props('dense').classes('w-44').bind_visibility_from(mode, 'value', lambda v: v=='TCP')
            tcpport_in = ui.input(placeholder='Port').props('dense').classes('w-28').bind_visibility_from(mode, 'value', lambda v: v=='TCP')
            ui.button('Start', on_click=lambda: asyncio.create_task(start_stream(mode.value, port_in.value, baud_in.value, host_in.value, tcpport_in.value)))
            ui.button('Stop', on_click=lambda: asyncio.create_task(stop_stream()), color='negative')
            ui.button('🌙/☀️', on_click=toggle_theme).tooltip('Toggle dark/light mode')

    with ui.card().classes('w-full max-w-5xl mx-auto mt-4'):
        chart = ui.echart(make_waveform_option()).classes('w-full h-72')

    with ui.row().classes('justify-center gap-6 mt-2'):
        status_label = ui.label("Status: 🔴 Idle")
        mean_label = ui.label("Mean: ---")
        rms_label = ui.label("RMS: ---")

    with ui.footer().classes('justify-center'):
        ui.label(f'{SAMPLE_RATE} Hz • {ROLLING_SECONDS}s window • chunk {CHUNK}').classes('text-sm opacity-70')
