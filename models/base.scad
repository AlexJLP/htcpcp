include <config.scad>

base_view_mode = "assembly"; // ["assembly", "base", "lid"]

if (base_view_mode == "assembly") {
    colour(colour_base) enclosure_base();
    
    colour(colour_lid) 
        translate([0, 0, chassis_height]) 
        enclosure_lid();
        
    // Place mock electronics
    translate([-chassis_width/2 + 8, -chassis_length/2 + 8, wall_thickness + pi_standoff_h])
        mock_raspberry_pi_3();
        
    translate([chassis_width/2 - bb_w - 8, -chassis_length/2 + 9, wall_thickness])
        mock_breadboard();
        
    translate([0, 0, chassis_height + lid_height - 3])
        rotate([0, 0, 180])
        mock_ssd1306_oled();
} else if (base_view_mode == "base") {
    enclosure_base();
} else if (base_view_mode == "lid") {
    // Oriented for printing
    translate([0, 0, lid_height + wall_thickness]) rotate([180, 0, 0]) enclosure_lid();
}


// Lower base shell
module enclosure_base() {
    difference() {
        // Main block
        rounded_box(chassis_width + 2*wall_thickness, chassis_length + 2*wall_thickness, chassis_height + wall_thickness, corner_radius);
        
        // Inner cavity
        translate([0, 0, wall_thickness])
            rounded_box(chassis_width, chassis_length, chassis_height + 2, corner_radius - wall_thickness);
            
        // Left wall cutouts for Pi 3 B+ side ports
        translate([-chassis_width/2 - wall_thickness - 2, -chassis_length/2 + 8, wall_thickness + pi_standoff_h]) {
            // Micro-USB Power
            translate([-1, 10.6 - 5.0, -1.5])
                cube([wall_thickness + 6, 10.0, 6.5]);
            // Full-Size HDMI
            translate([-1, 32.0 - 8.5, -1.5])
                cube([wall_thickness + 6, 17.0, 9.0]);
            // A/V Jack
            translate([-1, 53.5, 1.5])
                rotate([0, 90, 0])
                cylinder(d=8.5, h=wall_thickness + 6);
        }
        
        // Rear wall cutouts for Ethernet and USB ports
        translate([-chassis_width/2 + 8, -chassis_length/2 - wall_thickness - 2, wall_thickness + pi_standoff_h]) {
            // Ethernet
            translate([pi_pcb_l - 20 - 1.5, -1, 0])
                cube([21 + 3, wall_thickness + 6, 13.5 + 2]);
            // Dual USB stack 1 & 2
            translate([pi_pcb_l - 17 - 1.5, -1, 0])
                cube([14 + 3, wall_thickness + 6, 15.5 + 2]);
            translate([pi_pcb_l - 17 - 1.5 + 17, -1, 0])
                cube([14 + 3, wall_thickness + 6, 15.5 + 2]);
        }
        
        // Power jack hole (12V DC, on right wall)
        translate([chassis_width/2 + 1, -chassis_length/2 + 30, wall_thickness + 10])
            rotate([0, 90, 0])
            cylinder(d=11.5, h=wall_thickness + 4);
            
        // Temp probe wire exit slot
        translate([chassis_width/2 - 20, chassis_length/2 - 1, wall_thickness + chassis_height - 10])
            cube([8, wall_thickness + 4, 12]);
            
        // Air vents (left & right walls)
        for (i = [-2 : 2]) {
            translate([-chassis_width/2 - wall_thickness - 1, i*12, wall_thickness + 12])
                cube([wall_thickness + 4, 5, 18]);
            translate([chassis_width/2 - 1, i*12, wall_thickness + 12])
                cube([wall_thickness + 4, 5, 18]);
        }
        
        // Corner lid screws and nut pockets on bottom
        for (x = [-1, 1], y = [-1, 1]) {
            translate([x * (chassis_width/2 - 6), y * (chassis_length/2 - 6), -1])
                cylinder(d=3.2, h=wall_thickness + chassis_height + 5);
            translate([x * (chassis_width/2 - 6), y * (chassis_length/2 - 6), -1])
                cylinder(d=6.2, h=3.5, $fn=6);
        }
    }
    
    // Pi 3 B+ mounting pegs
    translate([-chassis_width/2 + 8, -chassis_length/2 + 8, wall_thickness]) {
        pi_standoff_peg(pi_hole_offset_x, pi_hole_offset_y);
        pi_standoff_peg(pi_hole_offset_x + pi_hole_spacing_x, pi_hole_offset_y);
        pi_standoff_peg(pi_hole_offset_x, pi_hole_offset_y + pi_hole_spacing_y);
        pi_standoff_peg(pi_hole_offset_x + pi_hole_spacing_x, pi_hole_offset_y + pi_hole_spacing_y);
    }
    
    // Breadboard retention guide walls
    translate([chassis_width/2 - bb_w - 8, -chassis_length/2 + 9, wall_thickness]) {
        translate([-1.5, -1.5, 0]) cube([1.5, bb_l + 3, 2.0]);
        translate([bb_w, -1.5, 0]) cube([1.5, bb_l + 3, 2.0]);
        translate([-1.5, bb_l, 0]) cube([bb_w + 3, 1.5, 2.0]);
        translate([-1.5, -1.5, 0]) cube([bb_w + 3, 1.5, 2.0]);
    }
    
    // Internal corner screw bosses
    for (x = [-1, 1], y = [-1, 1]) {
        translate([x * (chassis_width/2 - 6), y * (chassis_length/2 - 6), wall_thickness])
            difference() {
                cylinder(r=6, h=chassis_height - wall_thickness);
                cylinder(d=2.8, h=chassis_height); // Pilot holes
            }
    }
}

// Helper for Pi standoff pegs
module pi_standoff_peg(px, py) {
    translate([px, py, 0])
        difference() {
            cylinder(d=6.0, h=pi_standoff_h);
            cylinder(d=2.2, h=pi_standoff_h + 1); // For M2.5 screws
        }
}

// Upper console lid
module enclosure_lid() {
    difference() {
        union() {
            // Top lid cover
            difference() {
                rounded_box(chassis_width + 2*wall_thickness, chassis_length + 2*wall_thickness, lid_height + wall_thickness, corner_radius);
                
                translate([0, 0, -1])
                    rounded_box(chassis_width + tolerance, chassis_length + tolerance, lid_height + 2, corner_radius - wall_thickness);
            }
            
            // Inner rim to align lid to base
            translate([0, 0, -3.0])
                difference() {
                    rounded_box(chassis_width - 0.4, chassis_length - 0.4, 3.5, corner_radius - 1);
                    translate([0, 0, -1])
                        rounded_box(chassis_width - 2*wall_thickness, chassis_length - 2*wall_thickness, 6, corner_radius - wall_thickness);
                }
        }
        
        // OLED screen cutout
        translate([0, 0, -2]) {
            translate([-oled_bezel_w/2, -oled_bezel_h/2 + 2, 0])
                cube([oled_bezel_w, oled_bezel_h, wall_thickness + 10]);
            // Beveled recess
            translate([-oled_bezel_w/2 - 1.5, -oled_bezel_h/2 + 0.5, lid_height + wall_thickness - 2])
                cube([oled_bezel_w + 3, oled_bezel_h + 3, 3]);
        }
        
        // Counter-sunk screw holes on corners
        for (x = [-1, 1], y = [-1, 1]) {
            translate([x * (chassis_width/2 - 6), y * (chassis_length/2 - 6), -5])
                cylinder(d=3.4, h=lid_height + wall_thickness + 10);
            translate([x * (chassis_width/2 - 6), y * (chassis_length/2 - 6), lid_height + wall_thickness - 3.5])
                cylinder(d=6.5, h=4.0);
        }
    }
    
    // OLED mount standoffs
    translate([0, 0, wall_thickness + 0.5]) {
        for (x = [-1, 1], y = [-1, 1]) {
            translate([x * oled_hole_spacing/2, y * oled_hole_spacing/2, 0])
                difference() {
                    cylinder(d=5.0, h=4.5);
                    cylinder(d=1.8, h=6.0); // For M2 self-tapping screws
                }
        }
    }
}
