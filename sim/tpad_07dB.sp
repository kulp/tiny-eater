* T-pad attenuator at 7 dB, Z0=75.0
V1 in 0 DC 1
R1 in mid 28.685423
R3 mid out 28.685423
R2 mid 0 83.703603
Rload out 0 75.0
.op
.control
run
print v(out)
print i(v1)
.endc
.end
