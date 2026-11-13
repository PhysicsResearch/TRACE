; home'f.g - home 'f (LAT, plate 2, maximum endstop io3.in)
; called by G28 'f

G91                                         ; relative positioning
G1 H1 'f210 F600                            ; towards the max endstop (up to 210 mm: one press from anywhere), stops when it triggers; position = 100 (axis maximum, M208)
G1 'f-5 F600                                ; back off 5 mm
G1 H1 'f10 F120                             ; second, slower approach
G90                                         ; absolute positioning
