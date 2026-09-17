; sensor_wait.g
; Wait until Z-probe 0 reports > 500 OR force release is triggered
; it is used if the geiger sensor
if !exists(global.force_release_sensor)
    global force_release_sensor = false
else
    set global.force_release_sensor = false

M400                                    ; finish all buffered movements
echo "Waiting for sensor signal..."
while sensors.probes[0].value[0] <= 500 && !global.force_release_sensor
    G4 P10                              ; check every 10 ms
if global.force_release_sensor
    echo "Sensor wait force released by user. Continuing G-code."
else
    echo "Sensor detected. Continuing G-code."
