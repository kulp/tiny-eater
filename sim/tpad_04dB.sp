* T-pad attenuator at 4 dB, Z0=75.0
V1 in 0 DC 1
R1 in mid 16.970523
R3 mid out 16.970523
R2 mid 0 157.243278
Rload out 0 75.0
.op
.control
run
print v(out)
print i(v1)
.endc
.end
