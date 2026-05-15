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


def surface_distance(obj, world_point, depsgraph):
    local_point = obj.matrix_world.inverted() @ world_point
    hit, location, _normal, _face_index = obj.closest_point_on_mesh(local_point, depsgraph=depsgraph)
    if not hit:
        raise RuntimeError(f"Could not project point to mesh surface for {obj.name}")
    closest_world = obj.matrix_world @ location
    return (world_point - closest_world).length


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


def run_lattice_network_case(kind, output_mode):
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
    }
    results.append(summary)
    return summary


def run_lattice_strut_case(kind):
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
        "volume": round(volume, 6),
    }
    results.append(summary)
    return summary


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
run_lattice_seed_case("sphere_lattice")
raw_network = run_lattice_network_case("sphere_lattice_raw", 'RAW_EDGES')
welded_network = run_lattice_network_case("sphere_lattice_welded", 'FINAL_NETWORK')
if welded_network["edges"] >= raw_network["edges"]:
    raise RuntimeError(f"Expected welded network to remove duplicate edges: raw={raw_network}, welded={welded_network}")
if welded_network["vertices"] >= raw_network["vertices"]:
    raise RuntimeError(f"Expected welded network to reduce vertex count: raw={raw_network}, welded={welded_network}")
run_lattice_strut_case("sphere_lattice_struts")
run_case("cube_default_joined", seed_count=8, gap=0.05)
run_case("sphere", seed_count=10, gap=0.08)
run_case("cube_joined", seed_count=8, gap=0.05, join_cells=True, apply_wireframe=True)
run_case("cube_separate", seed_count=6, gap=0.05, join_cells=False)
print(json.dumps(results, indent=2))
voronoi_solid_addon.unregister()
