; homex.g - DYNAMIQ, home the X axis to its low-end switch
; 2026-11-12: guard against a switch that already reads triggered (G1 H1 would then home instantly, in place),
;             slower second pass (2 mm/s) for a repeatable zero, back-off at 10 mm/s.
;             Original: DYNAMIQ_setup_files/original_20261112/homex.g

if sensors.endstops[0].triggered        ; at the switch already, or a wiring / polarity fault
    G91
    G1 H2 X3 F300                    ; move 3 mm away from the switch (allowed before homing)
    G90
    M400
    if sensors.endstops[0].triggered
        abort "homex.g: X switch still triggered 3 mm away from home - check the switch and its cable (M119)"

G91                     ; relative positioning
G1 H1 X-45 F300       ; fast approach to the switch (first pass)
G1 H2 X3 F600         ; back off 3 mm
G1 H1 X-5 F120        ; slow approach (second pass) sets X=0
G90                     ; absolute positioning
