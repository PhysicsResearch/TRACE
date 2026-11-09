; home'f.g - home 'f (LAT, plate 2, maximum endstop io3.in)
; called by G28 'f

G91                                         ; relative positioning
G1 H1 'f105 F600                            ; towards the max endstop, stops when it triggers; position = 100 (axis maximum, M208)
G1 'f-5 F600                                ; back off 5 mm
G1 H1 'f10 F120                             ; second, slower approach
G90                                         ; absolute positioning
