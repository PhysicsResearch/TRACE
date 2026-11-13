; homex.g
; called to home the X axis
;

G91               ; relative positioning
G1 H1 X-240 F300  ; move quickly to X axis endstop and stop there (first pass)
G1 H2 X5 F6000    ; go back a few mm
G1 H1 X-240 F240  ; move slowly to X axis endstop once more (second pass)
G90               ; absolute positioning
