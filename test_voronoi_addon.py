import json
import math
import os
import sys

import bpy
import bmesh

PROJECT_DIR = "/Users/anoopjadhav/Documents/vibeCodedProjects/VoronoiSolidBlenderAddon"
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

import voronoi_solid_addon

if getattr(voronoi_solid_addon, "__file__", "").startswith(PROJECT_DIR) is False:
    raise RuntimeError(f"Loaded wrong addon module: {getattr(voronoi_solid_addon, '__file__', None)}")


results = []


def reset_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)

    for collection in list(bpy.data.collections):
        if collection.users == 0:
            bpy.data.collections.remove(collection)


def object_volume(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    volume = abs(bm.calc_volume()) if len(bm.faces) >= 4 else 0.0
    bm.free()
    return volume


def evaluated_object_volume(obj, depsgraph):
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    if mesh is None:
        return 0.0
    bm = bmesh.new()
    bm.from_mesh(mesh)
    volume = abs(bm.calc_volume()) if len(bm.faces) >= 4 else 0.0
    bm.free()
    evaluated.to_mesh_clear()
    return volume


def evaluated_world_bounds(obj, depsgraph):
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    if mesh is None or len(mesh.vertices) == 0:
        evaluated.to_mesh_clear()
        raise RuntimeError(f"Could not evaluate bounds for {obj.name}")
    coords = [obj.matrix_world @ vertex.co for vertex in mesh.vertices]
    evaluated.to_mesh_clear()
    min_x = min(co.x for co in coords)
    min_y = min(co.y for co in coords)
    min_z = min(co.z for co in coords)
    max_x = max(co.x for co in coords)
    max_y = max(co.y for co in coords)
    max_z = max(co.z for co in coords)
    return (min_x, min_y, min_z), (max_x, max_y, max_z)


def boundary_edge_count(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    count = sum(1 for edge in bm.edges if edge.is_boundary)
    bm.free()
    return count


def rounded_vertex_signature(obj, precision=4):
    verts = []
    for vertex in obj.data.vertices:
        co = obj.matrix_world @ vertex.co
        verts.append((round(co.x, precision), round(co.y, precision), round(co.z, precision)))
    return tuple(sorted(verts))


def surface_distance(obj, world_point, depsgraph):
    local_point = obj.matrix_world.inverted() @ world_point
    hit, location, _normal, _face_index = obj.closest_point_on_mesh(local_point, depsgraph=depsgraph)
    if not hit:
        raise RuntimeError(f"Could not project point to mesh surface for {obj.name}")
    closest_world = obj.matrix_world @ location
    return (world_point - closest_world).length


def nearest_neighbor_distances(points):
    distances = []
    for index, point in enumerate(points):
        nearest = None
        for other_index, other in enumerate(points):
            if index == other_index:
                continue
            distance = (point - other).length
            if nearest is None or distance < nearest:
                nearest = distance
        if nearest is not None:
            distances.append(nearest)
    return distances


def run_seed_distribution_case(kind):
    reset_scene()

    if kind != "cube_blue_noise":
        raise ValueError(kind)

    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0, 0, 0))
    src = bpy.context.active_object
    depsgraph = bpy.context.evaluated_depsgraph_get()
    settings = bpy.context.scene.voronoi_solid_settings
    settings.generation_mode = 'SOLID'
    settings.solid_output_mode = 'CELLS'
    settings.seed_count = 12
    settings.random_seed = 19
    settings.sample_attempt_multiplier = 120
    settings.sampling_mode = 'RANDOM'
    random_seeds = voronoi_solid_addon.generate_seed_points(src, settings, depsgraph)
    settings.sampling_mode = 'BLUE_NOISE'
    blue_noise_seeds = voronoi_solid_addon.generate_seed_points(src, settings, depsgraph)

    if len(random_seeds) != settings.seed_count or len(blue_noise_seeds) != settings.seed_count:
        raise RuntimeError(
            f"Expected both sampling modes to create {settings.seed_count} seeds, got random={len(random_seeds)} blue_noise={len(blue_noise_seeds)}"
        )

    random_distances = nearest_neighbor_distances(random_seeds)
    blue_noise_distances = nearest_neighbor_distances(blue_noise_seeds)
    if min(blue_noise_distances) <= min(random_distances):
        raise RuntimeError(
            "Expected blue-noise interior sampling to increase minimum nearest-neighbor spacing: "
            f"random={min(random_distances):.6f} blue_noise={min(blue_noise_distances):.6f}"
        )

    results.append(
        {
            "case": kind,
            "random_min_spacing": round(min(random_distances), 6),
            "blue_noise_min_spacing": round(min(blue_noise_distances), 6),
            "sampling_mode": settings.sampling_mode,
        }
    )


def run_lattice_seed_case(kind):
    reset_scene()

    if kind != "sphere_lattice":
        raise ValueError(kind)

    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.25, segments=32, ring_count=16, location=(0, 0, 0))
    src = bpy.context.active_object

    settings = bpy.context.scene.voronoi_solid_settings
    settings.generation_mode = 'LATTICE'
    settings.surface_seed_count = 10
    settings.interior_seed_count = 2
    settings.surface_shell_depth = 0.12
    settings.surface_shell_bias = 1.0
    settings.random_seed = 11
    settings.sample_attempt_multiplier = 100

    depsgraph = bpy.context.evaluated_depsgraph_get()
    seeds = voronoi_solid_addon.generate_seed_points(src, settings, depsgraph)
    if len(seeds) != 12:
        raise RuntimeError(f"Expected 12 lattice seeds, got {len(seeds)}")

    near_surface = [surface_distance(src, seed, depsgraph) for seed in seeds[:settings.surface_seed_count]]
    if any(distance > settings.surface_shell_depth * 1.35 for distance in near_surface):
        raise RuntimeError(f"Surface lattice seeds were not kept near the shell depth: {near_surface}")

    results.append(
        {
            "case": kind,
            "seed_count": len(seeds),
            "surface_seed_count": settings.surface_seed_count,
            "interior_seed_count": settings.interior_seed_count,
            "max_surface_distance": round(max(near_surface), 6),
        }
    )


def run_lattice_network_case(kind, output_mode, *, relax_iterations=0, relax_strength=0.5):
    reset_scene()

    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.25, segments=32, ring_count=16, location=(0, 0, 0))
    src = bpy.context.active_object

    settings = bpy.context.scene.voronoi_solid_settings
    settings.generation_mode = 'LATTICE'
    settings.lattice_output_mode = output_mode
    settings.surface_seed_count = 10
    settings.interior_seed_count = 2
    settings.surface_shell_depth = 0.12
    settings.surface_shell_bias = 1.0
    settings.random_seed = 11
    settings.gap = 0.0
    settings.sample_attempt_multiplier = 100
    settings.keep_original = True
    settings.collection_name = f"{kind}_cells"
    settings.join_cells = True
    settings.weld_tolerance = 0.03
    settings.minimum_edge_length = 0.02
    settings.duplicate_edge_tolerance = 0.0005
    settings.lattice_relax_iterations = relax_iterations
    settings.lattice_relax_strength = relax_strength

    bpy.context.view_layer.objects.active = src
    src.select_set(True)

    result = bpy.ops.object.generate_voronoi_solid_cells()
    if 'FINISHED' not in result:
        raise RuntimeError(f"Operator failed for {kind}: {result}")

    generated = [c for c in bpy.data.collections if c.name.startswith(settings.collection_name)]
    if not generated:
        raise RuntimeError(f"No collection created for {kind}")

    collection = max(generated, key=lambda c: len(c.objects))
    mesh_objects = [obj for obj in collection.objects if obj.type == 'MESH']
    if len(mesh_objects) != 1:
        raise RuntimeError(f"Expected one debug edge object for {kind}, got {len(mesh_objects)}")

    target = mesh_objects[0]
    mesh = target.data
    if len(mesh.polygons) != 0:
        raise RuntimeError(f"Expected edge-only debug mesh for {kind}, found {len(mesh.polygons)} faces")
    if len(mesh.edges) == 0:
        raise RuntimeError(f"Expected extracted edges for {kind}, found none")

    summary = {
        "case": kind,
        "output_mode": output_mode,
        "vertices": len(mesh.vertices),
        "edges": len(mesh.edges),
        "relax_iterations": relax_iterations,
        "relax_strength": round(relax_strength, 3),
        "vertex_signature": rounded_vertex_signature(target),
    }
    results.append({k: v for k, v in summary.items() if k != "vertex_signature"})
    return summary


def run_lattice_strut_case(
    kind,
    *,
    remesh_voxel_size=0.0,
    smooth_iterations=4,
    smooth_factor=0.35,
    node_subdivisions=1,
    boundary_cleanup_iterations=4,
    boundary_component_max_edges=2,
):
    reset_scene()

    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.25, segments=32, ring_count=16, location=(0, 0, 0))
    src = bpy.context.active_object

    settings = bpy.context.scene.voronoi_solid_settings
    settings.generation_mode = 'LATTICE'
    settings.lattice_output_mode = 'STRUTS'
    settings.surface_seed_count = 10
    settings.interior_seed_count = 2
    settings.surface_shell_depth = 0.12
    settings.surface_shell_bias = 1.0
    settings.random_seed = 11
    settings.gap = 0.0
    settings.sample_attempt_multiplier = 100
    settings.keep_original = True
    settings.collection_name = f"{kind}_cells"
    settings.join_cells = True
    settings.weld_tolerance = 0.03
    settings.minimum_edge_length = 0.02
    settings.duplicate_edge_tolerance = 0.0005
    settings.strut_radius = 0.035
    settings.node_radius_multiplier = 1.35
    settings.strut_sides = 8
    settings.node_subdivisions = node_subdivisions
    settings.boundary_cleanup_iterations = boundary_cleanup_iterations
    settings.boundary_component_max_edges = boundary_component_max_edges
    settings.strut_remesh_voxel_size = remesh_voxel_size
    settings.strut_smooth_iterations = smooth_iterations
    settings.strut_smooth_factor = smooth_factor

    bpy.context.view_layer.objects.active = src
    src.select_set(True)

    result = bpy.ops.object.generate_voronoi_solid_cells()
    if 'FINISHED' not in result:
        raise RuntimeError(f"Operator failed for {kind}: {result}")

    generated = [c for c in bpy.data.collections if c.name.startswith(settings.collection_name)]
    if not generated:
        raise RuntimeError(f"No collection created for {kind}")

    collection = max(generated, key=lambda c: len(c.objects))
    mesh_objects = [obj for obj in collection.objects if obj.type == 'MESH']
    if len(mesh_objects) != 1:
        raise RuntimeError(f"Expected one printable strut mesh for {kind}, got {len(mesh_objects)}")

    target = mesh_objects[0]
    mesh = target.data
    if len(mesh.polygons) == 0:
        raise RuntimeError(f"Expected printable lattice mesh with faces for {kind}, found none")

    volume = object_volume(target)
    if volume <= 0.0:
        raise RuntimeError(f"Expected positive printable lattice volume for {kind}, got {volume}")

    boundary_edges = boundary_edge_count(target)
    if boundary_edges != 0:
        raise RuntimeError(f"Expected watertight printable lattice mesh for {kind}, found {boundary_edges} boundary edges")

    mod = target.modifiers.new(name="SubdivisionTest", type='SUBSURF')
    mod.levels = 1
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = target.evaluated_get(depsgraph)
    temp_mesh = bpy.data.meshes.new_from_object(evaluated, depsgraph=depsgraph)
    try:
        if len(temp_mesh.vertices) == 0:
            raise RuntimeError(f"Subdivision evaluation produced empty strut mesh for {kind}")
    finally:
        bpy.data.meshes.remove(temp_mesh)

    summary = {
        "case": kind,
        "output_mode": 'STRUTS',
        "vertices": len(mesh.vertices),
        "edges": len(mesh.edges),
        "faces": len(mesh.polygons),
        "boundary_edges": boundary_edges,
        "volume": round(volume, 6),
        "remesh_voxel_size": round(remesh_voxel_size, 4),
        "smooth_iterations": smooth_iterations,
        "smooth_factor": round(smooth_factor, 3),
        "node_subdivisions": node_subdivisions,
        "boundary_cleanup_iterations": boundary_cleanup_iterations,
        "boundary_component_max_edges": boundary_component_max_edges,
        "node_subdivisions_prop": int(target.get("voronoi_node_subdivisions", -1)),
        "boundary_cleanup_iterations_prop": int(target.get("voronoi_boundary_cleanup_iterations", -1)),
        "boundary_component_max_edges_prop": int(target.get("voronoi_boundary_component_max_edges", -1)),
    }
    results.append(summary)
    return summary


def run_carve_case(kind, seed_count, gap, array_count=1, array_offset=1.0):
    reset_scene()

    if kind not in {"cube_carved", "cube_carved_array"}:
        raise ValueError(kind)

    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0, 0, 0))
    src = bpy.context.active_object
    if array_count > 1:
        mod = src.modifiers.new(name="ArraySource", type='ARRAY')
        mod.count = array_count
        mod.relative_offset_displace[0] = array_offset
        mod.relative_offset_displace[1] = 0.0
        mod.relative_offset_displace[2] = 0.0

    depsgraph = bpy.context.evaluated_depsgraph_get()
    source_volume = evaluated_object_volume(src, depsgraph)
    (_source_min_x, _source_min_y, _source_min_z), (source_max_x, _source_max_y, _source_max_z) = evaluated_world_bounds(src, depsgraph)

    settings = bpy.context.scene.voronoi_solid_settings
    settings.generation_mode = 'SOLID'
    settings.solid_output_mode = 'CARVED'
    settings.seed_count = seed_count
    settings.random_seed = 7
    settings.gap = gap
    settings.sample_attempt_multiplier = 120
    settings.keep_original = True
    settings.collection_name = f"{kind}_cells"
    settings.join_cells = True

    bpy.context.view_layer.objects.active = src
    src.select_set(True)

    result = bpy.ops.object.generate_voronoi_solid_cells()
    if 'FINISHED' not in result:
        raise RuntimeError(f"Operator failed for {kind}: {result}")

    generated = [c for c in bpy.data.collections if c.name.startswith(settings.collection_name)]
    if not generated:
        raise RuntimeError(f"No collection created for {kind}")

    collection = max(generated, key=lambda c: len(c.objects))
    mesh_objects = [obj for obj in collection.objects if obj.type == 'MESH']
    if len(mesh_objects) != 1:
        raise RuntimeError(f"Expected one carved mesh object for {kind}, got {len(mesh_objects)}")

    carved = mesh_objects[0]
    carved_volume = object_volume(carved)
    if carved_volume <= 0.0 or carved_volume >= source_volume:
        raise RuntimeError(
            f"Expected carved mesh volume to stay positive but below the source volume: carved={carved_volume}, source={source_volume}"
        )

    (_carved_min_x, _carved_min_y, _carved_min_z), (carved_max_x, _carved_max_y, _carved_max_z) = evaluated_world_bounds(carved, bpy.context.evaluated_depsgraph_get())
    if array_count > 1 and carved_max_x < source_max_x - 0.25:
        raise RuntimeError(
            f"Expected carved mesh to preserve evaluated source extents for modifier-backed geometry: carved_max_x={carved_max_x}, source_max_x={source_max_x}"
        )

    boundary_edges = boundary_edge_count(carved)
    if boundary_edges != 0:
        raise RuntimeError(f"Expected carved mesh to stay watertight, found {boundary_edges} boundary edges")
    if carved.get("voronoi_solid_output_mode") != 'CARVED':
        raise RuntimeError(f"Expected carved mesh to store solid output metadata, got {carved.get('voronoi_solid_output_mode')}")

    results.append(
        {
            "case": kind,
            "output_mode": 'CARVED',
            "source_volume": round(source_volume, 6),
            "carved_volume": round(carved_volume, 6),
            "source_max_x": round(source_max_x, 6),
            "carved_max_x": round(carved_max_x, 6),
            "boundary_edges": boundary_edges,
        }
    )


def run_case(kind, seed_count, gap, join_cells=None, apply_wireframe=False):
    reset_scene()

    if kind.startswith("cube"):
        bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0, 0, 0))
        src = bpy.context.active_object
    elif kind.startswith("sphere"):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.25, segments=32, ring_count=16, location=(0, 0, 0))
        src = bpy.context.active_object
    else:
        raise ValueError(kind)

    settings = bpy.context.scene.voronoi_solid_settings
    settings.generation_mode = 'SOLID'
    settings.solid_output_mode = 'CELLS'
    settings.seed_count = seed_count
    settings.random_seed = 7
    settings.gap = gap
    settings.sample_attempt_multiplier = 100
    settings.keep_original = True
    settings.collection_name = f"{kind}_cells"
    if join_cells is not None:
        settings.join_cells = join_cells

    bpy.context.view_layer.objects.active = src
    src.select_set(True)

    result = bpy.ops.object.generate_voronoi_solid_cells()
    if 'FINISHED' not in result:
        raise RuntimeError(f"Operator failed for {kind}: {result}")

    generated = [c for c in bpy.data.collections if c.name.startswith(settings.collection_name)]
    if not generated:
        raise RuntimeError(f"No collection created for {kind}")

    collection = max(generated, key=lambda c: len(c.objects))
    mesh_objects = [obj for obj in collection.objects if obj.type == 'MESH']
    volumes = [object_volume(obj) for obj in mesh_objects]

    join_expected = settings.join_cells if join_cells is None else join_cells
    expected_objects = 1 if join_expected else seed_count
    if len(mesh_objects) != expected_objects:
        raise RuntimeError(f"Expected {expected_objects} mesh objects for {kind}, got {len(mesh_objects)}")
    if any(v <= 0.0 for v in volumes):
        raise RuntimeError(f"Non-positive cell volume found for {kind}: {volumes}")

    if apply_wireframe:
        target = mesh_objects[0]
        mod = target.modifiers.new(name="WireframeTest", type='WIREFRAME')
        mod.thickness = 0.03
        depsgraph = bpy.context.evaluated_depsgraph_get()
        evaluated = target.evaluated_get(depsgraph)
        temp_mesh = bpy.data.meshes.new_from_object(evaluated, depsgraph=depsgraph)
        try:
            if len(temp_mesh.vertices) == 0:
                raise RuntimeError(f"Wireframe modifier evaluation produced empty mesh for {kind}")
        finally:
            bpy.data.meshes.remove(temp_mesh)

    results.append(
        {
            "case": kind,
            "cells": len(mesh_objects),
            "join_cells": join_expected,
            "wireframe_tested": apply_wireframe,
            "min_volume": round(min(volumes), 6),
            "max_volume": round(max(volumes), 6),
            "total_volume": round(sum(volumes), 6),
        }
    )

voronoi_solid_addon.register()
settings = bpy.context.scene.voronoi_solid_settings
if settings.lattice_relax_iterations != 4 or round(settings.lattice_relax_strength, 3) != 0.35:
    raise RuntimeError(f"Expected Iteration 5 lattice defaults to enable gentle relaxation: iterations={settings.lattice_relax_iterations}, strength={settings.lattice_relax_strength}")
if settings.strut_smooth_iterations != 4 or round(settings.strut_smooth_factor, 3) != 0.35:
    raise RuntimeError(f"Expected printable strut defaults to keep smoothing enabled: iterations={settings.strut_smooth_iterations}, factor={settings.strut_smooth_factor}")
if not hasattr(settings, "sampling_mode"):
    raise RuntimeError("Expected sampling_mode property to exist for blue-noise/Poisson seed generation")
if settings.sampling_mode != 'BLUE_NOISE':
    raise RuntimeError(f"Expected blue-noise sampling to be the default interior seed strategy, got {settings.sampling_mode}")
if not hasattr(settings, "solid_output_mode"):
    raise RuntimeError("Expected solid_output_mode property to exist for boolean carving")
if settings.solid_output_mode != 'CELLS':
    raise RuntimeError(f"Expected solid output mode to default to CELLS, got {settings.solid_output_mode}")
for required_attr in ("node_subdivisions", "boundary_cleanup_iterations", "boundary_component_max_edges"):
    if not hasattr(settings, required_attr):
        raise RuntimeError(f"Expected settings property '{required_attr}' to exist for exposed cleanup/cap controls")
run_seed_distribution_case("cube_blue_noise")
run_carve_case("cube_carved", seed_count=8, gap=0.12)
run_carve_case("cube_carved_array", seed_count=12, gap=0.08, array_count=2, array_offset=1.4)
run_lattice_seed_case("sphere_lattice")
raw_network = run_lattice_network_case("sphere_lattice_raw", 'RAW_EDGES')
welded_network = run_lattice_network_case("sphere_lattice_welded", 'FINAL_NETWORK')
relaxed_network = run_lattice_network_case("sphere_lattice_relaxed", 'FINAL_NETWORK', relax_iterations=4, relax_strength=0.35)
if welded_network["edges"] >= raw_network["edges"]:
    raise RuntimeError(f"Expected welded network to remove duplicate edges: raw={raw_network}, welded={welded_network}")
if welded_network["vertices"] >= raw_network["vertices"]:
    raise RuntimeError(f"Expected welded network to reduce vertex count: raw={raw_network}, welded={welded_network}")
if relaxed_network["vertices"] <= 0 or relaxed_network["edges"] <= 0:
    raise RuntimeError(f"Expected relaxed network to remain non-empty: relaxed={relaxed_network}")
if relaxed_network["edges"] > welded_network["edges"] or relaxed_network["vertices"] > welded_network["vertices"]:
    raise RuntimeError(f"Expected relaxed network cleanup to keep topology size stable or smaller: welded={welded_network}, relaxed={relaxed_network}")
if relaxed_network["vertex_signature"] == welded_network["vertex_signature"]:
    raise RuntimeError(f"Expected relaxed network geometry to change vertex positions: welded={welded_network}, relaxed={relaxed_network}")
default_struts = run_lattice_strut_case("sphere_lattice_struts")
detailed_struts = run_lattice_strut_case(
    "sphere_lattice_struts_detailed_nodes",
    remesh_voxel_size=0.03,
    smooth_iterations=4,
    smooth_factor=0.35,
    node_subdivisions=2,
    boundary_cleanup_iterations=6,
    boundary_component_max_edges=4,
)
coarse_struts = run_lattice_strut_case("sphere_lattice_struts_coarse", remesh_voxel_size=0.06, smooth_iterations=0)
smoothed_struts = run_lattice_strut_case("sphere_lattice_struts_smoothed", remesh_voxel_size=0.03, smooth_iterations=6, smooth_factor=0.45)
if detailed_struts["node_subdivisions_prop"] != 2:
    raise RuntimeError(f"Expected node subdivision control to propagate to the output object: {detailed_struts}")
if detailed_struts["boundary_cleanup_iterations_prop"] != 6:
    raise RuntimeError(f"Expected boundary cleanup iteration control to propagate to the output object: {detailed_struts}")
if detailed_struts["boundary_component_max_edges_prop"] != 4:
    raise RuntimeError(f"Expected boundary cleanup component threshold to propagate to the output object: {detailed_struts}")
if coarse_struts["faces"] >= smoothed_struts["faces"]:
    raise RuntimeError(f"Expected finer/smoothed strut cleanup to produce denser mesh detail: coarse={coarse_struts}, smoothed={smoothed_struts}")
run_case("cube_default_joined", seed_count=8, gap=0.05)
run_case("sphere", seed_count=10, gap=0.08)
run_case("cube_joined", seed_count=8, gap=0.05, join_cells=True, apply_wireframe=True)
run_case("cube_separate", seed_count=6, gap=0.05, join_cells=False)
print(json.dumps(results, indent=2))
voronoi_solid_addon.unregister()
