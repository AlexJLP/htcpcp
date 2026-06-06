extrusion_outer_width = 200.0; // Your 2020 frame width (200mm)
extrusion_profile     = 20.0;  // 20mm profile width
wall_thickness        = 4.0;   // Beefier walls for smooth rounding
base_floor_thickness  = 4.0;   // The floor your mug sits on
guard_height          = 120.0; 
corner_radius         = 25.0;  // Controls the outer corner rounding
sr04_transceiver_dia = 16.2;   // Diameter for sonar cylinders
sr04_center_spacing  = 26.0;   // Center-to-center distance of the eyes
sensor_height_pos    = 40.0;   // Height of the sensor from the floor

outer_dim = extrusion_outer_width + (wall_thickness * 2);
lip_down  = 18.0; // How far the encapsulation walls drop down over the 2020 rails

$fn = 80; 

module rounded_cube_profile(width, depth, height, radius) {
    linear_extrude(height = height, center = true) {
        hull() {
            // Back corners are rounded
            translate([-(width/2 - radius), (depth/2 - radius)]) circle(r = radius);
            translate([(width/2 - radius), (depth/2 - radius)]) circle(r = radius);
            // Front corners remain sharp/square for the opening
            translate([-(width/2), -(depth/2)]) square([radius, radius]);
            translate([(width/2 - radius), -(depth/2)]) square([radius, radius]);
        }
    }
}

difference() {
    // 1. SOLID BASE + WALLS + ENCAPSULATION SKIRT
    union() {
        // Upper splashguard tower
        translate([0, 0, (guard_height + base_floor_thickness)/2])
            rounded_cube_profile(outer_dim, outer_dim, guard_height + base_floor_thickness, corner_radius);
        
        // Lower encapsulation skirt (drops DOWN over the outside of the 2020 frame)
        translate([0, 0, -lip_down/2])
            rounded_cube_profile(outer_dim, outer_dim, lip_down, corner_radius);
    }

    // 2. HOLLOW OUT THE MUG CHAMBER
    translate([0, -wall_thickness, (guard_height + 10)/2 + base_floor_thickness])
        rounded_cube_profile(extrusion_outer_width, extrusion_outer_width, guard_height + 10, corner_radius - wall_thickness);

    // 3. HOLLOW OUT THE BOTTOM 
    translate([0, 0, -lip_down])
        cube([extrusion_outer_width+10, extrusion_profile+0.5, lip_down * 2], center = true);

    // 4. CUT OUT THE FRONT OPENING
    translate([0, -outer_dim/2, (guard_height + lip_down + 10)/2])
        cube([outer_dim + 2, outer_dim, guard_height + lip_down + 20], center = true);

    // 5. HORIZONTAL HC-SR04 MOUNT (Cut through the center-back wall)
    translate([0, (outer_dim/2) - (wall_thickness/2), sensor_height_pos + base_floor_thickness]) {
        rotate([90, 0, 0]) {
            // Left
            translate([-sr04_center_spacing/2, 0, 0])
                cylinder(h = wall_thickness * 3+1, d = sr04_transceiver_dia, center = true);
            // Right
            translate([sr04_center_spacing/2, 0, 0])
                cylinder(h = wall_thickness * 3+1, d = sr04_transceiver_dia, center = true);
        }
    }

    // 6. SPILL GROOVES
    for (r = [30 : 20 : 70]) {
        translate([0, 10, base_floor_thickness])
            difference() {
                cylinder(h = 2.0, r = r + 1.25, center = true);
                cylinder(h = 3.0, r = r - 1.25, center = true);
            }
    }
}



//    translate([0, 0, -lip_down])
//        cube([extrusion_outer_width+10, extrusion_profile+0.5, lip_down * 2], center = true);
