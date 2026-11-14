* T-pad attenuator at 3 dB, Z0=75.0
V1 in 0 DC 1
R1 in mid 12.824802
R3 mid out 12.824802
R2 mid 0 212.889234
Rload out 0 75.0
.op
.control
run
print v(out)
print i(v1)
.endc
.end
