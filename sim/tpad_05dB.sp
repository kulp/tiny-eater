* T-pad attenuator at 5 dB, Z0=75.0
V1 in 0 DC 1
R1 in mid 21.009750
R3 mid out 21.009750
R2 mid 0 123.361544
Rload out 0 75.0
.op
.control
run
print v(out)
print i(v1)
.endc
.end
