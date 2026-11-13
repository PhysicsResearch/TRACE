;G91               ; relative positioning
;G1 H2 Z5 F600    ; lift Z relative to current position
;G1 H1 Z-265 F300 ; move Z down until the endstop is triggered
;G92 Z0            ; set Z position to axis minimum (you may want to adjust this)

G91               ; relative positioning
G1 H1 Z-240 F300 ; move quickly to Y axis endstop and stop there (first pass)
G1 H2 Z5 F600    ; go back a few mm
G1 H1 Z-240 F240  ; move slowly to Y axis endstop once more (second pass)
G90               ; absolute positioning
