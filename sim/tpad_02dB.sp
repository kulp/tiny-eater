* T-pad attenuator at 2 dB, Z0=75.0
V1 in 0 DC 1
R1 in mid 8.596745
R3 mid out 8.596745
R2 mid 0 322.860335
Rload out 0 75.0
.op
.control
run
print v(out)
print i(v1)
.endc
.end
