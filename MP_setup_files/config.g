; General
G90                             ; absolute coordinates
M83                             ; relative extruder moves
M550 P"KINETIQ"                 ; machine name

; General preferences
M575 P1 S1 B57600               ; enable support for PanelDue

; Net
echo "Connecting to MotionControl2p4 WiFi..."

;M552 S0                         ; Stop WiFi module
;G4 S5                           ; Wait wifi module to start
;M552 S1                         ; Attempt to connect as station (Client mode)
;G4 S30                          ; Crucial pause to let the chip initialize the object model array

; ---- Fallback Logic Loop ----
;if network.interfaces[0].state != "active"
;    echo "MotionControl WiFi not found. Falling back to Standalone Server Mode..."
echo "Starting WiFi Access Point..."
echo "WiFi: MotionPlatform Pass: RealizeLab"
M552 S0                 ; Stop client attempt
G4 P4                   ; Wait 4 ms
M552 S2                 ; Start Access Point server mode using stored M589 settings

; Enable Web Server Protocols
M586 P0 S1                      ; Enable HTTP
M586 P1 S0                      ; Disable FTP
M586 P2 S0                      ; Disable Telnet



; Wait for expansion board
G4 S2    ;


; Kinematics
M669 K0                         ; Cartesian mode

; Trigger output (LogIQ switches it with M42 P5 S1 / M42 P5 S0)
M950 P5 C"out6"                 ; GPIO port 5 = out6


; Motor directions
; A B e and g - Plate 1
; C D f and h - Plate 2

; Vertical Axes A B C D
M569 P101.0 S0 ; A motor
M569 P101.4 S0 ; B motor
M569 P0 S0     ; C motor
M569 P1 S0     ; D motor
; ----------------------------------------------------------
; 'c 'a Axis - 4 motors (2 on each side of the platform)
; moving in the direction across the plate
M569 P3 S0 ; 'c motor 1
M569 P4 S0 ; 'c motor 2
M569 P101.3 S1 ; 'a motor 1 (5+ expansion) - S1 = firmware default, as before (this line was a duplicate 'M569 P101.0 S0')
M569 P101.1 S1 ; 'a motor 2 (5+ expansion)
; ----------------------------------------------------------
; 'f and 'e Axis - 2 motors (1 on each side of the platform) - Moving from left to right
M569 P2 S1     ; 'f motor
M569 P101.2 S0 ; 'e motor

; expose io5.in as a digital "switch" probe so rr_status includes it
M558 K0 P5 C"!^io5.in" H5 F120 T6000    ; K0 = probe#0, P5 = switch/digital mode; ! = inverted: no detector signal reads 0 (was 1000 with "^io5.in")
G31  K0 P500                            ; standard threshold (won't affect anything unless probing)

; Axis mapping

M584 A101.0 B101.4 C0 D1 'c3:4 'a101.1:101.3 'f2 'e101.2;



M350 A16 B16 C16 D16 'c16 'a16 'f16 'e16                    ; microstepping 1/16 for all axes (interpolated to 256 by the drivers)
M92 A1920 B1920 C1920 D1920 'c1920 'a1920 'f1920 'e1920     ; steps per mm
M566 A300 B300 C300 D300 'c300 'a300 'f300 'e300            ; maximum instantaneous speed change (jerk), mm/min
M203 A1200 B1200 C1200 D1200 'c1200 'a1200 'f1200 'e1200 I6 ; maximum speed per axis, mm/min; I6 = minimum movement speed 6 mm/min (0.1 mm/s, as in LogIQ G-code)
M201 A500 B500 C500 D500 'c500 'a500 'f500 'e500            ; maximum acceleration, mm/s^2
M906 A1000 B1000 C1000 D1000 'c1000 'a1000 'f1000 'e1000    ; motor current, mA (idle current: firmware default)

M84 S7200                               ; disable motors after 120 minutes of inactivity (release holding torque)

; Axis limits
M208 A0:90 B0:90 C0:90 D0:90 'c0:60 'a0:60 'f0:100 'e0:100

; 'f maximum endstop on io3.in
M574 'f2 S1 P"io3.in"
; 'c maximum endstop on io2.in
M574 'c2 S1 P"io2.in"
; C minimum endstop on io4.in
M574 C1 S1 P"io4.in"
; D minimum endstop on io1.in
M574 D1 S1 P"io1.in"

; A minimum endstop on 101.io2.in
M574 A1 S1 P"101.io2.in"
; B minimum endstop on 101.io1.in
M574 B1 S1 P"101.io1.in"

; 'e maximum endstop on 101.io0.in
M574 'e2 S1 P"101.io0.in"

; 'a maximum endstop on 101.io3.in
M574 'a2 S1 P"101.io3.in"

