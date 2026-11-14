* T-pad attenuator at 1 dB, Z0=75.0
V1 in 0 DC 1
R1 in mid 4.312585
R3 mid out 4.312585
R2 mid 0 650.004829
Rload out 0 75.0
.op
.control
run
print v(out)
print i(v1)
.endc
.end
