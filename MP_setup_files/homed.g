; homed.g - home D (vertical, plate 2, minimum endstop io1.in)
; called by G28 D

G91                                         ; relative positioning
G1 H1 D-95 F600                             ; towards the min endstop, stops when it triggers; position = 0 (axis minimum)
G1 D5 F600                                  ; back off 5 mm
G1 H1 D-10 F120                             ; second, slower approach
G90                                         ; absolute positioning
