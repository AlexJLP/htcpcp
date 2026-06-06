// General
$fn = 60; // Curve resolution
tolerance = 0.4; // Clearance for 3D printed parts (mm)

// Main console box
wall_thickness = 3.0;
corner_radius = 6.0;
chassis_width = 132.0; // Fits Pi and breadboard side-by-side
chassis_length = 100.0;
chassis_height = 42.0;
lid_height = 10.0;

// Raspberry Pi 3 B+
pi_pcb_l = 85.0;
pi_pcb_w = 56.0;
pi_pcb_h = 1.6;
pi_standoff_h = 6.0;
pi_hole_spacing_x = 58.0;
pi_hole_spacing_y = 49.0;
pi_hole_offset_x = 3.5;
pi_hole_offset_y = 3.5;
pi_hole_d = 2.5;

// Half-size breadboard
bb_l = 82.0;
bb_w = 53.0;
bb_h = 8.5;

// SSD1306 0.96" OLED screen
oled_pcb_w = 27.3;
oled_pcb_h = 27.8;
oled_hole_spacing = 22.0;
oled_hole_d = 2.0;
oled_screen_w = 22.5;
oled_screen_h = 12.5;
oled_bezel_w = oled_screen_w + 1.0;
oled_bezel_h = oled_screen_h + 1.0;

// Water pump pod
pump_d = 29.0; // Motor diameter
pump_l = 67.5; // Total length
pump_nozzle_d = 5.0;
pump_nozzle_l = 15.0;
pump_outlet_hole_d = 5.0; // Enclosure tube holes

// Pump box inner dimensions
pump_box_w = 56.0;
pump_box_l = 75.0;
pump_box_h = 42.0;
pump_wall = 2.5;

// 2020 extrusion mount config for pump pod
pump_extrusion_mount = true;
pump_m4_insert_d = 5.9; // Hole diameter for heat-set inserts

// Colour palette
colour_base = [0.15, 0.15, 0.15, 1.0]; // Charcoal Dark
colour_lid = [0.25, 0.35, 0.45, 1.0]; // Steel Blue
colour_pcb_green = [0.1, 0.5, 0.2, 1.0];
colour_pcb_blue = [0.1, 0.2, 0.6, 1.0];
colour_breadboard = [0.93, 0.93, 0.88, 1.0];
colour_metal = [0.75, 0.75, 0.75, 1.0];
colour_dark_metal = [0.3, 0.3, 0.3, 1.0];
colour_brass = [0.78, 0.61, 0.23, 1.0];
colour_glass = [0.2, 0.2, 0.2, 0.8];
colour_pump = [0.8, 0.8, 0.8, 0.9];


// Helper to support British spelling for OpenSCAD's color module
module colour(c) {
    color(c) children();
}

// Draw a rounded box chassis
module rounded_box(w, l, h, r) {
    translate([-w/2 + r, -l/2 + r, 0])
        minkowski() {
            cube([w - 2*r, l - 2*r, h - 1.0]);
            cylinder(r=r, h=1.0);
        }
}

module mock_raspberry_pi_3() {
    // Green PCB
    colour(colour_pcb_green)
        difference() {
            cube([pi_pcb_l, pi_pcb_w, pi_pcb_h]);
            // Standoff mount holes
            translate([pi_hole_offset_x, pi_hole_offset_y, -1]) 
                cylinder(d=pi_hole_d, h=pi_pcb_h+2);
            translate([pi_hole_offset_x + pi_hole_spacing_x, pi_hole_offset_y, -1]) 
                cylinder(d=pi_hole_d, h=pi_pcb_h+2);
            translate([pi_hole_offset_x, pi_hole_offset_y + pi_hole_spacing_y, -1]) 
                cylinder(d=pi_hole_d, h=pi_pcb_h+2);
            translate([pi_hole_offset_x + pi_hole_spacing_x, pi_hole_offset_y + pi_hole_spacing_y, -1]) 
                cylinder(d=pi_hole_d, h=pi_pcb_h+2);
        }
        
    // Ethernet and USB port stacks
    colour(colour_metal) {
        // RJ45 Ethernet port
        translate([pi_pcb_l - 20, 2, pi_pcb_h])
            cube([21, 16, 13.5]);
        // Dual USB 2.0 ports (middle and top stacks)
        translate([pi_pcb_l - 17, 22, pi_pcb_h])
            cube([18, 14, 15.5]);
        translate([pi_pcb_l - 17, 39, pi_pcb_h])
            cube([18, 14, 15.5]);
    }
    
    // Bottom edge ports (Micro-USB power, HDMI, and A/V jack)
    colour(colour_metal) {
        // Micro-USB
        translate([10.6 - 4, -2, pi_pcb_h])
            cube([8, 7.5, 3.0]);
        // HDMI
        translate([32.0 - 7.5, -2, pi_pcb_h])
            cube([15, 9.5, 6.0]);
        // A/V Jack
        translate([53.5, -2, pi_pcb_h])
            rotate([-90, 0, 0]) cylinder(d=6, h=8);
    }
    
    // GPIO Header
    colour(colour_brass)
        translate([29, pi_pcb_w - 6, pi_pcb_h])
            cube([51, 5, 8.5]);
            
    // CPU chip
    colour(colour_dark_metal)
        translate([26, 22, pi_pcb_h])
            cube([15, 15, 4]);
}

module mock_breadboard() {
    colour(colour_breadboard)
        cube([bb_w, bb_l, bb_h]);
        
    // Red & Blue power lines
    colour([0.8, 0.1, 0.1, 1.0]) {
        translate([3, 5, bb_h]) cube([1, bb_l - 10, 0.2]);
        translate([bb_w - 4, 5, bb_h]) cube([1, bb_l - 10, 0.2]);
    }
    colour([0.1, 0.1, 0.8, 1.0]) {
        translate([6, 5, bb_h]) cube([1, bb_l - 10, 0.2]);
        translate([bb_w - 7, 5, bb_h]) cube([1, bb_l - 10, 0.2]);
    }
}

module mock_ssd1306_oled() {
    // Blue board
    colour(colour_pcb_blue)
        difference() {
            translate([-oled_pcb_w/2, -oled_pcb_h/2, 0])
                cube([oled_pcb_w, oled_pcb_h, 1.2]);
            // Mount holes
            for (x = [-1, 1], y = [-1, 1]) {
                translate([x * oled_hole_spacing/2, y * oled_hole_spacing/2, -1])
                    cylinder(d=oled_hole_d, h=4);
            }
        }
    
    // Glass display face
    colour(colour_glass)
        translate([-oled_screen_w/2, -oled_screen_h/2 + 2, 1.2])
            cube([oled_screen_w, oled_screen_h, 1.5]);
            
    // Pins
    colour(colour_brass)
        translate([-6, oled_pcb_h/2 - 2, -6])
            cube([12, 2.5, 6]);
}

module mock_water_pump() {
    // Motor body (silver)
    colour(colour_metal) {
        cylinder(d=29, h=44);
        // Back terminals
        translate([-6, 0, -3]) cylinder(d=2, h=3);
        translate([6, 0, -3]) cylinder(d=2, h=3);
    }
    
    // Mounting flange (black plate)
    colour(colour_dark_metal)
        translate([0, 0, 44]) {
            difference() {
                hull() {
                    cylinder(d=40.3, h=3.5);
                    translate([-54.5/2 + 3, 0, 0]) cylinder(d=6, h=3.5);
                    translate([54.5/2 - 3, 0, 0]) cylinder(d=6, h=3.5);
                }
                translate([-48.5/2, 0, -1]) cylinder(d=3.2, h=6);
                translate([48.5/2, 0, -1]) cylinder(d=3.2, h=6);
            }
        }
        
    // Pump head (blue)
    colour(colour_pcb_blue) {
        translate([0, 0, 47.5]) {
            cylinder(d=35, h=20);
            translate([0, 0, 20]) cylinder(d=32, h=3.5);
            // Tubing ports
            translate([-6, 14, 10]) rotate([-90, 0, 0]) cylinder(d=5, h=12);
            translate([6, 14, 10]) rotate([-90, 0, 0]) cylinder(d=5, h=12);
        }
    }
    
    // Translucent silicone tubing
    colour([0.9, 0.9, 0.9, 0.6]) {
        translate([0, 0, 47.5]) {
            translate([-6, 14 + 12, 10]) cylinder(d=4, h=60);
            translate([6, 14 + 12, 10]) cylinder(d=4, h=60);
        }
    }
}

module mock_2020_extrusion(length = 150) {
    // 2020 Aluminum profile mock
    colour(colour_metal)
        difference() {
            translate([-10, -length/2, -20])
                cube([20, length, 20]);
            
            // Central core
            translate([0, -length/2 - 1, -10])
                rotate([-90, 0, 0])
                cylinder(d=5, h=length + 2);
                
            // Slots on 4 sides
            translate([-3, -length/2 - 1, -6]) cube([6, length + 2, 7]);
            translate([-5.5, -length/2 - 1, -12]) cube([11, length + 2, 6]);
                
            translate([-3, -length/2 - 1, -21]) cube([6, length + 2, 7]);
            translate([-5.5, -length/2 - 1, -14]) cube([11, length + 2, 6]);
                
            translate([-11, -length/2 - 1, -13]) cube([7, length + 2, 6]);
            translate([-14, -length/2 - 1, -15.5]) cube([6, length + 2, 11]);
                
            translate([4, -length/2 - 1, -13]) cube([7, length + 2, 6]);
            translate([8, -length/2 - 1, -15.5]) cube([6, length + 2, 11]);
        }
}
