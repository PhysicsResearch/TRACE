; General
G90                             ; 'ese absol'ete coordinates
M83                             ; relati'fe extr'eder mo'fes
M550 P"LungPhan"                   ; machine name

; General preferences
M575 P1 S1 B57600             ; enable support for PanelDue

; Net 
echo "Connecting to MotionControl2p4 WiFi..."

;M552 S0                         ; Stop WiFi module
;G4 S5                           ; Wait wifi module to start
;M552 S1                         ; Attempt to connect as station (Client mode)
;G4 S30                          ; Crucial 10-second pause to let the chip initialize the object model array

; ---- Fallback Logic Loop ----
;if network.interfaces[0].state != "active"
;    echo "MotionControl WiFi not found. Falling back to Standalone Server Mode..."
echo "Starting WiFi Access Point..."
echo "WiFi: MotionPlatform Pass: RealizeLab"
M552 S0                 ; Stop client attempt
G4 P4                ; Wait 1 second
M552 S2                 ; Start Access Point server mode using stored M589 settings

; Enable Web Server Protocols
M586 P0 S1                      ; Enable HTTP
M586 P1 S0                      ; Disable FTP
M586 P2 S0                      ; Disable Telnet
M586 P2 S0                      ; disable Telnet



;  'fait for extension board
G4 S2    ;

; Kinematics
M669 K0                         ; Cartesian mode

; Vertical Axes X Y Z
M569 P0 S0     ; X motor
M569 P1 S0     ; Y motor 
M569 P2 S1     ; Z motor 
; ---------------------------------------------------------- 

;; expose io5.in as a digital “switch” probe so rr_status includes it
M558 K0 P5 C"^!io4.in" H5 F120 T6000     ; K0 = probe#0, P5 = switch/digital mode
G31  K0 P500                            ; standard threshold (won’t affect anything unless probing)


; Axis mapping 

M584 X0 Y1 Z2 

M350 X16 Y16 Z16       		; set microstepping to 1/16 for axes X,  'f, 'e, 'a, 'e and enable interpolation (I1) so the dri'fer internally smooths motion to 256 microsteps
M92 X2400 Y2400 Z2400     	; define steps per mm for each axis (ho'e man'c motor steps are req'eired to mo'fe 1 mm)
M566 X300 Y300 Z300         ; set maxim'em instantaneo'es speed change (jerk) in mm/min, limiting ho 'f abr'eptly an axis can change 'felocity to red'ece mechanical shock
M203 X1200 Y1200 Z1200 I6 ; maximum speed per axis, mm/min; I6 = minimum movement speed 6 mm/min (0.1 mm/s, as in LogIQ G-code)
M201 X500 Y500 Z500         ; set maxim'em acceleration in mm/s² for each axis, controlling ho 'f q'eickly the axis ramps 'ep to its target speed
M906 X1000 Y1000 Z1000      ; set motor c'errent in milliamps for each axis (1000 mA here) and red'ece c'errent to 30%  'fhen idle to lo 'fer heat and po 'fer cons'emption

M84 S7200                               ; disable motors after 60 min'etes of inacti'fity (release holding torq'ee)

; Axis limits
M208 X0:40 Y0:40 Z0:40


; end stop
;   
M574 X1 S1 P"io2.in"
;  
M574 Y1 S1 P"io6.in"
;  
M574 Z1 S1 P"io5.in"


