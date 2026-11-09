; homeb.g - home B (vertical, plate 1, minimum endstop 101.io1.in)
; called by G28 B

G91                                         ; relative positioning
G1 H1 B-95 F600                             ; towards the min endstop, stops when it triggers; position = 0 (axis minimum)
G1 B5 F600                                  ; back off 5 mm
G1 H1 B-10 F120                             ; second, slower approach
G90                                         ; absolute positioning
