* T-pad attenuator at 8 dB, Z0=75.0
V1 in 0 DC 1
R1 in mid 32.287913
R3 mid out 32.287913
R2 mid 0 70.962944
Rload out 0 75.0
.op
.control
run
print v(out)
print i(v1)
.endc
.end
