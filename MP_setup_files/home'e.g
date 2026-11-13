; home'e.g - home 'e (LAT, plate 1, maximum endstop 101.io0.in)
; called by G28 'e

G91                                         ; relative positioning
G1 H1 'e210 F600                            ; towards the max endstop (up to 210 mm: one press from anywhere), stops when it triggers; position = 100 (axis maximum, M208)
G1 'e-5 F600                                ; back off 5 mm
G1 H1 'e10 F120                             ; second, slower approach
G90                                         ; absolute positioning
