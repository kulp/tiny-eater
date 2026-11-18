PYTHON    ?= python3
# KICAD_CLI is exported so recipes that shell out to helper scripts pick it up
# too.
KICAD_CLI ?= kicad-cli
export KICAD_CLI

# Each target is a self-contained block: it registers itself with `all` and
# defines its own rules.
.PHONY: all
all:

.PHONY: clean
clean:
	rm -rf build

# The fabrication output straight from the committed board.  --check-zones
# refills the GND copper before plotting, so no pre-filled copy of the board is
# needed.
.PHONY: gerbers
all: gerbers
gerbers: build/gerbers/attenuator-F_Cu.gtl build/gerbers/attenuator-B_Cu.gbl
build/gerbers/attenuator-F_Cu.gtl build/gerbers/attenuator-B_Cu.gbl &: attenuator.kicad_pcb
	$(KICAD_CLI) pcb export gerbers --check-zones -o build/gerbers/ attenuator.kicad_pcb
