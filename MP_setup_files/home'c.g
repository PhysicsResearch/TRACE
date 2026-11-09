; home'c.g - home 'c (SI, plate 2, maximum endstop io2.in)
; called by G28 'c

G91                                         ; relative positioning
G1 H1 'c65 F600                             ; towards the max endstop, stops when it triggers; position = 60 (axis maximum, M208)
G1 'c-5 F600                                ; back off 5 mm
G1 H1 'c10 F120                             ; second, slower approach
G90                                         ; absolute positioning
