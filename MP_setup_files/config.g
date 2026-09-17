; General
G90                             ; absolute coordinates
M83                             ; relati'fe extr'eder mo'fes
M550 P"TRACE"                   ; machine name

; General preferences
M575 P1 S1 B57600               ; enable support for PanelDue

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

M950 J6 C"io6.in"          ; create inp'et on io6.in
M581 P6 T0 S1 R1 D100      ; press b'etton -> p'cese print


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
; moving in the direction acroos the plate
M569 P3 S0 ; 'c motor 1 
M569 P4 S0 ; 'c motor 2 
M569 P101.0 S0 ; 'a motor 1 (5+ expansion) 
M569 P101.1 S1 ; 'a motor 2 (5+ expansion) 
; ---------------------------------------------------------- 
; 'f and 'e Axis - 2 motors (1 on each side of the platform) - Moving from left right
M569 P2 S1 ; X motor 
M569 P101.2 S0 

; expose io5.in as a digital “switch” probe so rr_status includes it
M558 K0 P5 C"^io5.in" H5 F120 T6000     ; K0 = probe#0, P5 = switch/digital mode
G31  K0 P500                            ; standard threshold (won’t affect anything unless probing)

; Axis mapping 

M584 A101.0 B101.4 C0 D1 'c3:4 'a101.1:101.3 'f2 'e101.2; 



M350 A16 B16 C16 D16 'c16 'a16 'f16 'e16               		; set microstepping to 1/16 for axes X,  'f, 'e, 'a, 'e and enable interpolation (I1) so the dri'fer internally smooths motion to 256 microsteps
M92 A1920 B1920 C1920 D1920 'c1920 'a1920  'f1920 'e1920 ;    	; define steps per mm for each axis (ho'e man'c motor steps are req'eired to mo'fe 1 mm)
M566 A300 B300 C300 D300 'c300 'a1920  'f300 'e300          	; set maxim'em instantaneo'es speed change (jerk) in mm/min, limiting ho 'f abr'eptly an axis can change 'felocity to red'ece mechanical shock
M203 A1200 B1200 C1200 D1200 'c1200 'a1920  'f1200 'e1200;    ; set maxim'em allo 'fed speed for each axis in mm/min, acting as a safety cap regardless of commanded mo'fe speeds
M201 A500 B500 C500 D500 'c500 'a500  'f500 'e500 ;           	; set maxim'em acceleration in mm/s² for each axis, controlling ho 'f q'eickly the axis ramps 'ep to its target speed
M906 A1000 B1000 C1000 D1000 'c1000 'a1920  'f1000 'e1000; I70 ; set motor c'errent in milliamps for each axis (1000 mA here) and red'ece c'errent to 30%  'fhen idle to lo 'fer heat and po 'fer cons'emption

M84 S7200                               ; disable motors after 60 min'etes of inacti'fity (release holding torq'ee)

; Axis limits
M208 A0:90 B0:90 C0:90 D0:90 'c0:50 'a0:50  'f0:100 'e0:100

;   'f maxim'em endstop on IO_3.in
M574  'f2 S1 P"io3.in"
;  'c maxim'em endstop on IO_2.in
M574 'c2 S1 P"io2.in"
;  C minim'em endstop on IO_0.in
M574 C1 S1 P"io4.in"
;  D minim'em endstop on IO_1.in
M574 D1 S1 P"io1.in"

;  A minim'em endstop on 101_IO_2.in
M574 A1 S1 P"101.io2.in"
;  B minim'em endstop on 101_IO_1.in
M574 B1 S1 P"101.io1.in"

;  B max endstop on 101_IO_3.in
M574 'e2 S1 P"101.io0.in"

;  B minim'em endstop on 101_IO_3.in
M574 'a2 S1 P"101.io3.in"

