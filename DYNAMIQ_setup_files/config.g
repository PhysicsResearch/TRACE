; config.g - DYNAMIQ (lung phantom), Duet 3 Mini 5+, RepRapFirmware 3.6.3
; 2026-11-12: comments repaired, microstep interpolation on (M350 I1), M564 explicit, event log (M929),
;             duplicate M586 and the expansion-board wait (no CAN board on DYNAMIQ) removed.
;             Original: DYNAMIQ_setup_files/original_20261112/config.g

; General
G90                             ; absolute coordinates
M83                             ; relative extruder moves
M550 P"LungPhan"                ; machine name

; General preferences
M575 P1 S1 B57600               ; enable support for PanelDue

; Network (unchanged)
echo "Connecting to MotionControl2p4 WiFi..."

;M552 S0                        ; stop WiFi module
;G4 S5                          ; wait for the WiFi module to start
;M552 S1                        ; connect as station (client mode)
;G4 S30                         ; let the module initialise

; ---- Fallback logic ----
;if network.interfaces[0].state != "active"
;    echo "MotionControl WiFi not found. Falling back to Standalone Server Mode..."
echo "Starting WiFi Access Point..."
echo "WiFi: MotionPlatform Pass: RealizeLab"
M552 S0                         ; stop client attempt
G4 P4                           ; short wait
M552 S2                         ; start access point mode with the stored M589 settings

; Web server protocols
M586 P0 S1                      ; enable HTTP
M586 P1 S0                      ; disable FTP
M586 P2 S0                      ; disable Telnet

; Event log on the SD card (0:/sys/eventlog.txt): resets, errors, connects/disconnects, job start/end
M929 P"eventlog.txt" S2

; Kinematics
M669 K0                         ; Cartesian

; Motors X Y Z (drivers 0.0, 0.1, 0.2)
M569 P0 S0                      ; X motor direction
M569 P1 S0                      ; Y motor direction
M569 P2 S1                      ; Z motor direction

; Detector input as a digital probe (io4.in, pull-up, inverted) so the status reports its state
M558 K0 P5 C"^!io4.in" H5 F120 T6000   ; K0 = probe 0, P5 = digital switch
G31 K0 P500                            ; threshold (only used when probing)

; Axis mapping
M584 X0 Y1 Z2

M350 X16 Y16 Z16 I1             ; 1/16 microstepping, interpolated to 256 by the drivers (smoother, quieter)
M92 X2400 Y2400 Z2400           ; steps per mm
M566 X300 Y300 Z300             ; max instantaneous speed change (jerk), mm/min
M203 X1200 Y1200 Z1200 I6       ; max speed 20 mm/s; I6 = minimum movement speed 0.1 mm/s (as in the LogIQ G-code)
M201 X500 Y500 Z500             ; max acceleration, mm/s^2
M906 X1000 Y1000 Z1000          ; motor current, mA
M84 S7200                       ; motors off after 2 hours idle

; Axis limits; moves before homing are refused and moves after homing stay within M208
M208 X0:40 Y0:40 Z0:40
M564 S1 H1

; Home switches (low end). Polarity checked 2026-11-12: each reads released 1 mm from home and triggered at home,
; so no '!' is needed. (A switch that read triggered away from home would make G28 home instantly in place;
; the homing files abort in that case.)
M574 X1 S1 P"io2.in"
M574 Y1 S1 P"io6.in"
M574 Z1 S1 P"io5.in"
