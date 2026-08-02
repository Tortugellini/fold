# fold
For those of us too lazy to set a timer.

## Real-time vibration detection and monitoring.
Designed to notify users when the laundry is done, 'fold' runs on the processing
capabilities of ESP8266 chips with a full RTOS operating system (thanks to the developers of FreeRTOS).<br />
Signal triggering is handled by an MPU-6050. The system is currently theorized to operate in two states:<br />
1) Laundry being washed - triggerless state.<br />
2) Laundry finished - triggered state: signal will be sent.<br />
<br />An ancillary feature of this product is vibrational normal mode analysis of washer and dryer systems.
