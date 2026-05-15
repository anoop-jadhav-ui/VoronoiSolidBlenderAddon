bl_info = {
    "name": "Voronoi Solid Pattern",
    "author": "Hermes Agent",
    "version": (0, 2, 0),
    "blender": (4, 3, 0),
    "location": "View3D > Sidebar > Voronoi",
    "description": "Generate Voronoi-style cells from any closed mesh solid",
    "category": "Object",
}

import random

import bpy
import bmesh
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import Operator, Panel, PropertyGroup
from mathutils import Matrix, Vector


EPSILON = 1e-6


class VoronoiSolidSettings(PropertyGroup):
    generation_mode: EnumProperty(
        name="Mode",
        items=(
            ('SOLID', "Solid Cells", "Generate solid Voronoi cells throughout the volume"),
            ('LATTICE', "Lattice Seeds", "Use shell-oriented surface-biased seeding for lattice development"),
        ),
        default='SOLID',
    )
    seed_count: IntProperty(
        name="Cells",
        default=12,
        min=2,
        max=250,
        description="How many Voronoi cells to generate inside the selected solid",
    )
    surface_seed_count: IntProperty(
        name="Surface Seeds",
        default=18,
        min=0,
        max=500,
        description="How many seeds to place near the surface shell in Lattice mode",
    )
    interior_seed_count: IntProperty(
        name="Interior Seeds",
        default=4,
        min=0,
        max=500,
        description="How many additional interior seeds to mix into Lattice mode",
    )
    random_seed: IntProperty(
        name="Random Seed",
        default=1,
        min=0,
        description="Seed for reproducible point generation",
    )
    gap: FloatProperty(
        name="Gap",
        default=0.08,
        min=0.0,
        max=0.95,
        subtype='FACTOR',
        description="Shrink each generated cell toward its site to create visible gaps",
    )
    surface_shell_depth: FloatProperty(
        name="Shell Depth",
        default=0.12,
        min=0.0,
        max=10.0,
        description="How far surface seeds can move inward from the mesh surface in Lattice mode",
    )
    surface_shell_bias: FloatProperty(
        name="Shell Bias",
        default=1.0,
        min=0.0,
        max=1.0,
        subtype='FACTOR',
        description="Higher values keep lattice surface seeds closer to the outer shell",
    )
    sample_attempt_multiplier: IntProperty(
        name="Sample Attempts x",
        default=40,
        min=5,
        max=500,
        description="More attempts helps fill thin or complex solids with points",
    )
    keep_original: BoolProperty(
        name="Keep Original",
        default=True,
        description="Leave the source mesh visible after generation",
    )
    collection_name: StringProperty(
        name="Collection",
        default="VoronoiCells",
        description="Base name for the generated collection",
    )
    join_cells: BoolProperty(
        name="Join Cells",
        default=True,
        description="Join all generated cells into one mesh object so one modifier affects the whole result",
    )


class OBJECT_OT_generate_voronoi_solid_cells(Operator):
    bl_idname = "object.generate_voronoi_solid_cells"
    bl_label = "Generate Voronoi Cells"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH'

    def execute(self, context):
        settings = context.scene.voronoi_solid_settings
        source_obj = context.active_object

        if source_obj.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        if not source_obj.data.polygons:
            self.report({'ERROR'}, "Selected object has no faces")
            return {'CANCELLED'}

        depsgraph = context.evaluated_depsgraph_get()
        source_bm = build_world_bmesh(source_obj, depsgraph)

        if len(source_bm.faces) == 0:
            source_bm.free()
            self.report({'ERROR'}, "Unable to evaluate mesh from active object")
            return {'CANCELLED'}

        try:
            seeds = generate_seed_points(source_obj, settings, depsgraph)
        except RuntimeError as exc:
            source_bm.free()
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}

        target_collection = ensure_unique_collection(context.scene.collection, settings.collection_name or f"{source_obj.name}_Voronoi")
        target_collection["voronoi_generation_mode"] = settings.generation_mode
        target_collection["voronoi_seed_count"] = len(seeds)

        created = 0
        created_objects = []
        for index, seed in enumerate(seeds, start=1):
            cell_bm = build_voronoi_cell(source_bm, seeds, index - 1)
            if cell_bm is None or len(cell_bm.faces) == 0:
                if cell_bm is not None:
                    cell_bm.free()
                continue

            if settings.gap > 0.0:
                shrink_cell(cell_bm, seed, settings.gap)

            mesh = bpy.data.meshes.new(f"{source_obj.name}_cell_{index:03d}")
            cell_bm.to_mesh(mesh)
            mesh.update()
            cell_bm.free()

            obj = bpy.data.objects.new(mesh.name, mesh)
            obj.matrix_world = Matrix.Identity(4)
            obj["voronoi_generation_mode"] = settings.generation_mode
            target_collection.objects.link(obj)
            created += 1
            created_objects.append(obj)

        source_bm.free()

        if created == 0:
            bpy.data.collections.remove(target_collection)
            self.report({'ERROR'}, "No Voronoi cells were generated")
            return {'CANCELLED'}

        if settings.join_cells and created_objects:
            joined_object = join_objects(context, created_objects, f"{source_obj.name}_voronoi")
            if joined_object is not None:
                joined_object["voronoi_generation_mode"] = settings.generation_mode
                created = 1

        if not settings.keep_original:
            source_obj.hide_set(True)
            source_obj.hide_render = True

        self.report({'INFO'}, f"Generated {created} Voronoi cells in collection '{target_collection.name}'")
        return {'FINISHED'}


class VIEW3D_PT_voronoi_solid_panel(Panel):
    bl_label = "Voronoi Solid"
    bl_idname = "VIEW3D_PT_voronoi_solid_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Voronoi'

    def draw(self, context):
        layout = self.layout
        settings = context.scene.voronoi_solid_settings
        obj = context.active_object

        col = layout.column(align=True)
        col.label(text=f"Active: {obj.name if obj else 'None'}")
        col.prop(settings, "generation_mode")

        if settings.generation_mode == 'SOLID':
            col.prop(settings, "seed_count")
        else:
            col.prop(settings, "surface_seed_count")
            col.prop(settings, "interior_seed_count")
            col.prop(settings, "surface_shell_depth")
            col.prop(settings, "surface_shell_bias")

        col.prop(settings, "random_seed")
        col.prop(settings, "gap")
        col.prop(settings, "sample_attempt_multiplier")
        col.prop(settings, "collection_name")
        col.prop(settings, "join_cells")
        col.prop(settings, "keep_original")
        layout.separator()
        layout.operator(OBJECT_OT_generate_voronoi_solid_cells.bl_idname, icon='MOD_BUILD')


def build_world_bmesh(obj, depsgraph):
    obj_eval = obj.evaluated_get(depsgraph)
    mesh = obj_eval.to_mesh(preserve_all_data_layers=False, depsgraph=depsgraph)
    if mesh is None:
        raise RuntimeError("Failed to evaluate selected mesh")

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.transform(bm, matrix=obj.matrix_world, verts=bm.verts)
    bm.normal_update()
    obj_eval.to_mesh_clear()
    return bm


def generate_seed_points(obj, settings, depsgraph):
    if settings.generation_mode == 'LATTICE':
        seeds = []
        if settings.surface_seed_count > 0:
            seeds.extend(
                sample_points_on_surface_shell(
                    obj,
                    settings.surface_seed_count,
                    settings.random_seed,
                    settings.surface_shell_depth,
                    settings.surface_shell_bias,
                    depsgraph,
                )
            )
        if settings.interior_seed_count > 0:
            seeds.extend(
                sample_points_inside_object(
                    obj,
                    settings.interior_seed_count,
                    settings.random_seed + 7919,
                    settings.sample_attempt_multiplier,
                    depsgraph,
                )
            )
        if not seeds:
            raise RuntimeError("Lattice mode needs at least one surface or interior seed")
        return seeds

    return sample_points_inside_object(
        obj,
        settings.seed_count,
        settings.random_seed,
        settings.sample_attempt_multiplier,
        depsgraph,
    )


def sample_points_inside_object(obj, target_count, random_seed, attempt_multiplier, depsgraph):
    bbox_world = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    min_corner = Vector((
        min(v.x for v in bbox_world),
        min(v.y for v in bbox_world),
        min(v.z for v in bbox_world),
    ))
    max_corner = Vector((
        max(v.x for v in bbox_world),
        max(v.y for v in bbox_world),
        max(v.z for v in bbox_world),
    ))

    rng = random.Random(random_seed)
    seeds = []
    attempts = max(target_count * attempt_multiplier, target_count)

    for _ in range(attempts):
        if len(seeds) >= target_count:
            break

        candidate = Vector((
            rng.uniform(min_corner.x, max_corner.x),
            rng.uniform(min_corner.y, max_corner.y),
            rng.uniform(min_corner.z, max_corner.z),
        ))

        if not point_is_inside_object(obj, candidate, depsgraph):
            continue

        seeds.append(candidate)

    if len(seeds) < target_count:
        raise RuntimeError(
            f"Only found {len(seeds)} interior sample points out of {target_count}. Increase attempts or use a cleaner closed mesh."
        )

    return seeds


def sample_points_on_surface_shell(obj, target_count, random_seed, shell_depth, shell_bias, depsgraph):
    triangles = get_surface_triangles(obj, depsgraph)
    if not triangles:
        raise RuntimeError("Could not extract surface triangles for lattice seeding")

    rng = random.Random(random_seed)
    total_area = sum(triangle[3] for triangle in triangles)
    if total_area <= EPSILON:
        raise RuntimeError("Surface triangle area is too small for lattice seeding")

    cumulative = []
    running = 0.0
    for triangle in triangles:
        running += triangle[3]
        cumulative.append(running)

    seeds = []
    attempts = max(target_count * 10, target_count)
    exponent = 1.0 + max(0.0, min(1.0, shell_bias)) * 4.0

    for _ in range(attempts):
        if len(seeds) >= target_count:
            break

        triangle = pick_triangle(triangles, cumulative, running, rng)
        surface_point = random_point_on_triangle(triangle[0], triangle[1], triangle[2], rng)
        normal = triangle[4]

        if shell_depth <= EPSILON:
            candidate = surface_point
        else:
            offset_distance = shell_depth * (rng.random() ** exponent)
            candidate = project_point_inside_shell(obj, surface_point, normal, offset_distance, depsgraph)
            if candidate is None:
                continue

        if not point_is_inside_object(obj, candidate, depsgraph):
            continue
        seeds.append(candidate)

    if len(seeds) < target_count:
        raise RuntimeError(
            f"Only found {len(seeds)} surface shell points out of {target_count}. Reduce shell depth or use a cleaner closed mesh."
        )

    return seeds


def get_surface_triangles(obj, depsgraph):
    obj_eval = obj.evaluated_get(depsgraph)
    mesh = obj_eval.to_mesh(preserve_all_data_layers=False, depsgraph=depsgraph)
    if mesh is None:
        return []

    mesh.calc_loop_triangles()
    triangles = []
    try:
        for loop_triangle in mesh.loop_triangles:
            a = obj.matrix_world @ mesh.vertices[loop_triangle.vertices[0]].co
            b = obj.matrix_world @ mesh.vertices[loop_triangle.vertices[1]].co
            c = obj.matrix_world @ mesh.vertices[loop_triangle.vertices[2]].co
            cross = (b - a).cross(c - a)
            area = cross.length * 0.5
            if area <= EPSILON:
                continue
            normal = cross.normalized()
            triangles.append((a, b, c, area, normal))
    finally:
        obj_eval.to_mesh_clear()

    return triangles


def pick_triangle(triangles, cumulative, total_area, rng):
    target = rng.uniform(0.0, total_area)
    for index, threshold in enumerate(cumulative):
        if target <= threshold:
            return triangles[index]
    return triangles[-1]


def random_point_on_triangle(a, b, c, rng):
    u = rng.random()
    v = rng.random()
    if u + v > 1.0:
        u = 1.0 - u
        v = 1.0 - v
    return a + (b - a) * u + (c - a) * v


def project_point_inside_shell(obj, surface_point, normal, offset_distance, depsgraph):
    inward = surface_point - normal * offset_distance
    if point_is_inside_object(obj, inward, depsgraph):
        return inward

    outward = surface_point + normal * offset_distance
    if point_is_inside_object(obj, outward, depsgraph):
        return outward

    if point_is_inside_object(obj, surface_point, depsgraph):
        return surface_point
    return None


def point_is_inside_object(obj, world_point, depsgraph):
    local_point = obj.matrix_world.inverted() @ world_point
    hit, location, normal, _face_index = obj.closest_point_on_mesh(local_point, depsgraph=depsgraph)
    if not hit:
        return False

    closest_world = obj.matrix_world @ location
    normal_world = obj.matrix_world.to_3x3() @ normal
    if normal_world.length <= EPSILON:
        return False

    normal_world.normalize()
    offset = world_point - closest_world
    return offset.dot(normal_world) <= EPSILON


def build_voronoi_cell(source_bm, seeds, current_index):
    seed = seeds[current_index]
    bm = source_bm.copy()

    for other_index, other_seed in enumerate(seeds):
        if other_index == current_index:
            continue

        delta = other_seed - seed
        if delta.length <= EPSILON:
            continue

        midpoint = seed.lerp(other_seed, 0.5)
        normal = delta.normalized()

        bmesh.ops.bisect_plane(
            bm,
            geom=list(bm.verts) + list(bm.edges) + list(bm.faces),
            plane_co=midpoint,
            plane_no=normal,
            clear_outer=True,
            clear_inner=False,
        )

        delete_loose_geometry(bm)
        if len(bm.faces) == 0:
            bm.free()
            return None

        boundary_edges = [edge for edge in bm.edges if edge.is_valid and edge.is_boundary]
        if boundary_edges:
            try:
                bmesh.ops.holes_fill(bm, edges=boundary_edges, sides=0)
            except RuntimeError:
                pass

        delete_loose_geometry(bm)
        if len(bm.faces) == 0:
            bm.free()
            return None

    try:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    except RuntimeError:
        pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bm.normal_update()
    return bm


def delete_loose_geometry(bm):
    loose_verts = [v for v in bm.verts if v.is_valid and not v.link_faces]
    if loose_verts:
        bmesh.ops.delete(bm, geom=loose_verts, context='VERTS')


def shrink_cell(bm, center, gap):
    scale = max(0.01, 1.0 - gap)
    for vert in bm.verts:
        vert.co = center + (vert.co - center) * scale
    bm.normal_update()


def ensure_unique_collection(parent_collection, base_name):
    name = base_name
    suffix = 1
    while bpy.data.collections.get(name) is not None:
        suffix += 1
        name = f"{base_name}_{suffix:02d}"

    collection = bpy.data.collections.new(name)
    parent_collection.children.link(collection)
    return collection


def join_objects(context, objects, object_name):
    mesh_objects = [obj for obj in objects if obj is not None and obj.type == 'MESH' and obj.name in bpy.data.objects]
    if not mesh_objects:
        return None

    if len(mesh_objects) == 1:
        mesh_objects[0].name = object_name
        mesh_objects[0].data.name = f"{object_name}_mesh"
        return mesh_objects[0]

    view_layer = context.view_layer
    previous_active = view_layer.objects.active
    previous_selected = list(context.selected_objects)

    bpy.ops.object.select_all(action='DESELECT')
    for obj in mesh_objects:
        obj.select_set(True)

    view_layer.objects.active = mesh_objects[0]
    bpy.ops.object.join()

    joined = view_layer.objects.active
    if joined is not None:
        joined.name = object_name
        if joined.data is not None:
            joined.data.name = f"{object_name}_mesh"

    bpy.ops.object.select_all(action='DESELECT')
    for obj in previous_selected:
        if obj is not None and obj.name in bpy.data.objects:
            obj.select_set(True)

    if previous_active is not None and previous_active.name in bpy.data.objects:
        view_layer.objects.active = previous_active
    elif joined is not None:
        view_layer.objects.active = joined

    return joined


classes = (
    VoronoiSolidSettings,
    OBJECT_OT_generate_voronoi_solid_cells,
    VIEW3D_PT_voronoi_solid_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.voronoi_solid_settings = PointerProperty(type=VoronoiSolidSettings)


def unregister():
    del bpy.types.Scene.voronoi_solid_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
