* T-pad attenuator at 9 dB, Z0=75.0
V1 in 0 DC 1
R1 in mid 35.716355
R3 mid out 35.716355
R2 mid 0 60.887260
Rload out 0 75.0
.op
.control
run
print v(out)
print i(v1)
.endc
.end
