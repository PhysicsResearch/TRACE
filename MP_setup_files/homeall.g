; homeall.g - home every axis: A B C D first, then LAT ('e 'f), then SI ('a 'c)
; called by G28

G91                                         ; relative positioning

; 1) vertical axes A B C D (minimum endstops, travel 0-90 mm)
G1 H1 A-95 B-95 C-95 D-95 F600              ; towards the min endstop, stops when it triggers; position = 0 (axis minimum)
G1 A5 B5 C5 D5 F600                         ; back off 5 mm
G1 H1 A-10 B-10 C-10 D-10 F120              ; second, slower approach

; 2) LAT: 'e 'f (maximum endstops, travel 0-100 mm)
G1 H1 'e210 'f210 F600                      ; towards the max endstop (up to 210 mm: one press from anywhere), stops when it triggers; position = 100 (axis maximum, M208)
G1 'e-5 'f-5 F600                           ; back off 5 mm
G1 H1 'e10 'f10 F120                        ; second, slower approach

; 3) SI: 'a 'c (maximum endstops, travel 0-60 mm)
G1 H1 'a65 'c65 F600                        ; towards the max endstop, stops when it triggers; position = 60 (axis maximum, M208)
G1 'a-5 'c-5 F600                           ; back off 5 mm
G1 H1 'a10 'c10 F120                        ; second, slower approach

G90                                         ; absolute positioning
