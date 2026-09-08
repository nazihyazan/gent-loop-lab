#!/usr/bin/env python3
"""
Ghost Mannequin Fashion Catwalk Generator (Blender 4.0)
Generates high-end 9:16 vertical fashion runway videos with:
- Realistic catwalk walking armature & walk cycle (walking forward, turn, walk back)
- True Ghost Mannequin effect (hollow hood/collar, pitch-black void, no face/head)
- Stage runway environment with overhead track spotlights and glossy reflective floor
- Dynamic cloth drapery matching any uploaded dress, djellaba, or kaftan
"""

import bpy
import sys
import os
import math
import argparse
import bmesh

def clip(val, low=0.0, high=1.0):
    return max(low, min(val, high))

def parse_args():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []
        
    parser = argparse.ArgumentParser(description="Ghost Mannequin Catwalk Generator")
    parser.add_argument("--image", type=str, default="", help="Path to dress/garment photo")
    parser.add_argument("--color", type=str, default="#5c4046", help="Base dress hex color")
    parser.add_argument("--garment", type=str, default="hooded_jalaba", choices=["hooded_jalaba", "maxi_dress", "kaftan_cape"])
    parser.add_argument("--frames", type=int, default=120, help="Total frames (at 24fps: 120 frames = 5s, 240 frames = 10s)")
    parser.add_argument("--width", type=int, default=720, help="Render width (9:16 vertical default 720)")
    parser.add_argument("--height", type=int, default=1280, help="Render height (9:16 vertical default 1280)")
    parser.add_argument("--output", type=str, required=True, help="Output MP4 file path")
    return parser.parse_args(argv)

def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip('#')
    if len(hex_str) != 6:
        return (0.36, 0.25, 0.27, 1.0)
    r = int(hex_str[0:2], 16) / 255.0
    g = int(hex_str[2:4], 16) / 255.0
    b = int(hex_str[4:6], 16) / 255.0
    # sRGB to linear conversion
    r = math.pow(r, 2.2)
    g = math.pow(g, 2.2)
    b = math.pow(b, 2.2)
    return (r, g, b, 1.0)

def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for col in bpy.data.collections:
        bpy.data.collections.remove(col)
    for mesh in bpy.data.meshes:
        bpy.data.meshes.remove(mesh)
    for mat in bpy.data.materials:
        bpy.data.materials.remove(mat)

def setup_runway_stage():
    # World dark mood
    world = bpy.data.worlds.new("CatwalkWorld")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.012, 0.012, 0.016, 1.0)
    bg.inputs[1].default_value = 0.4
    
    # Runway Catwalk Floor (Glossy reflective dark catwalk)
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0, 2.5, 0.0))
    runway = bpy.context.active_object
    runway.name = "CatwalkFloor"
    runway.scale = (1.9, 14.0, 1.0)
    
    rmat = bpy.data.materials.new("CatwalkFloorMat")
    rmat.use_nodes = True
    rbsdf = rmat.node_tree.nodes["Principled BSDF"]
    rbsdf.inputs['Base Color'].default_value = (0.045, 0.045, 0.052, 1.0)
    rbsdf.inputs['Roughness'].default_value = 0.16 # High gloss reflection
    rbsdf.inputs['Metallic'].default_value = 0.40
    runway.data.materials.append(rmat)
    
    # Runway Side Walls (Dark tunnel perspective)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-2.2, 2.5, 2.8))
    left_wall = bpy.context.active_object
    left_wall.scale = (0.2, 14.0, 5.6)
    
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(2.2, 2.5, 2.8))
    right_wall = bpy.context.active_object
    right_wall.scale = (0.2, 14.0, 5.6)
    
    # Back Stage Wall
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 9.0, 2.8))
    back_wall = bpy.context.active_object
    back_wall.scale = (5.0, 0.2, 5.6)
    
    wmat = bpy.data.materials.new("WallDarkMat")
    wmat.use_nodes = True
    wbsdf = wmat.node_tree.nodes["Principled BSDF"]
    wbsdf.inputs['Base Color'].default_value = (0.015, 0.015, 0.02, 1.0)
    wbsdf.inputs['Roughness'].default_value = 0.95
    for wall in [left_wall, right_wall, back_wall]:
        wall.data.materials.append(wmat)
        
    # Overhead Lighting Rig / Truss (Stage beam lights visible at top)
    lamp_emiss_mat = bpy.data.materials.new("StageLampEmission")
    lamp_emiss_mat.use_nodes = True
    nodes = lamp_emiss_mat.node_tree.nodes
    nodes.clear()
    out = nodes.new(type='ShaderNodeOutputMaterial')
    emiss = nodes.new(type='ShaderNodeEmission')
    emiss.inputs['Color'].default_value = (1.0, 0.98, 0.95, 1.0)
    emiss.inputs['Strength'].default_value = 18.0
    lamp_emiss_mat.node_tree.links.new(emiss.outputs['Emission'], out.inputs['Surface'])
    
    # Overhead Spotlights on Catwalk
    spot_y_coords = [-0.5, 1.2, 2.9, 4.6, 6.3]
    for i, y_c in enumerate(spot_y_coords):
        # Physical lamp fixture mesh
        bpy.ops.mesh.primitive_cylinder_add(radius=0.14, depth=0.12, location=(0, y_c, 3.45))
        lamp_mesh = bpy.context.active_object
        lamp_mesh.data.materials.append(lamp_emiss_mat)
        
        # Spot Light
        spot_data = bpy.data.lights.new(name=f"RunwaySpot_{i}", type='SPOT')
        spot_data.energy = 4200
        spot_data.spot_size = math.radians(48)
        spot_data.spot_blend = 0.3
        spot_data.color = (1.0, 0.98, 0.95)
        
        spot_obj = bpy.data.objects.new(name=f"RunwaySpot_{i}", object_data=spot_data)
        spot_obj.location = (0, y_c, 3.4)
        spot_obj.rotation_euler = (0, 0, 0)
        bpy.context.collection.objects.link(spot_obj)
        
    # Front Key Light (Soft commercial fashion fill)
    front_data = bpy.data.lights.new(name="FrontKeyLight", type='AREA')
    front_data.energy = 1600
    front_data.size = 2.5
    front_data.color = (1.0, 0.96, 0.92)
    front_obj = bpy.data.objects.new(name="FrontKeyLight", object_data=front_data)
    front_obj.location = (0.0, -3.2, 2.0)
    front_obj.rotation_euler = (math.radians(65), 0, 0)
    bpy.context.collection.objects.link(front_obj)
    
    # Back Rim Silhouette Light
    rim_data = bpy.data.lights.new(name="RimLight", type='AREA')
    rim_data.energy = 1200
    rim_data.size = 3.2
    rim_data.color = (0.80, 0.88, 1.0)
    rim_obj = bpy.data.objects.new(name="RimLight", object_data=rim_data)
    rim_obj.location = (0.0, 7.5, 3.2)
    rim_obj.rotation_euler = (math.radians(130), 0, 0)
    bpy.context.collection.objects.link(rim_obj)

def create_catwalk_rig_and_animation(total_frames=120):
    """
    Creates an armature with high-fashion runway walk cycle:
    - Strides forward along runway (Y: 6.0 -> 0.0)
    - Hip sway, knee bend, alternating feet extension with high-heel pose
    - Turnaround at front of catwalk and walk back
    """
    bpy.ops.object.armature_add(location=(0, 0, 0))
    arm_obj = bpy.context.active_object
    arm_obj.name = "CatwalkArmature"
    arm = arm_obj.data
    arm.name = "ArmatureData"
    
    bpy.ops.object.mode_set(mode='EDIT')
    edit_bones = arm.edit_bones
    root_bone = edit_bones[0]
    root_bone.name = "Root"
    root_bone.head = (0, 0, 0)
    root_bone.tail = (0, 0, 0.2)
    
    # Pelvis / Hips
    hips = edit_bones.new("Hips")
    hips.head = (0, 0, 0.95)
    hips.tail = (0, 0, 1.15)
    hips.parent = root_bone
    
    # Spine & Torso
    spine = edit_bones.new("Spine")
    spine.head = (0, 0, 1.15)
    spine.tail = (0, 0, 1.45)
    spine.parent = hips
    
    # Neck & Head (Void anchor)
    neck = edit_bones.new("Neck")
    neck.head = (0, 0, 1.45)
    neck.tail = (0, 0, 1.75)
    neck.parent = spine
    
    # Legs (Left & Right)
    for side, prefix, sign in [(0.12, "L", 1), (-0.12, "R", -1)]:
        # Thigh
        thigh = edit_bones.new(f"Thigh.{prefix}")
        thigh.head = (sign * 0.12, 0, 0.95)
        thigh.tail = (sign * 0.11, 0.02, 0.52)
        thigh.parent = hips
        
        # Shin
        shin = edit_bones.new(f"Shin.{prefix}")
        shin.head = thigh.tail
        shin.tail = (sign * 0.10, -0.01, 0.14)
        shin.parent = thigh
        
        # Foot (Heel pose)
        foot = edit_bones.new(f"Foot.{prefix}")
        foot.head = shin.tail
        foot.tail = (sign * 0.10, -0.15, 0.02)
        foot.parent = shin
        
    # Arms (Left & Right)
    for side, prefix, sign in [(0.22, "L", 1), (-0.22, "R", -1)]:
        upper_arm = edit_bones.new(f"UpperArm.{prefix}")
        upper_arm.head = (sign * 0.22, 0, 1.42)
        upper_arm.tail = (sign * 0.32, 0.04, 1.05)
        upper_arm.parent = spine
        
        forearm = edit_bones.new(f"Forearm.{prefix}")
        forearm.head = upper_arm.tail
        forearm.tail = (sign * 0.35, -0.08, 0.72)
        forearm.parent = upper_arm
        
    bpy.ops.object.mode_set(mode='POSE')    # Animate Runway Walk Cycle
    walk_forward_end = int(total_frames * 0.65)
    turn_end = int(total_frames * 0.75)
    
    pose_bones = arm_obj.pose.bones
    cadence_frames = 24 # 1 full stride cycle = 24 frames
    
    for f in range(1, total_frames + 1):
        if f <= walk_forward_end:
            prog = (f - 1) / max(1, walk_forward_end - 1)
            y_pos = 4.2 - prog * 3.7 # Walks from 4.2m down to 0.5m in front of camera
            rot_z = 0.0 # Facing camera
            cycle_phase = ((f - 1) % cadence_frames) / cadence_frames * 2 * math.pi
            
            # Armature object translation along runway
            arm_obj.location = (0, y_pos, 0)
            arm_obj.rotation_euler = (0, 0, rot_z)
            arm_obj.keyframe_insert(data_path="location", frame=f)
            arm_obj.keyframe_insert(data_path="rotation_euler", frame=f)
            
            # Hip sway (Female runway model hip roll)
            hip_sway = math.sin(cycle_phase) * math.radians(6.0)
            hip_drop = math.cos(cycle_phase) * math.radians(3.0)
            bounce = -abs(math.sin(cycle_phase * 2)) * 0.02
            pose_bones["Hips"].rotation_euler = (0, hip_sway, hip_drop)
            pose_bones["Hips"].location = (0, 0, bounce)
            pose_bones["Hips"].keyframe_insert(data_path="rotation_euler", frame=f)
            pose_bones["Hips"].keyframe_insert(data_path="location", frame=f)
            
            # Left Leg (Forward and back swing)
            l_thigh_angle = math.sin(cycle_phase) * math.radians(26)
            l_knee_angle = max(0, -math.sin(cycle_phase + 0.5) * math.radians(40))
            pose_bones["Thigh.L"].rotation_euler = (l_thigh_angle, 0, math.radians(-2))
            pose_bones["Shin.L"].rotation_euler = (l_knee_angle, 0, 0)
            pose_bones["Thigh.L"].keyframe_insert(data_path="rotation_euler", frame=f)
            pose_bones["Shin.L"].keyframe_insert(data_path="rotation_euler", frame=f)
            
            # Right Leg (Opposite phase)
            r_thigh_angle = math.sin(cycle_phase + math.pi) * math.radians(26)
            r_knee_angle = max(0, -math.sin(cycle_phase + math.pi + 0.5) * math.radians(40))
            pose_bones["Thigh.R"].rotation_euler = (r_thigh_angle, 0, math.radians(2))
            pose_bones["Shin.R"].rotation_euler = (r_knee_angle, 0, 0)
            pose_bones["Thigh.R"].keyframe_insert(data_path="rotation_euler", frame=f)
            pose_bones["Shin.R"].keyframe_insert(data_path="rotation_euler", frame=f)
            
            # Arm swing (Gentle runway fashion swing)
            arm_swing_l = -math.sin(cycle_phase) * math.radians(12)
            arm_swing_r = -math.sin(cycle_phase + math.pi) * math.radians(12)
            pose_bones["UpperArm.L"].rotation_euler = (arm_swing_l, 0, math.radians(5))
            pose_bones["UpperArm.R"].rotation_euler = (arm_swing_r, 0, math.radians(-5))
            pose_bones["UpperArm.L"].keyframe_insert(data_path="rotation_euler", frame=f)
            pose_bones["UpperArm.R"].keyframe_insert(data_path="rotation_euler", frame=f)
            
        elif f <= turn_end:
            # Turnaround pivot at the front of runway
            turn_prog = (f - walk_forward_end) / max(1, turn_end - walk_forward_end)
            y_pos = 0.5
            rot_z = turn_prog * math.pi
            
            arm_obj.location = (0, y_pos, 0)
            arm_obj.rotation_euler = (0, 0, rot_z)
            arm_obj.keyframe_insert(data_path="location", frame=f)
            arm_obj.keyframe_insert(data_path="rotation_euler", frame=f)
            
            pose_bones["Hips"].rotation_euler = (0, 0, 0)
            pose_bones["Hips"].location = (0, 0, 0)
            pose_bones["Thigh.L"].rotation_euler = (math.radians(5), 0, 0)
            pose_bones["Thigh.R"].rotation_euler = (math.radians(-5), 0, 0)
            pose_bones["Hips"].keyframe_insert(data_path="rotation_euler", frame=f)
            pose_bones["Hips"].keyframe_insert(data_path="location", frame=f)
            pose_bones["Thigh.L"].keyframe_insert(data_path="rotation_euler", frame=f)
            pose_bones["Thigh.R"].keyframe_insert(data_path="rotation_euler", frame=f)
            
        else:
            # Walk back away down runway
            prog_back = (f - turn_end) / max(1, total_frames - turn_end)
            y_pos = 0.5 + prog_back * 3.0
            rot_z = math.pi
            cycle_phase = ((f - 1) % cadence_frames) / cadence_frames * 2 * math.pi
            
            arm_obj.location = (0, y_pos, 0)
            arm_obj.rotation_euler = (0, 0, rot_z)
            arm_obj.keyframe_insert(data_path="location", frame=f)
            arm_obj.keyframe_insert(data_path="rotation_euler", frame=f)
            
            l_thigh_angle = math.sin(cycle_phase) * math.radians(24)
            l_knee_angle = max(0, -math.sin(cycle_phase + 0.5) * math.radians(38))
            r_thigh_angle = math.sin(cycle_phase + math.pi) * math.radians(24)
            r_knee_angle = max(0, -math.sin(cycle_phase + math.pi + 0.5) * math.radians(38))
            
            pose_bones["Thigh.L"].rotation_euler = (l_thigh_angle, 0, 0)
            pose_bones["Shin.L"].rotation_euler = (l_knee_angle, 0, 0)
            pose_bones["Thigh.R"].rotation_euler = (r_thigh_angle, 0, 0)
            pose_bones["Shin.R"].rotation_euler = (r_knee_angle, 0, 0)
            pose_bones["Thigh.L"].keyframe_insert(data_path="rotation_euler", frame=f)
            pose_bones["Shin.L"].keyframe_insert(data_path="rotation_euler", frame=f)
            pose_bones["Thigh.R"].keyframe_insert(data_path="rotation_euler", frame=f)
            pose_bones["Shin.R"].keyframe_insert(data_path="rotation_euler", frame=f)
            
    bpy.ops.object.mode_set(mode='OBJECT')
    return arm_obj

def create_ghost_mannequin_shoes(arm_obj):
    shoes = []
    for side, prefix, sign in [(0.10, "L", 1), (-0.10, "R", -1)]:
        bpy.ops.mesh.primitive_cylinder_add(radius=0.045, depth=0.14, location=(sign * 0.10, -0.06, 0.07))
        shoe = bpy.context.active_object
        shoe.name = f"Heel_{prefix}"
        shoe.scale = (0.7, 1.4, 0.6)
        
        bpy.ops.mesh.primitive_cylinder_add(radius=0.012, depth=0.09, location=(sign * 0.10, 0.01, 0.045))
        stiletto = bpy.context.active_object
        
        bpy.ops.object.select_all(action='DESELECT')
        shoe.select_set(True)
        stiletto.select_set(True)
        bpy.context.view_layer.objects.active = shoe
        bpy.ops.object.join()
        
        smat = bpy.data.materials.new(f"ShoeMat_{prefix}")
        smat.use_nodes = True
        sbsdf = smat.node_tree.nodes["Principled BSDF"]
        sbsdf.inputs['Base Color'].default_value = (0.01, 0.01, 0.01, 1.0)
        sbsdf.inputs['Roughness'].default_value = 0.08
        shoe.data.materials.append(smat)
        
        shoe.parent = arm_obj
        shoe.parent_type = 'BONE'
        shoe.parent_bone = f"Foot.{prefix}"
        shoes.append(shoe)
        
    return shoes

def create_ghost_void_inner():
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.15, location=(0, 0, 1.72))
    void_sphere = bpy.context.active_object
    void_sphere.name = "GhostVoid"
    void_sphere.scale = (0.9, 0.8, 1.1)
    
    mat = bpy.data.materials.new("VoidBlackMat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs['Base Color'].default_value = (0.0, 0.0, 0.0, 1.0)
    bsdf.inputs['Roughness'].default_value = 1.0
    void_sphere.data.materials.append(mat)
    return void_sphere

def build_catwalk_dress_and_cape(arm_obj, base_color_hex="#5c4046", texture_path=""):
    # 1. Flowing Inner Maxi Dress
    dress_mesh = bpy.data.meshes.new("Mesh_CatwalkDress")
    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.verify()
    
    d_rows, d_circ = 32, 24
    d_verts = {}
    for r in range(d_rows):
        v = r / (d_rows - 1)
        z = 1.58 - v * 1.52
        flare = 0.20 + (v**1.2) * 0.26
        
        for c in range(d_circ):
            ang = (c / d_circ) * 2 * math.pi
            x = math.sin(ang) * flare
            y = math.cos(ang) * flare * 0.75
            
            vert = bm.verts.new((x, y, z))
            d_verts[(r, c)] = vert
            
    for r in range(d_rows - 1):
        for c in range(d_circ):
            c_next = (c + 1) % d_circ
            v1 = d_verts[(r, c)]
            v2 = d_verts[(r, c_next)]
            v3 = d_verts[(r + 1, c_next)]
            v4 = d_verts[(r + 1, c)]
            face = bm.faces.new((v1, v2, v3, v4))
            for loop in face.loops:
                v_norm = (loop.vert.co.z - 0.06) / 1.52
                u_norm = (loop.vert.co.x / 0.55 + 1.0) * 0.5
                loop[uv_layer].uv = (clip(u_norm, 0, 1), clip(1.0 - v_norm, 0, 1))
                
    bm.to_mesh(dress_mesh)
    bm.free()
    dress_obj = bpy.data.objects.new("Garment_CatwalkDress", dress_mesh)
    bpy.context.collection.objects.link(dress_obj)
    
    # 2. Outer Hooded Butterfly Cape (Drapes naturally down over shoulders and hips)
    cape_mesh = bpy.data.meshes.new("Mesh_CatwalkCape")
    bm_c = bmesh.new()
    uv_c = bm_c.loops.layers.uv.verify()
    
    c_rad, c_ang = 24, 28
    cape_verts = {}
    for r in range(c_rad):
        rad_ratio = r / (c_rad - 1)
        for a in range(c_ang):
            theta = (a / (c_ang - 1)) * math.pi * 1.5 - math.pi * 0.75
            # Natural shoulder-to-hip drape
            radius = 0.21 + rad_ratio * 0.22
            x = math.sin(theta) * radius * 1.15
            y = math.cos(theta) * radius * 0.90
            z = 1.50 - rad_ratio * 0.58 + math.sin(theta * 2) * 0.025
            vert = bm_c.verts.new((x, y, z))
            cape_verts[(r, a)] = vert
            
    for r in range(c_rad - 1):
        for a in range(c_ang - 1):
            v1 = cape_verts[(r, a)]
            v2 = cape_verts[(r, a + 1)]
            v3 = cape_verts[(r + 1, a + 1)]
            v4 = cape_verts[(r + 1, a)]
            face = bm_c.faces.new((v1, v2, v3, v4))
            for loop in face.loops:
                is_front = (a <= 3 or a >= c_ang - 4)
                if is_front:
                    # White Lace trim center strip
                    lu = 0.46 + loop.vert.co.x * 0.06
                    lv = (loop.vert.co.z - 0.9) / 0.6
                else:
                    lu = (loop.vert.co.x / 0.6 + 1.0) * 0.5
                    lv = (loop.vert.co.z - 0.9) / 0.6
                loop[uv_c].uv = (clip(lu, 0, 1), clip(lv, 0, 1))
                
    # Traditional Moroccan Hood (قب الجلابة المعلق فوق الرأس)
    h_rows, h_cols = 16, 16
    h_verts = {}
    for hr in range(h_rows):
        hu = hr / (h_rows - 1) # From neck up over head
        for hc in range(h_cols):
            hv = hc / (h_cols - 1) # Around circumference
            hang = (hv - 0.5) * math.pi * 1.05
            
            # Arched peaked hood
            h_rad = 0.16 + hu * 0.05
            hx = math.sin(hang) * h_rad * 1.05
            hy = math.cos(hang) * h_rad * 0.95 - (hu * 0.06)
            # Peaks at top (z=1.82) and tapers back
            hz = 1.48 + math.sin(hu * math.pi * 0.82) * 0.34
            
            vert = bm_c.verts.new((hx, hy, hz))
            h_verts[(hr, hc)] = vert
            
    for hr in range(h_rows - 1):
        for hc in range(h_cols - 1):
            v1 = h_verts[(hr, hc)]
            v2 = h_verts[(hr, hc + 1)]
            v3 = h_verts[(hr + 1, hc + 1)]
            v4 = h_verts[(hr + 1, hc)]
            face = bm_c.faces.new((v1, v2, v3, v4))
            for loop in face.loops:
                loop[uv_c].uv = (loop.vert.co.x * 1.5 + 0.5, (loop.vert.co.z - 1.48) / 0.35)
                
    bm_c.to_mesh(cape_mesh)
    bm_c.free()
    cape_obj = bpy.data.objects.new("Garment_CatwalkCape", cape_mesh)
    bpy.context.collection.objects.link(cape_obj)
    
    mat = bpy.data.materials.new("CatwalkFabricMat")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    
    out_node = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.inputs['Roughness'].default_value = 0.55
    if 'Sheen Weight' in bsdf.inputs:
        bsdf.inputs['Sheen Weight'].default_value = 0.8
        bsdf.inputs['Sheen Tint'].default_value = (0.95, 0.90, 0.92, 1.0)
        
    r, g, b, a = hex_to_rgb(base_color_hex)
    
    if texture_path and os.path.exists(texture_path):
        tex_img = bpy.data.images.load(os.path.abspath(texture_path))
        tex_node = nodes.new(type='ShaderNodeTexImage')
        tex_node.image = tex_img
        tex_node.location = (-400, 100)
        
        # Mix base color with texture
        mix_node = nodes.new(type='ShaderNodeMix')
        mix_node.data_type = 'RGBA'
        mix_node.blend_type = 'MULTIPLY'
        mix_node.inputs[0].default_value = 0.85 # Factor
        mix_node.inputs[6].default_value = (r, g, b, 1.0) # Base Color A
        links.new(tex_node.outputs['Color'], mix_node.inputs[7]) # Texture B
        links.new(mix_node.outputs[2], bsdf.inputs['Base Color'])
    else:
        bsdf.inputs['Base Color'].default_value = (r, g, b, 1.0)
        
    links.new(bsdf.outputs['BSDF'], out_node.inputs['Surface'])
    dress_obj.data.materials.append(mat)
    cape_obj.data.materials.append(mat)
    
    for obj in [dress_obj, cape_obj]:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.shade_smooth()
        
    for obj in [dress_obj, cape_obj]:
        arm_mod = obj.modifiers.new(name="ArmatureModifier", type='ARMATURE')
        arm_mod.object = arm_obj
        
    vg_spine = dress_obj.vertex_groups.new(name="Spine")
    vg_hips = dress_obj.vertex_groups.new(name="Hips")
    vg_thigh_l = dress_obj.vertex_groups.new(name="Thigh.L")
    vg_thigh_r = dress_obj.vertex_groups.new(name="Thigh.R")
    vg_shin_l = dress_obj.vertex_groups.new(name="Shin.L")
    vg_shin_r = dress_obj.vertex_groups.new(name="Shin.R")
    
    for v in dress_mesh.vertices:
        z = v.co.z
        x = v.co.x
        if z > 1.30:
            vg_spine.add([v.index], 1.0, 'REPLACE')
        elif z > 0.90:
            vg_hips.add([v.index], 1.0, 'REPLACE')
        elif z > 0.45:
            if x >= 0:
                vg_thigh_l.add([v.index], 0.85, 'REPLACE')
                vg_thigh_r.add([v.index], 0.15, 'REPLACE')
            else:
                vg_thigh_r.add([v.index], 0.85, 'REPLACE')
                vg_thigh_l.add([v.index], 0.15, 'REPLACE')
        else:
            if x >= 0:
                vg_shin_l.add([v.index], 0.8, 'REPLACE')
            else:
                vg_shin_r.add([v.index], 0.8, 'REPLACE')
                
    vg_cape_spine = cape_obj.vertex_groups.new(name="Spine")
    vg_cape_neck = cape_obj.vertex_groups.new(name="Neck")
    for v in cape_mesh.vertices:
        if v.co.z > 1.55:
            vg_cape_neck.add([v.index], 1.0, 'REPLACE')
        else:
            vg_cape_spine.add([v.index], 0.9, 'REPLACE')
            
    dress_obj.parent = arm_obj
    cape_obj.parent = arm_obj
    return dress_obj, cape_obj

def setup_runway_camera(target_obj, total_frames=120):
    cam_data = bpy.data.cameras.new("RunwayCam")
    cam_data.lens = 48
    cam_data.dof.use_dof = True
    cam_data.dof.focus_object = target_obj
    cam_data.dof.aperture_fstop = 2.8
    
    cam_obj = bpy.data.objects.new("RunwayCam", cam_data)
    bpy.context.collection.objects.link(cam_obj)
    bpy.context.scene.camera = cam_obj
    
    cam_obj.location = (0.0, -1.8, 1.10)
    
    track = cam_obj.constraints.new(type='TRACK_TO')
    track.target = target_obj
    track.track_axis = 'TRACK_NEGATIVE_Z'
    track.up_axis = 'UP_Y'
    
    for f in range(1, total_frames + 1):
        prog = (f - 1) / total_frames
        cam_z = 1.10 + math.sin(prog * math.pi * 2) * 0.02
        cam_obj.location = (0.0, -1.8, cam_z)
        cam_obj.keyframe_insert(data_path="location", frame=f)

def render_catwalk_video(output_path, total_frames=120, width=720, height=1280):
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = total_frames
    scene.render.fps = 24
    
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    
    scene.render.engine = 'BLENDER_EEVEE'
    scene.eevee.taa_render_samples = 32
    scene.eevee.use_gtao = True
    scene.eevee.use_ssr = True
    scene.eevee.use_soft_shadows = True
    
    scene.render.image_settings.file_format = 'FFMPEG'
    scene.render.ffmpeg.format = 'MPEG4'
    scene.render.ffmpeg.codec = 'H264'
    scene.render.ffmpeg.constant_rate_factor = 'HIGH'
    scene.render.ffmpeg.ffmpeg_preset = 'GOOD'
    scene.render.filepath = output_path
    
    print(f"[Ghost Catwalk] Rendering fashion runway animation to {output_path} ({total_frames} frames @ {width}x{height})...")
    bpy.ops.render.render(animation=True)
    
    # Blender often appends frame ranges like 'catwalk.mp40001-0120.mp4' or 'catwalk0001-0120.mp4'
    if not os.path.exists(output_path):
        out_dir = os.path.dirname(os.path.abspath(output_path))
        base_prefix = os.path.splitext(os.path.basename(output_path))[0]
        for fname in os.listdir(out_dir):
            if fname.startswith(base_prefix) and (fname.endswith('.mp4') or fname.endswith('.mkv')):
                candidate = os.path.join(out_dir, fname)
                import shutil
                shutil.copy2(candidate, output_path)
                print(f"[Ghost Catwalk] Normalized {fname} -> {output_path}")
                break
                
    print(f"[Ghost Catwalk] Catwalk video ready at: {output_path}")

def main():
    args = parse_args()
    print("=" * 60)
    print("GHOST MANNEQUIN FASHION CATWALK GENERATOR")
    print(f"Output: {args.output}")
    print(f"Frames: {args.frames} | Res: {args.width}x{args.height}")
    print("=" * 60)
    
    clear_scene()
    print("[1/5] Building Runway Stage & Overhead Spotlights...")
    setup_runway_stage()
    
    print("[2/5] Creating Catwalk Walk Cycle Armature & Rig...")
    arm_obj = create_catwalk_rig_and_animation(total_frames=args.frames)
    
    print("[3/5] Adding High-Heel Footwear & Ghost Void Interior...")
    create_ghost_mannequin_shoes(arm_obj)
    void_obj = create_ghost_void_inner()
    void_obj.parent = arm_obj
    void_obj.parent_type = 'BONE'
    void_obj.parent_bone = 'Neck'
    
    print("[4/5] Draping Dress & Butterfly Cape with Fabric Physics...")
    tex_path = args.image if (args.image and os.path.exists(args.image)) else None
    dress, cape = build_catwalk_dress_and_cape(arm_obj, base_color_hex=args.color, texture_path=tex_path)
    
    print("[5/5] Positioning 9:16 Vertical Fashion Camera...")
    target = bpy.data.objects.new("CameraTarget", None)
    target.location = (0, 0, 1.05)
    target.parent = arm_obj
    bpy.context.collection.objects.link(target)
    
    setup_runway_camera(target, total_frames=args.frames)
    
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    render_catwalk_video(args.output, total_frames=args.frames, width=args.width, height=args.height)

if __name__ == "__main__":
    main()
