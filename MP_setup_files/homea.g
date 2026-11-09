; homea.g - home A (vertical, plate 1, minimum endstop 101.io2.in)
; called by G28 A

G91                                         ; relative positioning
G1 H1 A-95 F600                             ; towards the min endstop, stops when it triggers; position = 0 (axis minimum)
G1 A5 F600                                  ; back off 5 mm
G1 H1 A-10 F120                             ; second, slower approach
G90                                         ; absolute positioning
