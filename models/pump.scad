include <config.scad>

pump_view_mode = "assembly"; // ["assembly", "base", "lid"]

if (pump_view_mode == "assembly") {
    colour(colour_base) pump_enclosure_base();
    
    colour(colour_lid) 
        translate([0, 0, pump_box_h + pump_wall - 1]) 
        pump_enclosure_lid();
        
    // Mock water pump inside sleeve
    translate([0, -pump_box_l/2 + pump_wall + 3, pump_wall + pump_d/2 + 1])
        rotate([-90, 0, 180])
        mock_water_pump();
} else if (pump_view_mode == "base") {
    pump_enclosure_base();
} else if (pump_view_mode == "lid") {
    // Lay flat on back for printing
    translate([0, 0, pump_wall]) rotate([0, 180, 0]) pump_enclosure_lid();
}


// Pump sleeve base
module pump_enclosure_base() {
    difference() {
        union() {
            // Main sleeve box
            translate([-pump_box_w/2 - pump_wall, -pump_box_l/2 - pump_wall, 0])
                cube([pump_box_w + 2*pump_wall, pump_box_l + 2*pump_wall+2, pump_box_h + pump_wall]);
                
            // 2020 profile mounting tabs on left wall
            if (pump_extrusion_mount) {
                translate([-pump_box_w/2 - pump_wall - 12, -pump_box_l/2 + 8, 0])
                    cube([12, 14, 6]);
                translate([-pump_box_w/2 - pump_wall - 12, pump_box_l/2 - 22, 0])
                    cube([12, 14, 6]);
            }
        }
            
        // Inner compartment
        translate([-pump_box_w/2, -pump_box_l/2, pump_wall])
            cube([pump_box_w, pump_box_l + 2, pump_box_h + 2]);
            
        // Front wall tubing outlets
        translate([0, pump_box_l/2 - 2, pump_wall + 32.5]) {
            translate([-6, 0, 0]) rotate([-90, 0, 0]) cylinder(d=pump_outlet_hole_d, h=pump_wall + 6);
            translate([6, 0, 0]) rotate([-90, 0, 0]) cylinder(d=pump_outlet_hole_d, h=pump_wall + 6);
        }
        
        // Back wall wire slot
        translate([-4, -pump_box_l/2 - pump_wall - 1, pump_wall])
            cube([8, pump_wall + 2, 8]);
            
        // Sliding lid guide tracks (left & right walls)
        translate([-pump_box_w/2 - 0.2, -pump_box_l/2 - 1, pump_box_h + pump_wall - 4.5])
            cube([1.8, pump_box_l + 4, 2.5]);
        translate([pump_box_w/2 - 1.6, -pump_box_l/2 - 1, pump_box_h + pump_wall - 4.5])
            cube([1.8, pump_box_l + 4, 2.5]);
            
        // Mounting insert holes on tabs
        if (pump_extrusion_mount) {
            translate([-pump_box_w/2 - pump_wall - 6, -pump_box_l/2 + 15, -1])
                cylinder(d=pump_m4_insert_d, h=8);
            translate([-pump_box_w/2 - pump_wall - 6, pump_box_l/2 - 15, -1])
                cylinder(d=pump_m4_insert_d, h=8);
        }
    }
    
    // Internal mounting partition wall
    translate([0, 10.25, pump_wall])
        difference() {
            translate([-pump_box_w/2 + 0.2, -1.75, 0])
                cube([pump_box_w - 0.4, 3.5, pump_box_h]);
            
            // U-slot to slide motor body into place
            translate([0, -3, 18.0 - pump_wall])
                rotate([-90, 0, 0])
                cylinder(d=29.5, h=10);
            translate([-29.5/2, -3, 18.0 - pump_wall])
                cube([29.5, 10, pump_box_h]);
                
            // Holes for M3 partition mounting screws
            translate([-24.25, -3, 18.0 - pump_wall])
                rotate([-90, 0, 0])
                cylinder(d=3.4, h=10);
            translate([24.25, -3, 18.0 - pump_wall])
                rotate([-90, 0, 0])
                cylinder(d=3.4, h=10);
        }

    // Vertical guide rails for partition wall
    translate([-pump_box_w/2, 15.5, pump_wall]) cube([3.0, 2.0, pump_box_h]);
    translate([pump_box_w/2 - 3.0, 15.5, pump_wall]) cube([3.0, 2.0, pump_box_h]);
        
    // Motor support cradle rib
    translate([0, -15, pump_wall])
        pump_rib_cradle();
}

// Rib to support bottom of motor body
module pump_rib_cradle() {
    difference() {
        translate([-pump_box_w/2 + 0.5, -2.5, 0])
            cube([pump_box_w - 1.0, 5, pump_d/2 + 1]);
        translate([0, -5, pump_d/2 + 1])
            rotate([-90, 0, 0])
            cylinder(d=pump_d + tolerance, h=10);
    }
}

// Sliding lid cover
module pump_enclosure_lid() {
    union() {
        // Main flat plate
        translate([-pump_box_w/2 + tolerance, -pump_box_l/2 + 1, 0])
            cube([pump_box_w - 2*tolerance, pump_box_l - 2, pump_wall]);
            
        // Side slide rail keys
        translate([-pump_box_w/2 - 1.2 + tolerance, -pump_box_l/2 + 2, 0.5])
            cube([1.2, pump_box_l - 4, 1.5]);
        translate([pump_box_w/2 - tolerance, -pump_box_l/2 + 2, 0.5])
            cube([1.2, pump_box_l - 4, 1.5]);
            
        // Pull tab at one end
        translate([-pump_box_w/2 + 5, -pump_box_l/2 + 4, pump_wall])
            difference() {
                cube([pump_box_w - 10, 6, 6]);
                translate([-1, 3, 3]) rotate([0, 90, 0]) cylinder(d=4, h=pump_box_w);
            }
    }
}
