* T-pad attenuator at 6 dB, Z0=75.0
V1 in 0 DC 1
R1 in mid 24.920914
R3 mid out 24.920914
R2 mid 0 100.396561
Rload out 0 75.0
.op
.control
run
print v(out)
print i(v1)
.endc
.end
