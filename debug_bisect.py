import bpy
import bmesh
from mathutils import Vector

bm = bmesh.new()
bmesh.ops.create_cube(bm, size=2.0)
bmesh.ops.bisect_plane(
    bm,
    geom=list(bm.verts) + list(bm.edges) + list(bm.faces),
    plane_co=Vector((0,0,0)),
    plane_no=Vector((1,0,0)),
    clear_outer=True,
    clear_inner=False,
)
loops = [e for e in bm.edges if e.is_boundary]
print('before', len(bm.faces), len(loops))
bmesh.ops.holes_fill(bm, edges=loops, sides=0)
print('after', len(bm.faces), sum(1 for e in bm.edges if e.is_boundary), 'is_valid', all(f.is_valid for f in bm.faces))
for f in bm.faces:
    print('face verts', len(f.verts), 'normal', tuple(round(x,3) for x in f.normal))
