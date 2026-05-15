# Voronoi Solid Blender Addon

Project path:
`/Users/anoopjadhav/Documents/vibeCodedProjects/VoronoiSolidBlenderAddon`

This project contains a Blender addon that generates Voronoi-style volumetric cells from any selected closed mesh object.

Files:
- `voronoi_solid_addon/__init__.py` — installable addon
- `VoronoiSolidPatternAddon.zip` — packaged addon zip ready to install from Blender Preferences
- `run_selected_object.py` — quick runner script for the currently selected object
- `test_voronoi_addon.py` — headless validation script

Current release:
- addon version: `0.7.0`
- Blender target: `4.3.0`

What it does:
- samples interior and shell seeds with `Blue Noise` spacing by default for more even Voronoi distribution, with optional `Random` sampling when you want looser variation
- includes a `Lattice` mode that biases seeds to a shallow shell near the mesh surface
- can output either clipped Voronoi cells, a carved boolean solid result, raw extracted lattice edges, a welded/deduplicated debug edge network, or a printable strut mesh
- computes a Voronoi-like clipped cell for each point
- by default joins generated cells into one mesh object so modifiers affect the whole result
- can optionally keep cells as separate mesh objects in a new collection
- optionally shrinks each cell to create visible gaps

Current limitations:
- works best on clean, closed, manifold meshes
- this is a geometry prototype, not a polished production addon yet
- performance drops as cell count rises because each cell is clipped against every other point
- for very thin/complex shapes, increase `sample_attempt_multiplier`
- `Struts` now performs an Iteration 5 cleanup pass with gentle default network relaxation, configurable node-detail and boundary-repair controls, voxel remesh cleanup, and post-remesh smoothing to produce a watertight printable lattice mesh while getting closer to the Grasshopper-style reference

Tested:
- Blender 4.3.0
- cube: 8 cells generated successfully
- cube carved mode: boolean result generated successfully with lower volume than the source cube and `boundary_edges = 0`
- modifier-backed carved mode: array-modified cube keeps evaluated source extents (`source_max_x = carved_max_x = 3.8`) so boolean carving respects unapplied source modifiers
- UV sphere: 10 cells generated successfully
- lattice raw-edge, welded-network, relaxed-network, and printable-strut outputs validated in the headless suite
- printable strut output now verifies watertight cleanup with `boundary_edges = 0` on the test mesh

Headless test command:
```bash
/Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup --python /Users/anoopjadhav/Documents/vibeCodedProjects/VoronoiSolidBlenderAddon/test_voronoi_addon.py
```

Expected result:
- Blender prints passing generation checks for the cube and sphere cases, including lattice/strut validation
- exits with code 0

Option 1: Run as an installable addon in Blender
1. Open Blender.
2. Go to Edit > Preferences > Add-ons.
3. Click the dropdown in the top-right and choose Install from Disk.
4. Select:
   `/Users/anoopjadhav/Documents/vibeCodedProjects/VoronoiSolidBlenderAddon/VoronoiSolidPatternAddon.zip`
5. Enable `Voronoi Solid Pattern`.
6. Select a closed mesh object in Object Mode.
7. Open the 3D View sidebar with `N`.
8. Open the `Voronoi` tab.
9. Set:
   - `Mode`
   - `Solid Output` (`Cells` or `Carved` when using Solid mode)
   - `Cells`
   - `Sampling`
   - `Random Seed`
   - `Gap`
   - `Sample Attempts x`
   - `Collection`
   - `Join Cells` (enabled by default so one modifier affects the whole result)
10. Click `Generate Voronoi Cells`.

Generation controls:
- `Solid Output`
  - `Cells` — keeps the generated Voronoi cell meshes as the result
  - `Carved` — joins the generated cells and subtracts them from a duplicate of the source solid to create a perforated/carved boolean shell
- `Sampling`
  - `Blue Noise` — spreads shell and interior seeds more evenly using a greedy best-candidate pass
  - `Random` — preserves the older pure-random accepted seed placement
- `Surface Seeds` — number of shell-oriented seeds near the source surface
- `Interior Seeds` — optional extra seeds inside the volume
- `Shell Depth` — max inward offset from the surface for shell seeds
- `Shell Bias` — higher values keep seeds closer to the outer skin
- `Lattice Output`
  - `Cells` — clipped Voronoi cells
  - `Raw Edges` — extracted edge network before cleanup
  - `Final Network` — welded/deduplicated debug network
  - `Struts` — printable joined lattice mesh built from the cleaned network
- `Weld Tolerance` — merges nearby network vertices in debug and strut output
- `Min Edge Length` — drops tiny degenerate segments during cleanup
- `Duplicate Edge Tol` — removes nearly identical segments during cleanup
- `Relax Iterations` — optional Laplacian-style relaxation passes on the cleaned lattice network (defaults to a gentle value for a softer Grasshopper-like flow)
- `Relax Strength` — how strongly each relaxed lattice vertex moves toward its neighbors
- `Strut Radius` — radius of each printable lattice tube
- `Node Radius x` — expands node caps at welded junctions
- `Strut Sides` — cylinder side count for printable struts
- `Node Detail` — subdivision level for the spherical junction caps
- `Boundary Cleanup` — how many repair passes to run when closing tiny printable strut openings
- `Tiny Boundary Max` — boundary loops up to this edge count are treated as tiny cleanup candidates
- `Remesh Voxel` — explicit voxel size for printable strut cleanup; `0` keeps the automatic detail size
- `Smooth Iterations` — extra post-remesh smoothing passes for printable struts
- `Smooth Factor` — strength of each post-remesh smoothing pass

Option 2: Run the included script directly in Blender
1. Open Blender.
2. Open or create a mesh object.
3. Select the target mesh in Object Mode.
4. Open the Scripting workspace.
5. Open this file:
   `/Users/anoopjadhav/Documents/vibeCodedProjects/VoronoiSolidBlenderAddon/run_selected_object.py`
6. Adjust the values at the top if needed:
   - `GENERATION_MODE`
   - `SOLID_OUTPUT_MODE`
   - `LATTICE_OUTPUT_MODE`
   - `SAMPLING_MODE`
   - `CELL_COUNT`
   - `SURFACE_SEED_COUNT`
   - `INTERIOR_SEED_COUNT`
   - `SURFACE_SHELL_DEPTH`
   - `SURFACE_SHELL_BIAS`
   - `WELD_TOLERANCE`
   - `MINIMUM_EDGE_LENGTH`
   - `DUPLICATE_EDGE_TOLERANCE`
   - `LATTICE_RELAX_ITERATIONS`
   - `LATTICE_RELAX_STRENGTH`
   - `STRUT_RADIUS`
   - `NODE_RADIUS_MULTIPLIER`
   - `STRUT_SIDES`
   - `NODE_SUBDIVISIONS`
   - `BOUNDARY_CLEANUP_ITERATIONS`
   - `BOUNDARY_COMPONENT_MAX_EDGES`
   - `STRUT_REMESH_VOXEL_SIZE`
   - `STRUT_SMOOTH_ITERATIONS`
   - `STRUT_SMOOTH_FACTOR`
   - `RANDOM_SEED`
   - `GAP`
   - `ATTEMPT_MULTIPLIER`
   - `KEEP_ORIGINAL`
   - `COLLECTION_NAME`
   - `JOIN_CELLS`
7. Click `Run Script`.
8. Generated cells will appear in a new collection.

Recommended starting values:
- simple object: `CELL_COUNT = 12`
- more detailed breakup: `CELL_COUNT = 20 to 40`
- visible gaps: `GAP = 0.05 to 0.12`
- complex meshes: `ATTEMPT_MULTIPLIER = 80 to 150`
- relaxed lattice preview: `LATTICE_RELAX_ITERATIONS = 3 to 6`, `LATTICE_RELAX_STRENGTH = 0.25 to 0.45`
- printable node detail: `NODE_SUBDIVISIONS = 1 to 2` for lighter meshes, `3` only when you need rounder junctions and can afford the extra density
- printable boundary repair: `BOUNDARY_CLEANUP_ITERATIONS = 4 to 8`, `BOUNDARY_COMPONENT_MAX_EDGES = 2 to 6`
- printable struts: `STRUT_REMESH_VOXEL_SIZE = 0.0` for auto or `0.02 to 0.05` to tune detail, `STRUT_SMOOTH_ITERATIONS = 2 to 6`, `STRUT_SMOOTH_FACTOR = 0.25 to 0.45`

Recommended printable strut preset for a medium-sized object:
- for roughly `100 x 100 mm` output scale, start with a medium-density strut layout rather than very dense cells
- use `LATTICE_RELAX_ITERATIONS = 4`
- use `LATTICE_RELAX_STRENGTH = 0.35`
- use `NODE_SUBDIVISIONS = 1`
- use `BOUNDARY_CLEANUP_ITERATIONS = 4`
- use `BOUNDARY_COMPONENT_MAX_EDGES = 2`
- use `STRUT_SMOOTH_ITERATIONS = 4`
- use `STRUT_SMOOTH_FACTOR = 0.35 to 0.45`
- keep `STRUT_REMESH_VOXEL_SIZE = 0.0` first, then switch to an explicit voxel size only if you need to trade detail for a cleaner printable surface

If generation fails:
- make sure the object is a closed mesh
- apply transforms if the mesh has unusual scale
- recalculate normals in Edit Mode
- try reducing `CELL_COUNT`
- increase `ATTEMPT_MULTIPLIER`

Next good improvements:
- blue-noise / Poisson sampling instead of pure random sampling
- boolean pattern carving mode instead of only generating separate cells
- Geometry Nodes-assisted preview workflow
- export helpers for 3D-printable shells or perforated surfaces
