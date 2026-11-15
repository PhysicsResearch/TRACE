; daemon.g - DYNAMIQ (lung phantom), Duet 3 Mini 5+, RepRapFirmware 3.6.3
; Install on the board's SD card as 0:/sys/daemon.g (RRF runs it in its own channel, beside the job and the panel).
; Needs 0:/macros/sensor_wait.g (DYNAMIQ_setup_files/sensor_wait.g).
;
; Purpose: the "Wait radiation" button of the PanelDue (Control tab). While a job runs, the panel sends
;     set global.radiation_wait = true
;     M25
; Once the job is paused, this file waits for the detector with sensor_wait.g (until sensors.probes[0], the detector
; on io4.in, reads > 500, or until Release: set global.force_release_sensor = true, from the panel or LogIQ) and
; then resumes the job (M24).
;
; Rules:
;   - The request flag stays set during the detector wait. The job is resumed only if the flag is still set and the
;     job is still paused afterwards: Play or Cancel on the panel during the wait first send
;     "set global.radiation_wait = false" and "set global.force_release_sensor = true", so the wait ends and the job
;     is left to that Play / Cancel.
;   - A request with no job any more (status idle) is dropped.
;   - The panel withdraws its own request if the job has not paused 15 s after Wait radiation.

if !exists(global.radiation_wait)
    global radiation_wait = false                   ; true: resume the paused job when the detector sees radiation
if !exists(global.force_release_sensor)
    global force_release_sensor = false             ; true: end the wait of sensor_wait.g (Release)

while true
    if global.radiation_wait && state.status == "paused"
        M98 P"0:macros/sensor_wait.g"               ; returns on the detector signal or on Release
        if global.radiation_wait && state.status == "paused"
            set global.radiation_wait = false
            M24                                     ; resume the job
        else
            set global.radiation_wait = false       ; resumed or cancelled meanwhile: leave the job alone
    elif global.radiation_wait && state.status == "idle"
        set global.radiation_wait = false           ; stale request: the job has ended
    G4 P50                                          ; check every 50 ms
