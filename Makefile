PYTHON    ?= python3
# KICAD_CLI is exported so recipes that shell out to helper scripts pick it up too.
KICAD_CLI ?= kicad-cli
export KICAD_CLI
OPENSCAD  ?= openscad

# Only the entry points are phony. Every step that writes a file has a rule
# named after that file, so running a target twice in a row does nothing until
# one of its inputs is newer than its output.
.PHONY: all test resistor-table production-pcb pcb-renders clean
all: resistor-table production-pcb pcb-renders

test:
	bash test/run_tests.sh

resistor-table: sim/resistor_table.csv
production-pcb: build/attenuator.kicad_pcb
pcb-renders: build/attenuator_3d_front.png build/attenuator_3d_back.png

sim/resistor_table.csv: scripts/gen_resistor_table.py
	$(PYTHON) scripts/gen_resistor_table.py --write

build/attenuator.kicad_pcb: attenuator.kicad_pcb scripts/build_production_pcb.py
	$(PYTHON) scripts/build_production_pcb.py

# The RCA jacks only show up in the render when the STEP model that
# tools/fetch_footprints.py places in models/Same_Sky_RCJ-044/ is present. It
# is the only 3D model that tool produces; the trimmer and test point models
# come from the KiCad install. The model is an order-only prerequisite of the
# renders: it has to exist, but refreshing it does not by itself mean the
# renders are stale.
models/Same_Sky_RCJ-044/RCJ-044.step: tools/fetch_footprints.py models/RCJ-04/Same_Sky_RCJ-044.zip.txt
	$(PYTHON) tools/fetch_footprints.py || true
	@test -f $@ || { echo "error: $@ is missing; tools/fetch_footprints.py cannot get the RCJ-044 STEP without a browser session" >&2; exit 1; }
	# The tool leaves an already downloaded model untouched, so stamp it here;
	# otherwise make would keep re-running the fetch every time it is invoked.
	touch $@

build/attenuator_3d_front.png build/attenuator_3d_back.png &: scripts/render_pcb_3d.sh build/attenuator.kicad_pcb | models/Same_Sky_RCJ-044/RCJ-044.step
	bash scripts/render_pcb_3d.sh

clean:
	rm -rf build
