; homeall.g - DYNAMIQ, home X, Y and Z
; 2026-11-12: each axis is homed by its own file (switch guard, slow second pass), one after the other.
;             Original (all three together, no guard): DYNAMIQ_setup_files/original_20261112/homeall.g
M98 P"homex.g"
M98 P"homey.g"
M98 P"homez.g"
