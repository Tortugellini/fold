# fold
For those of us too lazy to set a timer.

**Real-time audio frequency detection and monitoring.**
Low-latency C backend for capture/FFT; Python layer for streaming, visualization, and alerts.
Originally built to ping when laundry cycles finish — now generalized for any acoustic trigger.

## Features
- Real-time mic capture
- Live data streaming to desktop and mobile UI
- Notifications on frequency match (CLI, desktop, or webhook)
- *Planned:* FFT-based band detection, continuous recording, playback

## Architecture
- **C layer:** audio driver, ring buffer, windowing, FFT, band detection
- **Python layer:** configuration, IPC/streaming (e.g., ZeroMQ or WebSocket), visualization, and alerting
- **Clients:** lightweight web or mobile app for spectrogram and status display

#### More description to come.
