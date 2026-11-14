// Attenuator enclosure with a castellated lid on the slide-in end.
//
// Houses the 29 x 23 x 1.6 mm attenuator PCB (attenuator.kicad_pcb).
// The board slides in from one short end, along the RCA barrel axis (X).
// The two RCA jacks sit 4.5 mm in from each short end and face opposite
// directions; their barrels stick out the two short ends and pass through
// openings in the two end faces.
//
// The slide-in end is closed by a lid (a separate part) held by a ring of
// castellations: the ends of the four enclosure walls carry tabs that stick out
// by cast_d, and the lid's rim has matching notches cut out of it that those
// tabs pass through. The lid is therefore a plate of uniform thickness - the
// castellations are cutouts in it rather than teeth added to it. The tab/notch
// comb stops the lid from spinning about the mating axis (X) or being pulled
// sideways out of the interface. Pulling the lid straight off is resisted only
// by friction; it is not meant to be removed.
//
// Build: openscad -o enclosure.stl enclosure.scad
// Both parts land in one file as two solids; enclosure/build_parts.sh writes them
// as two separate STLs in print orientation, and enclosure/check_castellations.py
// shows how to render each part on its own.

// ---- Parameters ----
board_x   = 29.0;   // board length (X, slide-in axis)
board_y   = 23.0;   // board width  (Y)
board_z   = 1.6;    // board thickness (Z)
side_clr  = 0.4;    // min clearance on each side (X, Y)
top_clr   = 15.0;   // clearance above the board top (Z)
slot_clr  = 0.2;    // board-to-slot clearance (Y per side, Z above the board)
wall      = 1.5;    // wall thickness

// Lid
lid_t     = 1.5;    // lid plate thickness (X); the lid is one uniform thickness
fit_clr   = 0.1;    // clearance between the lid plate and the enclosure end face

// Castellations: tabs on the enclosure's wall ends that pass through notches cut
// out of the lid's rim. enclosure() and lid() both take a `castellations` flag;
// passing false renders the parts with no interface, which is what
// enclosure/check_castellations.py subtracts to get the tab and notch volumes.
// cast_d + cast_clr has to stay below lid_t - fit_clr, otherwise a tab would
// poke through the outside of the lid.
cast_d    = wall;   // how far a tab sticks out of the wall end (X)
cast_w    = 3.0;    // tab width along the rim
cast_gap  = 3.0;    // gap between neighbouring tabs
cast_pd   = 1.0;    // tab depth into the wall (perpendicular to the rim)
cast_clr  = 0.1;    // clearance between a tab and its notch
cast_off  = 1.0;    // offset of the first tab from the rim corner

// ---- Derived sizes ----
cav_x = board_x + 2*side_clr;   // 29.8
cav_y = board_y + 2*side_clr;   // 23.8
cav_z = board_z + top_clr;      // 16.6
out_x = cav_x + wall;           // 31.3  (the slide-in end is closed by the lid)
out_y = cav_y + 2*wall;         // 26.8
out_z = cav_z + 2*wall;         // 19.6

// Board slot: a tight channel along X that the board slides into from the
// left. It is the lower part of the cavity, narrowed in Y (by fin_w per
// side) and only slot_h tall (board_z + slot_clr), so its walls grip the
// board in Y and its ceiling stops it in Z, capturing it fully. The
// full-width upper cavity sits above the slot for the barrels.
fin_w  = side_clr - slot_clr;   // 0.2 (slot narrowing per side, in Y)
slot_h = board_z + slot_clr;    // 1.8 (slot channel height, from the floor)

// RCA barrel geometry
barrel_dia = 8.3;               // barrel outer diameter (mm)
open_dia   = barrel_dia + 0.7;  // end-face opening diameter (9.0)
barrel_h   = 6.5;               // barrel axis height above the board top
axis_y     = wall + side_clr + board_y/2;  // 13.4 (board Y center)
axis_z     = wall + board_z + barrel_h;    // 9.6  (barrel axis Z)

// Castellation layout. The rim at the open end is a ring of wall material: the
// top and bottom walls run along Y, the left and right walls along Z. Each tab
// starts cast_off from the inner corner of the ring and repeats every
// cast_w + cast_gap, stopping before the far corner so the tabs of the two
// walls meeting at a corner never overlap.
function rim_starts(from, to) = [
  for (t = from; t + cast_w <= to; t = t + cast_w + cast_gap) t
];
rim_y = rim_starts(wall + cast_off, out_y - wall);  // top and bottom walls
rim_z = rim_starts(wall + cast_off, out_z - wall);  // left and right walls

// The enclosure is a box with the slide-in end open. The board slides into a
// tight slot (a channel along X, open at the slide-in end) that grips the
// board in Y and Z, holding it securely; the space above the slot is full
// width for the RCA barrels and jack bodies. The right end face has a hole
// for the J2 RCA barrel. The ends of the four walls carry the castellation tabs
// that pass through the notches cut in the lid's rim. The J1 barrel passes
// through a matching hole in the lid (see lid() below).
module enclosure(castellations = true) {
  difference() {
    // Outer shell.
    cube([out_x, out_y, out_z]);
    // Board slot: the lower part of the internal cavity, a tight channel along
    // X, open on the left (slide-in) end. Narrowed in Y (by fin_w per side) and
    // only slot_h tall, so its walls grip the board in Y and its ceiling stops
    // it in Z, capturing it fully. The board slides in from the left and is
    // held securely by this slot.
    translate([0, wall + fin_w, wall])
      cube([cav_x, cav_y - 2*fin_w, slot_h]);
    // Upper cavity: the full-width space above the slot, for the RCA barrels
    // and jack bodies.
    translate([0, wall, wall + slot_h])
      cube([cav_x, cav_y, cav_z - slot_h]);
    // Right end-face RCA barrel opening: a hole through the right wall, along
    // X, centered on the barrel axis (axis_y, axis_z).
    translate([cav_x - 1, axis_y, axis_z])
      rotate([0, 90, 0])
        cylinder(h = wall + 2, d = open_dia, $fn = 64);
  }

  // Castellation tabs on the wall ends, sticking out by cast_d so they thread
  // through the notches cut in the lid.
  if (castellations) {
    // Top and bottom walls, tabs spaced along Y.
    for (t = rim_y) {
      translate([-cast_d, t, out_z - cast_pd]) cube([cast_d, cast_w, cast_pd]);
      translate([-cast_d, t, 0]) cube([cast_d, cast_w, cast_pd]);
    }
    // Left (slide-in) and right walls, tabs spaced along Z.
    for (t = rim_z) {
      translate([-cast_d, 0, t]) cube([cast_d, cast_pd, cast_w]);
      translate([-cast_d, out_y - cast_pd, t]) cube([cast_d, cast_pd, cast_w]);
    }
  }
}

// ---- Lid (separate part) ----
// The lid is a plate of uniform thickness whose rim is notched: one notch for
// each tab on the enclosure's wall ends, cast_clr wider than the tab and cut
// cast_d + cast_clr deep from the mating face, leaving lid_t - cast_d - cast_clr
// of material at the outer face. Nothing sticks out of the plate, so the lid
// stays one thickness. Rotating the lid about the mating axis (X) drives the
// notch walls into the tabs, so the lid cannot turn; pulling it straight off is
// resisted only by friction.
module lid(castellations = true) {
  difference() {
    // Lid plate (with clearance to the enclosure shell at the open end).
    translate([-lid_t, 0, 0])
      cube([lid_t - fit_clr, out_y, out_z]);
    // Notches for the enclosure's wall tabs, cast_clr roomier than the tab on
    // the inside and open at the lid's outer edge.
    if (castellations) {
      for (t = rim_y) {
        // Top wall tabs.
        translate([-cast_d - cast_clr, t - cast_clr, out_z - cast_pd - cast_clr])
          cube([cast_d + cast_clr - fit_clr,
                cast_w + 2 * cast_clr, cast_pd + 2 * cast_clr]);
        // Bottom wall tabs.
        translate([-cast_d - cast_clr, t - cast_clr, -cast_clr])
          cube([cast_d + cast_clr - fit_clr,
                cast_w + 2 * cast_clr, cast_pd + 2 * cast_clr]);
      }
      for (t = rim_z) {
        // Left (slide-in) wall tabs.
        translate([-cast_d - cast_clr, -cast_clr, t - cast_clr])
          cube([cast_d + cast_clr - fit_clr,
                cast_pd + 2 * cast_clr, cast_w + 2 * cast_clr]);
        // Right wall tabs.
        translate([-cast_d - cast_clr, out_y - cast_pd - cast_clr, t - cast_clr])
          cube([cast_d + cast_clr - fit_clr,
                cast_pd + 2 * cast_clr, cast_w + 2 * cast_clr]);
      }
    }
    // J1 barrel opening: a hole through the lid plate, along X, centered on
    // the barrel axis (axis_y, axis_z).
    translate([-lid_t - 1, axis_y, axis_z])
      rotate([0, 90, 0])
        cylinder(h = lid_t + 2, d = open_dia, $fn = 64);
  }
}

// ---- Print orientations ----
// Both parts print with the castellation interface facing up (+Z): the body
// stands on its solid far end wall with the sockets opening at the top, and the
// lid lies flat on its plate with the teeth pointing up. In that orientation the
// RCA barrel bores run vertically with their outer openings downward.
module enclosure_print() {
  translate([0, 0, out_x]) rotate([0, 90, 0]) enclosure();
}

module lid_print() {
  translate([out_z, 0, lid_t]) rotate([0, -90, 0]) lid();
}

// Both parts in their print orientations, side by side with their long edges
// facing each other and a 2 mm gap, so one STL can hold the whole print job and
// the footprint stays close to square rather than a 19.6 x 55.6 strip.
module print_all() {
  enclosure_print();
  translate([out_z + 2, 0, 0]) lid_print();
}

// ---- Render both parts ----
enclosure();
lid();
