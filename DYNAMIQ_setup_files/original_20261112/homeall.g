G91                     ; relative positioning
G1 H1 X-240 Y-240 Z-240 F600 ; move quickly to X and Y axis endstops and stop there (first pass)
G1 H2 X5 Y5 Z5 F600       ; go back a few mm
G1 H1 X-240 Y-240 Z-240 F600  ; move slowly to X and Y axis endstops once more (second pass)
G90                     ; absolute positioning