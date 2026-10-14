// Placeholder: low polygon count for the original DOS renderer.
// Z is up. The converter uniformly fits this mesh into its selected city slot.
$fn = 8;
union() {
    translate([-12,-10,0]) cube([24,20,8]);
    translate([-9,-7,8]) cube([18,14,35]);
    translate([0,0,43]) cylinder(h=10,r1=11,r2=3);
}
