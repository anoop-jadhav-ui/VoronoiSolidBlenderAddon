bl_info = {
    "name": "Voronoi Solid Pattern",
    "author": "Hermes Agent",
    "version": (0, 7, 0),
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
    solid_output_mode: EnumProperty(
        name="Solid Output",
        items=(
            ('CELLS', "Cells", "Keep the generated Voronoi cells as the output"),
            ('CARVED', "Carved", "Subtract the joined Voronoi cells from a duplicate of the source mesh"),
        ),
        default='CELLS',
        description="Controls whether solid mode outputs the cells themselves or a carved boolean result",
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
    lattice_output_mode: EnumProperty(
        name="Lattice Output",
        items=(
            ('CELLS', "Cells", "Keep the clipped Voronoi cell meshes"),
            ('RAW_EDGES', "Raw Edges", "Output the raw extracted edge network before cleanup"),
            ('FINAL_NETWORK', "Final Network", "Output a welded and deduplicated edge network for lattice development"),
            ('STRUTS', "Struts", "Build a printable strut mesh from the cleaned lattice network"),
        ),
        default='CELLS',
    )
    sampling_mode: EnumProperty(
        name="Sampling",
        items=(
            ('BLUE_NOISE', "Blue Noise", "Spread seeds more evenly using a blue-noise style candidate selection pass"),
            ('RANDOM', "Random", "Use plain random accepted interior/shell samples"),
        ),
        default='BLUE_NOISE',
        description="Controls how Voronoi seeds are distributed inside the solid or surface shell",
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
    weld_tolerance: FloatProperty(
        name="Weld Tolerance",
        default=0.02,
        min=0.0,
        max=1.0,
        description="Merge nearby network vertices within this distance in Lattice network modes",
    )
    minimum_edge_length: FloatProperty(
        name="Min Edge Length",
        default=0.01,
        min=0.0,
        max=10.0,
        description="Discard lattice edge segments shorter than this length during cleanup",
    )
    duplicate_edge_tolerance: FloatProperty(
        name="Duplicate Edge Tol",
        default=0.0005,
        min=0.0,
        max=1.0,
        description="Treat nearly identical lattice segments as duplicates within this tolerance",
    )
    lattice_relax_iterations: IntProperty(
        name="Relax Iterations",
        default=4,
        min=0,
        max=24,
        description="Optional Laplacian relaxation passes applied to the cleaned lattice network before output",
    )
    lattice_relax_strength: FloatProperty(
        name="Relax Strength",
        default=0.35,
        min=0.0,
        max=1.0,
        subtype='FACTOR',
        description="How strongly each lattice relaxation pass pulls vertices toward their neighbors",
    )
    strut_radius: FloatProperty(
        name="Strut Radius",
        default=0.03,
        min=0.001,
        max=1.0,
        description="Radius of each printable lattice strut in Struts output mode",
    )
    node_radius_multiplier: FloatProperty(
        name="Node Radius x",
        default=1.25,
        min=0.5,
        max=5.0,
        description="Multiplier applied to the strut radius when capping junction nodes",
    )
    strut_sides: IntProperty(
        name="Strut Sides",
        default=8,
        min=3,
        max=24,
        description="Number of sides used for each cylindrical printable strut",
    )
    node_subdivisions: IntProperty(
        name="Node Detail",
        default=1,
        min=1,
        max=4,
        description="Subdivision level used for the spherical junction caps at welded lattice nodes",
    )
    boundary_cleanup_iterations: IntProperty(
        name="Boundary Cleanup",
        default=4,
        min=0,
        max=20,
        description="How many cleanup passes are used to fill or collapse tiny open boundary loops in printable struts",
    )
    boundary_component_max_edges: IntProperty(
        name="Tiny Boundary Max",
        default=2,
        min=0,
        max=32,
        description="Treat boundary loops up to this many edges as tiny cleanup candidates during printable strut repair",
    )
    strut_remesh_voxel_size: FloatProperty(
        name="Remesh Voxel",
        default=0.0,
        min=0.0,
        max=1.0,
        description="Voxel size used for printable strut cleanup; 0 keeps the automatic detail size",
    )
    strut_smooth_iterations: IntProperty(
        name="Smooth Iterations",
        default=4,
        min=0,
        max=50,
        description="Extra vertex smoothing passes applied after strut remeshing",
    )
    strut_smooth_factor: FloatProperty(
        name="Smooth Factor",
        default=0.35,
        min=0.0,
        max=1.0,
        subtype='FACTOR',
        description="Strength of each post-remesh smoothing pass for printable struts",
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
        target_collection["voronoi_solid_output_mode"] = settings.solid_output_mode
        target_collection["voronoi_seed_count"] = len(seeds)
        target_collection["voronoi_sampling_mode"] = settings.sampling_mode

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
            obj["voronoi_solid_output_mode"] = settings.solid_output_mode
            obj["voronoi_sampling_mode"] = settings.sampling_mode
            target_collection.objects.link(obj)
            created += 1
            created_objects.append(obj)

        source_bm.free()

        if created == 0:
            bpy.data.collections.remove(target_collection)
            self.report({'ERROR'}, "No Voronoi cells were generated")
            return {'CANCELLED'}

        if settings.generation_mode == 'LATTICE' and settings.lattice_output_mode != 'CELLS':
            lattice_object = build_lattice_output_object(
                target_collection,
                created_objects,
                source_obj.name,
                settings.lattice_output_mode,
                settings.weld_tolerance,
                settings.minimum_edge_length,
                settings.duplicate_edge_tolerance,
                settings.lattice_relax_iterations,
                settings.lattice_relax_strength,
                settings.strut_radius,
                settings.node_radius_multiplier,
                settings.strut_sides,
                settings.node_subdivisions,
                settings.boundary_cleanup_iterations,
                settings.boundary_component_max_edges,
                settings.strut_remesh_voxel_size,
                settings.strut_smooth_iterations,
                settings.strut_smooth_factor,
            )
            lattice_object["voronoi_sampling_mode"] = settings.sampling_mode
            cleanup_generated_objects(created_objects)
            created_objects = [lattice_object]
            created = 1
        elif settings.generation_mode == 'SOLID' and settings.solid_output_mode == 'CARVED':
            cutter_object = join_objects(context, created_objects, f"{source_obj.name}_voronoi_cutters")
            if cutter_object is None:
                cleanup_generated_objects(created_objects)
                bpy.data.collections.remove(target_collection)
                self.report({'ERROR'}, "Could not build joined Voronoi cutters for boolean carving")
                return {'CANCELLED'}
            try:
                carved_object = build_carved_output_object(target_collection, source_obj, cutter_object)
            except RuntimeError as exc:
                cleanup_generated_objects([cutter_object])
                cleanup_generated_objects(created_objects)
                bpy.data.collections.remove(target_collection)
                self.report({'ERROR'}, str(exc))
                return {'CANCELLED'}
            carved_object["voronoi_generation_mode"] = settings.generation_mode
            carved_object["voronoi_solid_output_mode"] = settings.solid_output_mode
            carved_object["voronoi_sampling_mode"] = settings.sampling_mode
            cleanup_generated_objects([cutter_object])
            created_objects = [carved_object]
            created = 1
        elif settings.join_cells and created_objects:
            joined_object = join_objects(context, created_objects, f"{source_obj.name}_voronoi")
            if joined_object is not None:
                joined_object["voronoi_generation_mode"] = settings.generation_mode
                joined_object["voronoi_solid_output_mode"] = settings.solid_output_mode
                joined_object["voronoi_sampling_mode"] = settings.sampling_mode
                created = 1

        if not settings.keep_original:
            source_obj.hide_set(True)
            source_obj.hide_render = True

        result_label = "Voronoi result"
        if settings.generation_mode == 'LATTICE' and settings.lattice_output_mode != 'CELLS':
            result_label = f"lattice {settings.lattice_output_mode.lower()} output"
        elif settings.generation_mode == 'SOLID' and settings.solid_output_mode == 'CARVED':
            result_label = "carved Voronoi solid"
        self.report({'INFO'}, f"Generated {created} {result_label} object(s) in collection '{target_collection.name}'")
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
            col.prop(settings, "solid_output_mode")
            col.prop(settings, "seed_count")
        else:
            col.prop(settings, "surface_seed_count")
            col.prop(settings, "interior_seed_count")
            col.prop(settings, "surface_shell_depth")
            col.prop(settings, "surface_shell_bias")
            col.prop(settings, "lattice_output_mode")
            if settings.lattice_output_mode != 'CELLS':
                col.prop(settings, "weld_tolerance")
                col.prop(settings, "minimum_edge_length")
                col.prop(settings, "duplicate_edge_tolerance")
                col.prop(settings, "lattice_relax_iterations")
                if settings.lattice_relax_iterations > 0:
                    col.prop(settings, "lattice_relax_strength")
                if settings.lattice_output_mode == 'STRUTS':
                    col.prop(settings, "strut_radius")
                    col.prop(settings, "node_radius_multiplier")
                    col.prop(settings, "strut_sides")
                    col.prop(settings, "node_subdivisions")
                    col.prop(settings, "boundary_cleanup_iterations")
                    col.prop(settings, "boundary_component_max_edges")
                    col.prop(settings, "strut_remesh_voxel_size")
                    col.prop(settings, "strut_smooth_iterations")
                    if settings.strut_smooth_iterations > 0:
                        col.prop(settings, "strut_smooth_factor")

        col.prop(settings, "sampling_mode")
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
                    settings.sampling_mode,
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
                    settings.sampling_mode,
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
        settings.sampling_mode,
        depsgraph,
    )


def sample_points_inside_object(obj, target_count, random_seed, attempt_multiplier, sampling_mode, depsgraph):
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
    attempts = max(target_count * attempt_multiplier, target_count)
    candidates = []

    for _ in range(attempts):
        candidate = Vector((
            rng.uniform(min_corner.x, max_corner.x),
            rng.uniform(min_corner.y, max_corner.y),
            rng.uniform(min_corner.z, max_corner.z),
        ))

        if not point_is_inside_object(obj, candidate, depsgraph):
            continue

        candidates.append(candidate)

    if len(candidates) < target_count:
        raise RuntimeError(
            f"Only found {len(candidates)} interior sample points out of {target_count}. Increase attempts or use a cleaner closed mesh."
        )

    return finalize_seed_candidates(candidates, target_count, random_seed, sampling_mode)


def sample_points_on_surface_shell(obj, target_count, random_seed, shell_depth, shell_bias, sampling_mode, depsgraph):
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

    candidates = []
    attempts = max(target_count * 10, target_count)
    exponent = 1.0 + max(0.0, min(1.0, shell_bias)) * 4.0

    for _ in range(attempts):
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
        candidates.append(candidate)

    if len(candidates) < target_count:
        raise RuntimeError(
            f"Only found {len(candidates)} surface shell points out of {target_count}. Reduce shell depth or use a cleaner closed mesh."
        )

    return finalize_seed_candidates(candidates, target_count, random_seed, sampling_mode)


def finalize_seed_candidates(candidates, target_count, random_seed, sampling_mode):
    if len(candidates) < target_count:
        raise RuntimeError(f"Only found {len(candidates)} valid seed candidates out of {target_count}")
    if sampling_mode == 'RANDOM':
        return [candidate.copy() for candidate in candidates[:target_count]]
    if sampling_mode == 'BLUE_NOISE':
        return select_blue_noise_candidates(candidates, target_count, random_seed)
    raise RuntimeError(f"Unsupported sampling mode: {sampling_mode}")


def select_blue_noise_candidates(candidates, target_count, random_seed):
    rng = random.Random(random_seed)
    remaining = [candidate.copy() for candidate in candidates]
    if len(remaining) <= target_count:
        return remaining

    seed_index = rng.randrange(len(remaining))
    selected = [remaining.pop(seed_index)]
    min_distances = [distance_squared(point, selected[0]) for point in remaining]

    while len(selected) < target_count and remaining:
        next_index = max(range(len(remaining)), key=lambda index: (min_distances[index], -index))
        next_point = remaining.pop(next_index)
        min_distances.pop(next_index)
        selected.append(next_point)
        for index, point in enumerate(remaining):
            candidate_distance = distance_squared(point, next_point)
            if candidate_distance < min_distances[index]:
                min_distances[index] = candidate_distance

    return selected


def distance_squared(a, b):
    delta = a - b
    return delta.dot(delta)


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


def build_lattice_output_object(
    collection,
    cell_objects,
    source_name,
    output_mode,
    weld_tolerance,
    minimum_edge_length,
    duplicate_edge_tolerance,
    lattice_relax_iterations,
    lattice_relax_strength,
    strut_radius,
    node_radius_multiplier,
    strut_sides,
    node_subdivisions,
    boundary_cleanup_iterations,
    boundary_component_max_edges,
    strut_remesh_voxel_size,
    strut_smooth_iterations,
    strut_smooth_factor,
):
    raw_segments = extract_edge_segments(cell_objects)

    if output_mode == 'RAW_EDGES':
        segments = [segment for segment in raw_segments if segment_length(segment) >= max(minimum_edge_length, EPSILON)]
        if not segments:
            raise RuntimeError("No lattice edge segments remained after extraction/cleanup")
        return build_edge_debug_object(collection, source_name, output_mode, segments, False, weld_tolerance)

    clean_segments = clean_edge_segments(raw_segments, weld_tolerance, minimum_edge_length, duplicate_edge_tolerance)
    if not clean_segments:
        raise RuntimeError("No lattice edge segments remained after extraction/cleanup")

    if lattice_relax_iterations > 0 and lattice_relax_strength > 0.0:
        clean_segments = relax_edge_segments(clean_segments, weld_tolerance, lattice_relax_iterations, lattice_relax_strength)

    if output_mode == 'FINAL_NETWORK':
        return build_edge_debug_object(collection, source_name, output_mode, clean_segments, True, weld_tolerance)
    if output_mode == 'STRUTS':
        return build_lattice_strut_object(
            collection,
            source_name,
            clean_segments,
            weld_tolerance,
            strut_radius,
            node_radius_multiplier,
            strut_sides,
            node_subdivisions,
            boundary_cleanup_iterations,
            boundary_component_max_edges,
            strut_remesh_voxel_size,
            strut_smooth_iterations,
            strut_smooth_factor,
        )

    raise RuntimeError(f"Unsupported lattice output mode: {output_mode}")


def build_edge_debug_object(collection, source_name, output_mode, segments, unique_vertices, weld_tolerance):
    object_name = f"{source_name}_{output_mode.lower()}"
    mesh = bpy.data.meshes.new(f"{object_name}_mesh")
    vertices, edges = build_edge_mesh_data(segments, unique_vertices, weld_tolerance)
    mesh.from_pydata(vertices, edges, [])
    mesh.update()

    obj = bpy.data.objects.new(object_name, mesh)
    obj.matrix_world = Matrix.Identity(4)
    obj["voronoi_generation_mode"] = 'LATTICE'
    obj["voronoi_lattice_output_mode"] = output_mode
    collection.objects.link(obj)
    return obj


def build_lattice_strut_object(
    collection,
    source_name,
    segments,
    weld_tolerance,
    strut_radius,
    node_radius_multiplier,
    strut_sides,
    node_subdivisions,
    boundary_cleanup_iterations,
    boundary_component_max_edges,
    remesh_voxel_size,
    smooth_iterations,
    smooth_factor,
):
    object_name = f"{source_name}_struts"
    bm = bmesh.new()

    safe_radius = max(strut_radius, 0.001)
    safe_sides = max(3, int(strut_sides))
    safe_node_subdivisions = max(1, int(node_subdivisions))
    safe_boundary_cleanup_iterations = max(0, int(boundary_cleanup_iterations))
    safe_boundary_component_max_edges = max(0, int(boundary_component_max_edges))
    node_radius = safe_radius * max(node_radius_multiplier, 0.5)

    for start, end in segments:
        append_cylinder_segment(bm, start, end, safe_radius, safe_sides)

    for point in unique_segment_points(segments, weld_tolerance):
        bmesh.ops.create_icosphere(
            bm,
            subdivisions=safe_node_subdivisions,
            radius=node_radius,
            matrix=Matrix.Translation(point),
        )

    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=max(weld_tolerance, safe_radius * 0.25, EPSILON))
    for _ in range(safe_boundary_cleanup_iterations):
        boundary_edges = [edge for edge in bm.edges if edge.is_valid and edge.is_boundary]
        if not boundary_edges:
            break
        try:
            bmesh.ops.holes_fill(bm, edges=boundary_edges, sides=0)
        except RuntimeError:
            pass
        boundary_edges = [edge for edge in bm.edges if edge.is_valid and edge.is_boundary]
        if not boundary_edges:
            break
        try:
            bmesh.ops.triangle_fill(bm, edges=boundary_edges)
        except RuntimeError:
            pass
        if safe_boundary_component_max_edges <= 0:
            continue
        tiny_boundary_edges = find_small_boundary_components(bm, max_edges=safe_boundary_component_max_edges)
        if not tiny_boundary_edges:
            break
        bmesh.ops.delete(bm, geom=tiny_boundary_edges, context='EDGES_FACES')
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=max(weld_tolerance, safe_radius * 0.25, EPSILON))
    delete_loose_geometry(bm)
    try:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    except RuntimeError:
        pass
    bm.normal_update()

    mesh = bpy.data.meshes.new(f"{object_name}_mesh")
    bm.to_mesh(mesh)
    mesh.update()
    bm.free()

    obj = bpy.data.objects.new(object_name, mesh)
    obj.matrix_world = Matrix.Identity(4)
    obj["voronoi_generation_mode"] = 'LATTICE'
    obj["voronoi_lattice_output_mode"] = 'STRUTS'
    obj["voronoi_node_subdivisions"] = safe_node_subdivisions
    obj["voronoi_boundary_cleanup_iterations"] = safe_boundary_cleanup_iterations
    obj["voronoi_boundary_component_max_edges"] = safe_boundary_component_max_edges
    obj["voronoi_remesh_voxel_size"] = float(remesh_voxel_size)
    obj["voronoi_strut_smooth_iterations"] = max(0, int(smooth_iterations))
    obj["voronoi_strut_smooth_factor"] = float(max(0.0, min(1.0, smooth_factor)))
    collection.objects.link(obj)
    voxel_size = remesh_voxel_size if remesh_voxel_size > 0.0 else max(safe_radius * 0.8, weld_tolerance * 0.75, 0.01)
    voxel_remesh_object(obj, voxel_size)
    smooth_mesh_object(obj, smooth_iterations, smooth_factor)
    return obj


def voxel_remesh_object(obj, voxel_size):
    modifier = obj.modifiers.new(name="VoronoiStrutRemesh", type='REMESH')
    modifier.mode = 'VOXEL'
    modifier.voxel_size = max(voxel_size, 0.001)
    modifier.adaptivity = 0.0
    modifier.use_remove_disconnected = False

    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    remeshed = bpy.data.meshes.new_from_object(evaluated, depsgraph=depsgraph)
    obj.modifiers.remove(modifier)

    if remeshed is None or len(remeshed.vertices) == 0:
        if remeshed is not None and remeshed.users == 0:
            bpy.data.meshes.remove(remeshed)
        return

    old_mesh = obj.data
    obj.data = remeshed
    obj.data.update()
    if old_mesh is not None and old_mesh.users == 0:
        bpy.data.meshes.remove(old_mesh)


def smooth_mesh_object(obj, iterations, factor):
    safe_iterations = max(0, int(iterations))
    safe_factor = max(0.0, min(1.0, factor))
    if safe_iterations <= 0 or safe_factor <= 0.0 or obj is None or obj.type != 'MESH' or obj.data is None:
        return

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    for _ in range(safe_iterations):
        bmesh.ops.smooth_vert(
            bm,
            verts=bm.verts,
            factor=safe_factor,
            use_axis_x=True,
            use_axis_y=True,
            use_axis_z=True,
        )
    bm.to_mesh(obj.data)
    obj.data.update()
    bm.free()


def append_cylinder_segment(bm, start, end, radius, sides):
    delta = end - start
    length = delta.length
    if length <= EPSILON:
        return

    midpoint = start.lerp(end, 0.5)
    rotation = delta.normalized().to_track_quat('Z', 'Y').to_matrix().to_4x4()
    matrix = Matrix.Translation(midpoint) @ rotation
    bmesh.ops.create_cone(
        bm,
        cap_ends=True,
        cap_tris=False,
        segments=max(3, int(sides)),
        radius1=radius,
        radius2=radius,
        depth=length,
        matrix=matrix,
    )


def unique_segment_points(segments, tolerance):
    points = {}
    for start, end in segments:
        start_key = quantize_vector(start, max(tolerance, EPSILON))
        end_key = quantize_vector(end, max(tolerance, EPSILON))
        points.setdefault(start_key, start)
        points.setdefault(end_key, end)
    return [point.copy() for point in points.values()]


def find_small_boundary_components(bm, max_edges):
    boundary_edges = [edge for edge in bm.edges if edge.is_valid and edge.is_boundary]
    if not boundary_edges:
        return []

    visited = set()
    tiny_edges = []
    for edge in boundary_edges:
        if edge in visited:
            continue
        stack = [edge]
        component = []
        while stack:
            current = stack.pop()
            if current in visited or not current.is_valid or not current.is_boundary:
                continue
            visited.add(current)
            component.append(current)
            for vert in current.verts:
                for linked in vert.link_edges:
                    if linked.is_valid and linked.is_boundary and linked not in visited:
                        stack.append(linked)
        if 0 < len(component) <= max_edges:
            tiny_edges.extend(component)
    return tiny_edges


def relax_edge_segments(segments, tolerance, iterations, strength):
    safe_iterations = max(0, int(iterations))
    safe_strength = max(0.0, min(1.0, strength))
    if safe_iterations <= 0 or safe_strength <= 0.0 or not segments:
        return segments

    point_map = {}
    adjacency = {}
    edge_keys = []
    quantize_tolerance = max(tolerance, EPSILON)

    for start, end in segments:
        start_key = quantize_vector(start, quantize_tolerance)
        end_key = quantize_vector(end, quantize_tolerance)
        point_map.setdefault(start_key, start.copy())
        point_map.setdefault(end_key, end.copy())
        adjacency.setdefault(start_key, set()).add(end_key)
        adjacency.setdefault(end_key, set()).add(start_key)
        edge_keys.append((start_key, end_key))

    relaxed = {key: value.copy() for key, value in point_map.items()}
    for _ in range(safe_iterations):
        updated = {key: value.copy() for key, value in relaxed.items()}
        for key, neighbors in adjacency.items():
            if len(neighbors) < 3:
                continue
            total = Vector((0.0, 0.0, 0.0))
            for neighbor_key in neighbors:
                total += relaxed[neighbor_key]
            average = total / len(neighbors)
            updated[key] = relaxed[key].lerp(average, safe_strength)
        relaxed = updated

    return [(relaxed[start_key].copy(), relaxed[end_key].copy()) for start_key, end_key in edge_keys]


def extract_edge_segments(objects):
    segments = []
    for obj in objects:
        if obj is None or obj.type != 'MESH' or obj.data is None:
            continue
        mesh = obj.data
        for edge in mesh.edges:
            start = obj.matrix_world @ mesh.vertices[edge.vertices[0]].co
            end = obj.matrix_world @ mesh.vertices[edge.vertices[1]].co
            if (end - start).length <= EPSILON:
                continue
            segments.append((start.copy(), end.copy()))
    return segments


def clean_edge_segments(raw_segments, weld_tolerance, minimum_edge_length, duplicate_edge_tolerance):
    filtered = []
    seen_duplicates = set()
    duplicate_tol = max(duplicate_edge_tolerance, EPSILON)

    for start, end in raw_segments:
        if (end - start).length < max(minimum_edge_length, EPSILON):
            continue
        duplicate_key = canonical_segment_key(start, end, duplicate_tol)
        if duplicate_key[0] == duplicate_key[1] or duplicate_key in seen_duplicates:
            continue
        seen_duplicates.add(duplicate_key)
        filtered.append((start, end))

    if not filtered:
        return []

    welded_points = build_welded_point_map(filtered, max(weld_tolerance, EPSILON))
    final_segments = []
    seen_final = set()
    final_tolerance = max(weld_tolerance, duplicate_tol, EPSILON)

    for start, end in filtered:
        welded_start = welded_points[quantize_vector(start, max(weld_tolerance, EPSILON))]
        welded_end = welded_points[quantize_vector(end, max(weld_tolerance, EPSILON))]
        if (welded_end - welded_start).length < max(minimum_edge_length, EPSILON):
            continue
        final_key = canonical_segment_key(welded_start, welded_end, final_tolerance)
        if final_key[0] == final_key[1] or final_key in seen_final:
            continue
        seen_final.add(final_key)
        final_segments.append((welded_start.copy(), welded_end.copy()))

    return final_segments


def build_welded_point_map(segments, tolerance):
    buckets = {}
    for start, end in segments:
        start_key = quantize_vector(start, tolerance)
        end_key = quantize_vector(end, tolerance)
        buckets.setdefault(start_key, []).append(start)
        buckets.setdefault(end_key, []).append(end)

    welded = {}
    for key, points in buckets.items():
        total = Vector((0.0, 0.0, 0.0))
        for point in points:
            total += point
        welded[key] = total / len(points)
    return welded


def build_edge_mesh_data(segments, unique_vertices, tolerance):
    vertices = []
    edges = []

    if not unique_vertices:
        for start, end in segments:
            index = len(vertices)
            vertices.append(tuple(start))
            vertices.append(tuple(end))
            edges.append((index, index + 1))
        return vertices, edges

    index_by_key = {}
    for start, end in segments:
        start_index = get_or_create_vertex_index(vertices, index_by_key, start, tolerance)
        end_index = get_or_create_vertex_index(vertices, index_by_key, end, tolerance)
        if start_index == end_index:
            continue
        edges.append((start_index, end_index))
    return vertices, edges


def get_or_create_vertex_index(vertices, index_by_key, point, tolerance):
    key = quantize_vector(point, max(tolerance, EPSILON))
    if key in index_by_key:
        return index_by_key[key]
    index = len(vertices)
    vertices.append(tuple(point))
    index_by_key[key] = index
    return index


def quantize_vector(point, tolerance):
    scale = max(tolerance, EPSILON)
    return (
        int(round(point.x / scale)),
        int(round(point.y / scale)),
        int(round(point.z / scale)),
    )


def canonical_segment_key(start, end, tolerance):
    start_key = quantize_vector(start, tolerance)
    end_key = quantize_vector(end, tolerance)
    if start_key <= end_key:
        return start_key, end_key
    return end_key, start_key


def segment_length(segment):
    return (segment[1] - segment[0]).length


def cleanup_generated_objects(objects):
    for obj in objects:
        if obj is None or obj.name not in bpy.data.objects:
            continue
        mesh = obj.data if obj.type == 'MESH' else None
        bpy.data.objects.remove(obj, do_unlink=True)
        if mesh is not None and mesh.users == 0:
            bpy.data.meshes.remove(mesh)


def build_carved_output_object(collection, source_obj, cutter_obj, depsgraph=None):
    object_name = f"{source_obj.name}_carved"
    depsgraph = depsgraph or bpy.context.evaluated_depsgraph_get()
    source_bm = build_world_bmesh(source_obj, depsgraph)
    if len(source_bm.faces) == 0:
        source_bm.free()
        raise RuntimeError("Failed to evaluate the source mesh for boolean carving")
    mesh = bpy.data.meshes.new(f"{object_name}_source")
    source_bm.to_mesh(mesh)
    mesh.update()
    source_bm.free()
    carved = bpy.data.objects.new(object_name, mesh)
    carved.matrix_world = Matrix.Identity(4)
    collection.objects.link(carved)

    modifier = carved.modifiers.new(name="VoronoiCarve", type='BOOLEAN')
    modifier.operation = 'DIFFERENCE'
    modifier.solver = 'EXACT'
    modifier.object = cutter_obj
    bpy.context.view_layer.update()

    evaluated = carved.evaluated_get(depsgraph)
    carved_mesh = bpy.data.meshes.new_from_object(evaluated, depsgraph=depsgraph)
    carved.modifiers.remove(modifier)

    if carved_mesh is None or len(carved_mesh.vertices) == 0 or len(carved_mesh.polygons) == 0:
        if carved_mesh is not None and carved_mesh.users == 0:
            bpy.data.meshes.remove(carved_mesh)
        cleanup_generated_objects([carved])
        raise RuntimeError("Boolean carve produced an empty result; reduce gap or use a cleaner closed mesh")

    old_mesh = carved.data
    carved.data = carved_mesh
    carved.data.update()
    if old_mesh is not None and old_mesh.users == 0:
        bpy.data.meshes.remove(old_mesh)
    return carved


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
