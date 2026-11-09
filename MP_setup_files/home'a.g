; home'a.g - home 'a (SI, plate 1, maximum endstop 101.io3.in)
; called by G28 'a

G91                                         ; relative positioning
G1 H1 'a65 F600                             ; towards the max endstop, stops when it triggers; position = 60 (axis maximum, M208)
G1 'a-5 F600                                ; back off 5 mm
G1 H1 'a10 F120                             ; second, slower approach
G90                                         ; absolute positioning
