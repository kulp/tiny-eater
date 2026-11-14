* T-pad attenuator at 10 dB, Z0=75.0
V1 in 0 DC 1
R1 in mid 38.962039
R3 mid out 38.962039
R2 mid 0 52.704628
Rload out 0 75.0
.op
.control
run
print v(out)
print i(v1)
.endc
.end
