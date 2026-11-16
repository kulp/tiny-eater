PYTHON    ?= python3
# KICAD_CLI is exported so recipes that shell out to helper scripts pick it up
# too.
KICAD_CLI ?= kicad-cli
export KICAD_CLI

# Each target is a self-contained block: it registers itself with `all` and
# defines its own rules.
.PHONY: all
all:

build:
	mkdir -p $@

.PHONY: clean
clean:
	$(RM) -r build

# The fabrication output straight from the committed board.  --check-zones
# refills the GND copper before plotting, so no pre-filled copy of the board is
# needed.
.PHONY: gerbers
all: gerbers
gerbers: build/gerbers/attenuator-F_Cu.gtl build/gerbers/attenuator-B_Cu.gbl
build/gerbers/attenuator-F_Cu.gtl build/gerbers/attenuator-B_Cu.gbl &: attenuator.kicad_pcb | build
	$(KICAD_CLI) pcb export gerbers --check-zones -o build/gerbers/ attenuator.kicad_pcb

# The design checks: board DRC, schematic ERC and netlist-versus-board parity.
.PHONY: test
test:
	bash test/run_tests.sh

# The trimmer settings for each 1dB step, and the ngspice netlists derived from
# them.
.PHONY: resistor-table
all: resistor-table
resistor-table: sim/resistor_table.csv

sim/resistor_table.csv: scripts/gen_resistor_table.py
	$(PYTHON) scripts/gen_resistor_table.py --write

.PHONY: sim-netlists
all: sim-netlists
sim-netlists:
	$(PYTHON) scripts/gen_resistor_table.py --netlists

# A copy of the board with the ground zones refilled.  kicad-cli's 3D render only
# draws zone copper that is present in the file, so the renders need the filled
# copy; --save-board writes the refill back to the copy, leaving the committed
# board untouched.  The project file has to sit next to the copy, because the
# net-class clearances that bound the fill live in it.
.PHONY: production-pcb
all: production-pcb
production-pcb: build/attenuator.kicad_pcb
build/attenuator.kicad_pcb: attenuator.kicad_pcb attenuator.kicad_pro | build
	cp attenuator.kicad_pcb attenuator.kicad_pro build/
	$(KICAD_CLI) pcb drc --refill-zones --save-board build/attenuator.kicad_pcb

# The vendor STEP model of the RCA jack, downloaded into models/Same_Sky_RCJ-044/
# from the source named in the provenance note.  The tool leaves an already
# downloaded model alone, so the rule stamps the file; otherwise make would keep
# re-running the fetch every time it is invoked.
models/Same_Sky_RCJ-044/RCJ-044.step: tools/fetch_models.py models/RCJ-04/Same_Sky_RCJ-044.zip.txt
	$(PYTHON) tools/fetch_models.py
	touch $@
