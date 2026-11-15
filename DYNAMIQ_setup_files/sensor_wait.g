; sensor_wait.g - DYNAMIQ (lung phantom), RepRapFirmware 3.6.3
; Install on the board's SD card as 0:/macros/sensor_wait.g.
; Same logic as MP_setup_files/sensor_wait.g (KINETIQ). On DYNAMIQ the detector is probe 0 on io4.in
; (config.g: M558 K0 P5 C"^!io4.in", a digital probe that reads 0 or 1000).
; Waits until probe 0 reports > 500 (detector signal) OR a forced release (set global.force_release_sensor = true,
; the Release button of LogIQ and of the PanelDue). Called by the G-code of a plan (M98 P"0:macros/sensor_wait.g")
; and by daemon.g for the panel's "Wait radiation".
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
