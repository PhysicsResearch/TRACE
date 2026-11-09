; homec.g - home C (vertical, plate 2, minimum endstop io4.in)
; called by G28 C

G91                                         ; relative positioning
G1 H1 C-95 F600                             ; towards the min endstop, stops when it triggers; position = 0 (axis minimum)
G1 C5 F600                                  ; back off 5 mm
G1 H1 C-10 F120                             ; second, slower approach
G90                                         ; absolute positioning
