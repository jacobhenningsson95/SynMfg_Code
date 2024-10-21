import sys
import bpy
import random
import mathutils
import math
import time
from datetime import datetime
import json
import traceback
import numpy as np
import subprocess
import os
import cv2

def print_to_log(path, filename, message, verbose=False):
    """

    Prints message to log file and to terminal if verbose is set.

    :param path: Path to log folder
    :param filename: Log filename
    :param message: Message to print
    :param verbose: Print to terminal or not
    :return: None
    """
    now = datetime.now()
    # dd/mm/YY H:M:S
    dt_string = now.strftime("%Y-%m-%d %H:%M:%S")

    message = dt_string + " " + message

    if path != None:
        with open(os.path.join(path, filename), "a") as log_file:
            log_file.write(message + "\n")

    if verbose:
        print(message)

    return None


def load_distractors(pass_object_index, max_size=1.0, max_count=5, distractor_type=0, distractor_segmentations=False,
                     uniform_distractor_scale=False):
    """
    Creates distractor objects and prepares their properties.

    :param pass_object_index: Current object index, this property is used for the segmentation mask generation.
    :param max_size: Max distractor object size.
    :param max_count: Max amount of distractors.
    :param distractor_type: Specifying the distractor shape type, if 0 random shapes will be selected.
    :param distractor_segmentations: Add properties used for the segmentation mask or not.
    :param uniform_distractor_scale: Use uniform scaling or not. Non-uniform scaling leads to shape distortions.
    :return: None
    """
    index_ob = pass_object_index

    # Get the random amount of distractors to add.
    count = random.randint(0, max_count)

    for idx_distractor in range(0, count):

        #If distractor type is 0 add random type.
        if distractor_type == 0:
            which_type = random.uniform(0.0, 6.0)

            if 0.0 <= which_type < 1.0:
                select_type = 1
            elif 1.0 <= which_type < 2.0:
                select_type = 2
            elif 2.0 <= which_type < 3.0:
                select_type = 3
            elif 3.0 <= which_type < 4.0:
                select_type = 4
            elif 4.0 <= which_type < 5.0:
                select_type = 5
            else:
                select_type = 6
        else:
            select_type = distractor_type

        if uniform_distractor_scale:
            dimension_x = random.uniform(0.0000000001, max_size)
            dimension_y = dimension_x
            dimension_z = dimension_x
        else:
            dimension_x = random.uniform(0.0000000001, max_size)
            dimension_y = random.uniform(0.0000000001, max_size)
            dimension_z = random.uniform(0.0000000001, max_size)

        if select_type == 1:
            bpy.ops.mesh.primitive_cube_add()
            distractor_name = "cube"
        elif select_type == 2:
            bpy.ops.mesh.primitive_uv_sphere_add()
            distractor_name = "uvsphere"
        elif select_type == 3:
            bpy.ops.mesh.primitive_ico_sphere_add()
            distractor_name = "icosphere"
        elif select_type == 4:
            bpy.ops.mesh.primitive_cylinder_add()
            distractor_name = "cylinder"
        elif select_type == 5:
            bpy.ops.mesh.primitive_monkey_add()
            distractor_name = "monkey"
        else:
            bpy.ops.mesh.primitive_cone_add()
            distractor_name = "cone"

        # Name the distractor
        bpy.context.selected_objects[0].name = "distractor_" + str(idx_distractor + 1) + "_" + distractor_name
        bpy.context.selected_objects[0].dimensions = (dimension_x, dimension_y, dimension_z)

        # Add segmentation mask properties
        if distractor_segmentations:
            bpy.context.selected_objects[0].pass_index = index_ob
            index_ob += 1

        collection_name = "collection_" + str(idx_distractor + 1) + "_" + distractor_name + "_distractor"

        bpy.ops.object.move_to_collection(collection_index=0, is_new=True,
                                          new_collection_name=collection_name)

    return None


def lift_distractors(distractors, location_z_unit, limit_min, limit_max):
    """
    Place loaded distractor objects in the scene relative to already placed obj files. The location z is used to
    place the distractors close to already placed objects in z axis.

    :param distractors: List of distractor objects
    :param location_z_unit: Max size dimension of placed file, used to determine
    :param limit_min: Min location for x and y.
    :param limit_max: Max location for x and y, previously calculated when place obj files.
    :return: None
    """
    for distractor in distractors:

        location_z_new = random.uniform(0.0, location_z_unit * 2.0)

        if location_z_new > location_z_unit:

            location_x_new = random.uniform(limit_min, limit_max)
            location_y_new = random.uniform(limit_min, limit_max)

            distractor.location.z = location_z_new
            distractor.location.x = location_x_new
            distractor.location.y = location_y_new

        else:

            distractor.location.z = location_z_new

    return None


def get_lowest_vertex_by_object(object):
    """
    Finds the coordinates of the vertex with the lowest z coordinate in world space.

    :param object: Object to find lowest vertex.
    :return: Coordinate of lowest z vertex.
    """
    mw = object.matrix_world  # Active object's world matrix
    glob_vertex_coordinates = [mw @ v.co for v in object.data.vertices]  # Global coordinates of vertices

    # Find the lowest Z value amongst the object's verts
    global_z_min = min([co.z for co in glob_vertex_coordinates])

    # Select all the vertices that are on the lowest Z
    lowest_vertex = mathutils.Vector((0.0, 0.0, 0.0))
    for v in object.data.vertices:

        v_world = mw @ v.co

        if v_world.z == global_z_min:
            lowest_vertex = v_world

    return lowest_vertex


def get_collection_dimensions(collection):

    x_cords = []
    y_cords = []
    z_cords = []

    for obj in collection.all_objects:
        x_cords.append(obj.location.x - (obj.dimensions.x / 2))
        x_cords.append(obj.location.x + (obj.dimensions.x / 2))

        y_cords.append(obj.location.y - (obj.dimensions.y / 2))
        y_cords.append(obj.location.y + (obj.dimensions.y / 2))

        z_cords.append(obj.location.z - (obj.dimensions.z / 2))
        z_cords.append(obj.location.z + (obj.dimensions.z / 2))



    total_dimensions = [abs(min(x_cords) - max(x_cords)), abs(min(y_cords) - max(y_cords)), abs(min(z_cords) - max(z_cords))]

    return total_dimensions

def place_object(idx_object, obj_colletion, placements, rot_x_min, rot_x_max, rot_y_min, rot_y_max, ub_scale, lb_scale,
                 loc_x_lb=0.0,
                 loc_y_lb=0.0, ):
    """
    Places objects in the 3D scene and makes sure that they don't collied.

    :param idx_object: Object index in the placement process,
    :param obj_colletion: Loaded obj collection.
    :param placements: Current placement information for the object
    :param rot_x_min: Min X Rotation.
    :param rot_x_max: Max X Rotation.
    :param rot_y_min: Min Y Rotation.
    :param rot_y_max: Max Y Rotation.
    :param ub_scale: Max distance offset between objects.
    :param lb_scale: Min distance offset between objects.
    :param loc_x_lb: Current object x loc with offset, this is used to place the current object.
    :param loc_y_lb: Current object y loc with offset, this is used to place the current object.

    :return: loc_x_lb - Updated object x loc with offset, this is used to place the next object.
    :return: loc_y_lb - Updated object y loc with offset, this is used to place the next object.
    :return: placements - Updated placements list with current object new placement.
    """

    if obj_colletion.name.endswith("_distractor"):
        # Start make random rotation
        euler_x = math.radians(random.uniform(rot_x_min, rot_x_max))
        euler_y = math.radians(random.uniform(rot_y_min, rot_y_max))

        for obj in obj_colletion.all_objects:
            obj.rotation_euler[0] = euler_x
            obj.rotation_euler[1] = euler_y
        # End make random rotation

    bpy.context.view_layer.update()

    placement_key = obj_colletion.name.split("_")[2]

    if placement_key in placements:
        object_dim_max = placements[placement_key]
        object_dim_max = object_dim_max[1]
    else:
        object_dim_max = max(get_collection_dimensions(obj_colletion))

    if placement_key in placements:
        lowest_vertex = placements[placement_key]
        lowest_vertex = lowest_vertex[0]
    else:
        collection_lowest_vertex = []
        for obj in obj_colletion.all_objects:
            collection_lowest_vertex.append(get_lowest_vertex_by_object(obj))

        lowest_vertex = min(collection_lowest_vertex, key=lambda v: v.z)

    bpy.context.scene.cursor.location = lowest_vertex

    bpy.ops.object.select_all(action='DESELECT')

    for obj in obj_colletion.all_objects:
        obj.select_set(True)
        bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
        obj.location.z = 0.0
        obj.select_set(False)

    bpy.context.view_layer.update()


    if placement_key in placements:

        placement = placements[placement_key]

        if len(placement) == 4:

            object_loc_x_new = placement[2]
            object_loc_y_new = placement[3]

        else:

            if idx_object == 0:
                object_loc_x_new = random.uniform(loc_x_lb + object_dim_max * lb_scale,
                                                  loc_x_lb + object_dim_max * ub_scale)
                object_loc_y_new = random.uniform(loc_y_lb + object_dim_max * lb_scale,
                                                  loc_y_lb + object_dim_max * ub_scale)
            else:
                if idx_object % 2 == 0:
                    object_loc_x_new = random.uniform(loc_x_lb + object_dim_max * lb_scale,
                                                      loc_x_lb + object_dim_max * ub_scale)
                    object_loc_y_new = random.uniform(object_dim_max * lb_scale, loc_y_lb)
                else:
                    object_loc_x_new = random.uniform(object_dim_max * lb_scale, loc_x_lb)
                    object_loc_y_new = random.uniform(loc_y_lb + object_dim_max * lb_scale,
                                                      loc_y_lb + object_dim_max * ub_scale)

            placement.append(object_loc_x_new)
            placement.append(object_loc_y_new)

            placements[placement_key] = placement

    else:

        if idx_object == 0:
            object_loc_x_new = random.uniform(loc_x_lb + object_dim_max * lb_scale,
                                              loc_x_lb + object_dim_max * ub_scale)
            object_loc_y_new = random.uniform(loc_y_lb + object_dim_max * lb_scale,
                                              loc_y_lb + object_dim_max * ub_scale)
        else:
            if idx_object % 2 == 0:
                object_loc_x_new = random.uniform(loc_x_lb + object_dim_max * lb_scale,
                                                  loc_x_lb + object_dim_max * ub_scale)
                object_loc_y_new = random.uniform(object_dim_max * lb_scale, loc_y_lb)
            else:
                object_loc_x_new = random.uniform(object_dim_max * lb_scale, loc_x_lb)
                object_loc_y_new = random.uniform(loc_y_lb + object_dim_max * lb_scale,
                                                  loc_y_lb + object_dim_max * ub_scale)

    for obj in obj_colletion.all_objects:
        obj.location.x = object_loc_x_new
        obj.location.y = object_loc_y_new
    # End set location

    loc_x_lb_new = object_loc_x_new + object_dim_max * lb_scale
    loc_y_lb_new = object_loc_y_new + object_dim_max * lb_scale

    if loc_x_lb < loc_x_lb_new and (obj_colletion.name.endswith("_object") or obj_colletion.name.endswith("_duplicate")):
        print("loc_x_lb: ", loc_x_lb)
        loc_x_lb = loc_x_lb_new

    if loc_y_lb < loc_y_lb_new and (obj_colletion.name.endswith("_object") or obj_colletion.name.endswith("_duplicate")):
        loc_y_lb = loc_y_lb_new

    bpy.context.view_layer.update()

    return loc_x_lb, loc_y_lb, placements


def camera_look_at(camera_obj, target_point):
    """
    Points the camera object at a given point.

    :param camera_obj: Camera object.
    :param target_point: Coordinates to point the camera.
    """
    loc_camera = camera_obj.matrix_world.to_translation()

    direction = target_point - loc_camera
    # point the cameras '-Z' and use its 'Y' as up
    rot_quat = direction.to_track_quat('-Z', 'Y')

    # assume we're using euler rotation
    camera_obj.rotation_euler = rot_quat.to_euler()


def spherical_to_cartesian(r, theta, phi):
    """
    Convert spherical coordinates to cartesian coordinates

    :param r: radius.
    :param theta: polar angle.
    :param phi: azimuthal angle.
    :return: Converted cartesian coordinates.
    """
    x = r * math.sin(phi) * math.cos(theta)
    y = r * math.sin(phi) * math.sin(theta)
    z = r * math.cos(phi)
    return x, y, z


def calcBoundingBox(mesh_objs):
    """
    Calculates the total 3D bounding box given mesh object list.
    This includes the bounding box dimension and the center point of the bounding box.


    :param mesh_objs: List of mesh objects.
    :return: center_point - Updated object y loc with offset, this is used to place the next object.
    :return: dimensions - Updated placements list with current object new placement.
    """
    cornerApointsX = []
    cornerApointsY = []
    cornerApointsZ = []
    cornerBpointsX = []
    cornerBpointsY = []
    cornerBpointsZ = []

    for ob in mesh_objs:
        bbox_corners = [ob.matrix_world @ mathutils.Vector(corner) for corner in ob.bound_box]
        cornerApointsX.append(bbox_corners[0].x)
        cornerApointsY.append(bbox_corners[0].y)
        cornerApointsZ.append(bbox_corners[0].z)
        cornerBpointsX.append(bbox_corners[6].x)
        cornerBpointsY.append(bbox_corners[6].y)
        cornerBpointsZ.append(bbox_corners[6].z)

    minA = mathutils.Vector((min(cornerApointsX), min(cornerApointsY), min(cornerApointsZ)))
    maxB = mathutils.Vector((max(cornerBpointsX), max(cornerBpointsY), max(cornerBpointsZ)))

    center_point = mathutils.Vector(((minA.x + maxB.x) / 2, (minA.y + maxB.y) / 2, (minA.z + maxB.z) / 2))
    dimensions = mathutils.Vector((maxB.x - minA.x, maxB.y - minA.y, maxB.z - minA.z))

    return center_point, dimensions


def set_bsdf_roughness_val(principled_bsdf, val, log_path=None, log_filename=None, log_verbose=None):
    """
    Sets the roughness value for the PBR material and logs the value.

    :param principled_bsdf: Material node.
    :param val: Roughness value.
    :param log_path: Path to log folder.
    :param log_filename: Log filename.
    :param log_verbose: Print to terminal boolean.
    :return: Material node with the specified roughness value.
    """
    principled_bsdf.inputs['Roughness'].default_value = val

    # Start write to log file
    log_msg = "Set BSDF Roughness: " + str(val)
    print_to_log(log_path, log_filename, log_msg,
                 log_verbose)
    # End write to log file

    return principled_bsdf


def set_bsdf_specular_val(principled_bsdf, val, log_path=None, log_filename=None, log_verbose=None):
    """
    Sets the specular value for the PBR material and logs the value.

    :param principled_bsdf: Material node.
    :param val: Specular value.
    :param log_path: Path to log folder.
    :param log_filename: Log filename.
    :param log_verbose: Print to terminal boolean.
    :return: Material node with the specified specular value.
    """
    principled_bsdf.inputs['Specular'].default_value = val

    # Start write to log file
    log_msg = "Set BSDF Specular: " + str(val)
    print_to_log(log_path, log_filename, log_msg,
                 log_verbose)
    # End write to log file

    return principled_bsdf


def set_bsdf_metallic_val(principled_bsdf, val, log_path=None, log_filename=None, log_verbose=None):
    """
    Sets the metalic value for the PBR material and logs the value.

    :param principled_bsdf: Material node.
    :param val: Metalic value.
    :param log_path: Path to log folder.
    :param log_filename: Log filename.
    :param log_verbose: Print to terminal boolean.
    :return: Material node with the specified metalic value.
    """
    principled_bsdf.inputs['Metallic'].default_value = val

    # Start write to log file
    log_msg = "Set BSDF Metallic: " + str(val)
    print_to_log(log_path, log_filename, log_msg,
                 log_verbose)
    # End write to log file

    return principled_bsdf


def set_bsdf_property(principled_bsdf, log_path=None, log_filename=None, log_verbose=None):
    """
    Assigns randomised metalic, specular and roughness material to an exsisting material node.

    :param principled_bsdf: Material node.
    :param log_path: Path to log folder.
    :param log_filename: Log filename.
    :param log_verbose: Print to terminal boolean.
    :return: Material node with randomized properties.
    """

    bsdf_metallic_val = random.uniform(0.2, 0.8)
    bsdf_specular_val = random.uniform(0.2, 0.8)
    bsdf_roughness_val = random.uniform(0.2, 0.8)

    principled_bsdf.inputs['Metallic'].default_value = bsdf_metallic_val
    principled_bsdf.inputs['Specular'].default_value = bsdf_specular_val
    principled_bsdf.inputs['Roughness'].default_value = bsdf_roughness_val

    # Start write to log file
    log_msg = "Set BSDF property: Metallic=" + str(bsdf_metallic_val) + " Specular=" + str(
        bsdf_specular_val) + " Roughness=" + str(bsdf_roughness_val)
    print_to_log(log_path, log_filename, log_msg,
                 log_verbose)
    # End write to log file

    return principled_bsdf


def delete_shader_nodes(material):
    """
    Removes all material propery nodes from a given material.

    :param material: Material to remove properties from.
    :return: given material without material property nodes.
    """
    material_nodes = material.node_tree.nodes

    for node in material_nodes:

        if node.name != "Principled BSDF" and node.name != "Material Output":
            material.node_tree.nodes.remove(node)

    return material


def create_material(material_name="new material name"):
    """
    Creates new material with specified name.

    :param material_name: Name of the new material.
    :return: Created material with specified name.
    """
    material_new = bpy.data.materials.new(name=material_name)
    material_new.use_nodes = True

    return material_new


def set_color_texture(material, color=(0.0, 0.0, 0.0, 1.0), log_path=None, log_filename=None, log_verbose=None):
    """
    Applies a solid specified color to a given material and randomizes other material properties such
    as metalic, specular and roughness.
    :param material: Given material.
    :param color: Specified color in RGBA format.
    :param log_path: Path to log folder.
    :param log_filename: Log filename.
    :param log_verbose: Print to terminal boolean.
    :return: Material with applied solid color and randomized material properties.
    """
    material.use_nodes = True
    bsdf = material.node_tree.nodes["Principled BSDF"]

    # base color
    bsdf.inputs["Base Color"].default_value = color

    bsdf = set_bsdf_property(bsdf, log_path=log_path, log_filename=log_filename, log_verbose=log_verbose)

    # Start write to log file
    log_msg = "Set color texture: " + str(color)
    print_to_log(log_path, log_filename, log_msg,
                 log_verbose)
    # End write to log file

    return material


def create_displace_texture_node(material, file_path):
    """
    Creates a displacement node texture and adds it to given material. The displacement is controlled
    by a specified displacement map file.

    :param material: Given material to add displacement to.
    :param file_path: File path to displacement map.
    :return: Material with added displacement node.
    """
    material.use_nodes = True

    bsdf = material.node_tree.nodes["Principled BSDF"]

    image_node = material.node_tree.nodes.new('ShaderNodeTexImage')
    image_node.image = bpy.data.images.load(os.path.abspath(file_path))

    # change color space to Non-Color
    image_node.image.colorspace_settings.name = 'Non-Color'

    # new Displacement node
    displacement_node = material.node_tree.nodes.new('ShaderNodeDisplacement')
    displacement_node.inputs[1].default_value = 0.0  # Midlevel
    displacement_node.inputs[2].default_value = 0.01  # Scale

    # link Displacement node to Material Output node
    material_output_node = material.node_tree.nodes["Material Output"]
    material.node_tree.links.new(material_output_node.inputs['Displacement'], displacement_node.outputs['Displacement'])

    # link image texture node to Displacement node
    material.node_tree.links.new(displacement_node.inputs['Height'], image_node.outputs['Color'])

    return material


def create_norm_texture_node(material, file_path):
    """
    Creates a normal map texture node and adds it to given material. The normal map is controlled
    by a specified normal map file.

    :param material: Given material to add normal map to.
    :param file_path: File path to normal map.
    :return: Material with added normal map node.
    """
    material.use_nodes = True

    bsdf = material.node_tree.nodes["Principled BSDF"]

    image_node = material.node_tree.nodes.new('ShaderNodeTexImage')
    image_node.image = bpy.data.images.load(os.path.abspath(file_path))

    # change color space to Non-Color
    image_node.image.colorspace_settings.name = 'Non-Color'

    # new Normal Map node
    normal_map_node = material.node_tree.nodes.new('ShaderNodeNormalMap')

    # link Normal Map node to Normal
    material.node_tree.links.new(bsdf.inputs['Normal'], normal_map_node.outputs['Normal'])

    # link image texture node to Normal Map
    material.node_tree.links.new(normal_map_node.inputs['Color'], image_node.outputs['Color'])

    return material


def create_rough_texture_node(material, file_path):
    """
    Creates a roughness texture node and adds it to given material. The roughness is controlled
    by a specified roughness map file.

    :param material: Given material to add normal map to.
    :param file_path: File path to roughness map.
    :return: Material with added roughness map node.
    """
    material.use_nodes = True

    bsdf = material.node_tree.nodes["Principled BSDF"]

    image_node = material.node_tree.nodes.new('ShaderNodeTexImage')
    image_node.image = bpy.data.images.load(os.path.abspath(file_path))

    # change color space to Non-Color
    image_node.image.colorspace_settings.name = 'Non-Color'

    # link node to Roughness
    material.node_tree.links.new(bsdf.inputs['Roughness'], image_node.outputs['Color'])

    return material


def create_metal_texture_node(material, file_path):
    """
    Creates a metal texture node and adds it to given material. The metallicness is controlled
    by a specified metallic map file that controls two values "Metallic" and "Specular".

    :param material: Given material to add normal map to.
    :param file_path: File path to normal map.
    :return: Material with added normal map node.
    """
    material.use_nodes = True

    bsdf = material.node_tree.nodes["Principled BSDF"]

    image_node = material.node_tree.nodes.new('ShaderNodeTexImage')
    image_node.image = bpy.data.images.load(os.path.abspath(file_path))

    # change color space to Non-Color
    image_node.image.colorspace_settings.name = 'Non-Color'

    # link node to Metallic and Specular
    material.node_tree.links.new(bsdf.inputs['Metallic'], image_node.outputs['Color'])
    material.node_tree.links.new(bsdf.inputs['Specular'], image_node.outputs['Color'])

    return material


def create_image_texture_node(material, file_path):
    """
    Creates an image texture node and adds it to given material. The image is used as the material color.

    :param material: Given material to add image texture to.
    :param file_path: File path to image texture.
    :return: Material with added image texture node.
    """
    material.use_nodes = True

    bsdf = material.node_tree.nodes["Principled BSDF"]

    image_node = material.node_tree.nodes.new('ShaderNodeTexImage')
    image_node.image = bpy.data.images.load(os.path.abspath(file_path))

    material.node_tree.links.new(bsdf.inputs['Base Color'], image_node.outputs['Color'])

    return material


def set_image_texture(material, img_dir, log_path=None, log_filename=None, log_verbose=None):
    """
    Selects a random image from a specified folder of images and applies it as a texture to a given material.
    The selected image file is also logged.

    :param material: Material to apply the image texture to.
    :param img_dir: Folder path to images.
    :param log_path: Path to log folder.
    :param log_filename: Log filename.
    :param log_verbose: Print to terminal boolean.
    :return: Material with image texture applied.
    """

    valid_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp')

    # Start select a random image file
    files = [file for file in os.listdir(img_dir) if file.lower().endswith(valid_extensions)]
    random_file = random.choice(files)

    check_random_file_exist = str(random_file)

    while check_random_file_exist in used_texture_image:
        random_file = random.choice(files)
        check_random_file_exist = str(random_file)

    used_texture_image.add(check_random_file_exist)

    file_path = os.path.join(img_dir, random_file)
    # End select a random image file

    bsdf = material.node_tree.nodes["Principled BSDF"]
    bsdf = set_bsdf_property(bsdf, log_path=log_path, log_filename=log_filename, log_verbose=log_verbose)

    material = create_image_texture_node(material, file_path)

    # Start write to log file
    log_msg = "Set image texture: " + str(file_path)
    print_to_log(log_path, log_filename, log_msg,
                 log_verbose)
    # End write to log file

    return material


def set_pbr_texture(material, pbr_dir, log_path=None, log_filename=None, log_verbose=None):
    """
    Selects a random PBR material from a specified folder of PBR materials and applies all of its properties to a
    given material.

    :param material: Material to apply a randomly selected PBR to.
    :param pbr_dir: Folder path to PBRs.
    :param log_path: Path to log folder.
    :param log_filename: Log filename.
    :param log_verbose: Print to terminal boolean.
    :return: Material with PBR properties applied.
    """
    folders = [folder for folder in os.listdir(pbr_dir) if os.path.isdir(os.path.join(pbr_dir, folder))]
    random_folder = random.choice(folders)

    check_random_folder_exist = str(random_folder)

    while check_random_folder_exist in used_texture_pbr:
        random_folder = random.choice(folders)
        check_random_folder_exist = str(random_folder)

    used_texture_pbr.add(check_random_folder_exist)

    folder_path = os.path.join(pbr_dir, random_folder)

    files = os.listdir(folder_path)

    no_metal = True
    no_rough = True

    for filename in files:

        if "Color.jpg" in filename or "var1.jpg" in filename:

            file_path = os.path.join(folder_path, filename)
            material = create_image_texture_node(material, file_path)

        elif "Metalness.jpg" in filename:

            file_path = os.path.join(folder_path, filename)
            material = create_metal_texture_node(material, file_path)

        elif "Roughness.jpg" in filename:

            file_path = os.path.join(folder_path, filename)
            material = create_rough_texture_node(material, file_path)

        elif "NormalDX.jpg" in filename:

            file_path = os.path.join(folder_path, filename)
            material = create_norm_texture_node(material, file_path)

        elif "Displacement.jpg" in filename:

            file_path = os.path.join(folder_path, filename)
            material = create_displace_texture_node(material, file_path)

    bsdf = material.node_tree.nodes["Principled BSDF"]

    if no_metal:
        set_bsdf_metallic_val(bsdf, 0.0, log_path=log_path, log_filename=log_filename, log_verbose=log_verbose)
        set_bsdf_specular_val(bsdf, random.uniform(0.2, 0.8), log_path=log_path, log_filename=log_filename,
                              log_verbose=log_verbose)

    if no_rough:
        set_bsdf_roughness_val(bsdf, random.uniform(0.2, 0.8), log_path=log_path, log_filename=log_filename,
                               log_verbose=log_verbose)

    # Start write to log file
    log_msg = "Set material texture: " + str(folder_path) + " " + str(files)
    print_to_log(log_path, log_filename, log_msg,
                 log_verbose)
    # End write to log file

    return material

def set_none_texture(material, color=(0.0, 0.0, 0.0, 1.0), log_path=None, log_filename=None, log_verbose=None):
    """
    Applies simple material properties to the given material, applying only a color.

    :param material: Given material.
    :param color: Specified color in RGBA format.
    :param log_path: Path to log folder.
    :param log_filename: Log filename.
    :param log_verbose: Print to terminal boolean.
    :return: Material with added simple color.
    """


    material.use_nodes = True
    bsdf = material.node_tree.nodes["Principled BSDF"]

    # base color
    bsdf.inputs["Base Color"].default_value = color

    bsdf.inputs[1].default_value = 0.0

    for idx in range(4, 19):
        bsdf.inputs[idx].default_value = 0.0

    bsdf.inputs[20].default_value = 0.0

    # Start write to log file
    log_msg = "Set none texture: " + str(color)
    print_to_log(log_path, log_filename, log_msg,
                 log_verbose)
    # End write to log file

    return material

def set_material_texture(object, material, texture_type, img_dir=None, pbr_dir=None, log_path=None, log_filename=None,
                         log_verbose=None):
    """
    Applies a given material to a given object. The properties of the material is decided by the texture_type.
    texture_type 0 = Random, 1 = Image texture, 2 = Material texture, 3 = None. The selected texture and it's properties
    are logged.

    :param object: Object to apply material to.
    :param material: Material to apply.
    :param texture_type: Type of material.
    :param img_dir: Path to images used for image textures.
    :param pbr_dir: Path to PBR textures used for material textures.
    :param log_path: Path to log folder.
    :param log_filename: Log filename.
    :param log_verbose: Print to terminal boolean.
    :return: Material with applied properties.
    """
    if texture_type == -1 and (not object.name.startswith("distractor_")):
        return None

    if texture_type == 0 or texture_type == -1:
        which_type = random.uniform(0.0, 3.0)

        if 0.0 <= which_type < 1.0:
            texture_type = 1
        elif 1.0 <= which_type < 2.0:
            texture_type = 2
        else:
            texture_type = 3

    updated_material = delete_shader_nodes(material)

    # Start write to log file
    log_msg = "Final texture type: " + str(
        texture_type) + " (random texture=0, color texture=1, image texture=2, procedural texture=3, material texture=4, none=5)"
    print_to_log(log_path, log_filename, log_msg,
                 log_verbose)
    # End write to log file

    if texture_type == 1:

        # color texture
        random_color_r = random.uniform(0.0, 1.0)
        random_color_g = random.uniform(0.0, 1.0)
        random_color_b = random.uniform(0.0, 1.0)
        check_random_color_exist = str(int(random_color_r * 255.0)) + str(int(random_color_g * 255.0)) + str(
            int(random_color_b * 255.0))

        while check_random_color_exist in used_texture_color:
            random_color_r = random.uniform(0.0, 1.0)
            random_color_g = random.uniform(0.0, 1.0)
            random_color_b = random.uniform(0.0, 1.0)
            check_random_color_exist = str(int(random_color_r * 255.0)) + str(int(random_color_g * 255.0)) + str(
                int(random_color_b * 255.0))

        random_color = (random_color_r, random_color_g, random_color_b, 1.0)
        used_texture_color.add(check_random_color_exist)

        updated_material = set_color_texture(updated_material, random_color, log_path=log_path,
                                             log_filename=log_filename, log_verbose=log_verbose)

    elif texture_type == 2:

        updated_material = set_image_texture(updated_material, img_dir, log_path=log_path, log_filename=log_filename,
                                             log_verbose=log_verbose)

    elif texture_type == 3:

        updated_material = set_pbr_texture(updated_material, pbr_dir, log_path=log_path, log_filename=log_filename,
                                           log_verbose=log_verbose)

    else:

        updated_material = set_none_texture(updated_material, color=(0.5, 0.5, 0.5, 1.0),
                                            log_path=config_sys_render_log_path,
                                            log_filename=config_sys_render_log_filename,
                                            log_verbose=config_sys_render_log_verbose)

    return updated_material

def set_object_texture(object, texture_type=0, img_dir=None, pbr_dir=None, log_path=None, log_filename=None,
                       log_verbose=None):
    """
    Applies texture properties to a given objects material. If the object doesn't have a material one will be created.

    :param object: Object to apply material properties to.
    :param texture_type: Type of material.
    :param img_dir: Path to images used for image textures.
    :param pbr_dir: Path to PBR textures used for material textures.
    :param log_path: Path to log folder.
    :param log_filename: Log filename.
    :param log_verbose: Print to terminal boolean.
    :return: Object with applied material properties.
    :return:
    """
    if len(object.data.materials) > 0:

        # Get pre-defined materials for object
        for exist_material in object.data.materials:
            set_material_texture(object, exist_material, texture_type, img_dir, pbr_dir, log_path=log_path,
                                 log_filename=log_filename, log_verbose=log_verbose)

    else:

        # Create a new material and add it to the plane object
        object_material = create_material(material_name="color_texture")

        object_material = set_material_texture(object, object_material, texture_type, img_dir, pbr_dir,
                                               log_path=log_path, log_filename=log_filename, log_verbose=log_verbose)

        # Get pre-defined materials for object
        if object_material != None:
            object.data.materials.append(object_material)

    bpy.context.view_layer.update()

    return object


def enable_compositing(segment_out_path, index):
    """
    Creates segmentation maps by utilizing Blenders compositing system. Objects are segmented by using the
    previously applied object_index. The segmentation file is created during the rendering step.


    :param segment_out_path: output folder of the segmentations.
    :param index: Current generated image index, this is used for the segmentation file name.
    :return: None
    """
    bpy.data.scenes["Scene"].use_nodes = True
    bpy.context.scene.view_layers["ViewLayer"].use_pass_object_index = True

    compositing_nodes = bpy.data.scenes["Scene"].node_tree.nodes

    print("Removing")
    for compositing_node in compositing_nodes:
        bpy.data.scenes["Scene"].node_tree.nodes.remove(compositing_node)
    print("Finished Removing")
    bpy.data.scenes["Scene"].node_tree.nodes.new("CompositorNodeRLayers")

    bpy.data.scenes["Scene"].node_tree.nodes.new("CompositorNodeMath")
    bpy.data.scenes["Scene"].node_tree.nodes["Math"].operation = 'DIVIDE'
    bpy.data.scenes["Scene"].node_tree.nodes["Math"].operation = 'DIVIDE'
    bpy.data.scenes["Scene"].node_tree.nodes["Math"].inputs[1].default_value = 100

    color_ramp = bpy.data.scenes["Scene"].node_tree.nodes.new("CompositorNodeValToRGB")
    color_ramp.color_ramp.elements.remove(color_ramp.color_ramp.elements[0])

    bpy.data.scenes["Scene"].node_tree.nodes["ColorRamp"].color_ramp.interpolation = 'CONSTANT'

    color_ramp.color_ramp.elements.new(0.0)

    color_ramp.color_ramp.elements[0].color = (0, 0, 0, 1)
    segmentation_value = 0.01
    segmentation_count = 1

    print("Started Color ramp")
    for idx, obj in enumerate(bpy.data.objects):
        if obj.name.startswith("object_") or obj.name.startswith("distractor_"):
            print("adding element")
            color_ramp.color_ramp.elements.new(segmentation_value)
            print("Adding color")
            red = np.random.random()
            green = np.random.random()
            blue = np.random.random()

            color_ramp.color_ramp.elements[segmentation_count].color = (red, green, blue, 1)
            segmentation_value += 0.01
            segmentation_count += 1

    print("Starting linking")

    bpy.data.scenes["Scene"].node_tree.nodes.new("CompositorNodeOutputFile")
    bpy.data.scenes["Scene"].node_tree.nodes["File Output"].base_path = segment_out_path
    bpy.context.scene.frame_current = index
    bpy.data.scenes["Scene"].node_tree.nodes["File Output"].file_slots[0].path = "#"

    bpy.data.scenes["Scene"].node_tree.links.new(
        bpy.data.scenes["Scene"].node_tree.nodes["File Output"].inputs["Image"],
        bpy.data.scenes["Scene"].node_tree.nodes["ColorRamp"].outputs["Image"])

    bpy.data.scenes["Scene"].node_tree.links.new(
        bpy.data.scenes["Scene"].node_tree.nodes["ColorRamp"].inputs["Fac"],
        bpy.data.scenes["Scene"].node_tree.nodes["Math"].outputs["Value"])

    bpy.data.scenes["Scene"].node_tree.links.new(bpy.data.scenes["Scene"].node_tree.nodes["Math"].inputs["Value"],
                                                 bpy.data.scenes["Scene"].node_tree.nodes["Render Layers"].outputs[
                                                     "IndexOB"])

    return None

def camera_view_bounds_2d(scene, camera_object, mesh_object, fast_bboxes=True):
    """
    Calculates the 2d bounding box for an object in the scene. The bounding box is found by projecting vertices of the
    object to the 2d view plane.

    :param scene: blender scene object containing all 3D object information.
    :param camera_object: Camera of the scene.
    :param mesh_object: Object to project.
    :param fast_bboxes: Enables a faster way to calculate the 2d projections by selectively
    skipping some vertice projections. This method is much faster, but can be a bit more inaccurate.
    :return: Bounding box in YOLO XYWH format.
    """
    camera = camera_object
    an_obj = mesh_object

    # Get the inverse transformation matrix
    matrix = camera.matrix_world.normalized().inverted()
    # Create a new mesh data block, using the inverse transform matrix to undo any transformations
    mesh_matrix_world = an_obj.matrix_world
    dg = bpy.context.evaluated_depsgraph_get()
    ob = an_obj.evaluated_get(
        dg)  # this gives us the evaluated version of the object. Aka with all modifiers and deformations applied.
    mesh = ob.to_mesh()

    # mesh = mesh_object.to_mesh()
    vertices = [v.co.copy() for v in mesh.vertices]
    mesh.transform(an_obj.matrix_world)
    mesh.transform(matrix)

    # Get the world coordinates for the camera frame bounding box, before any transformations
    frame = [-v for v in camera.data.view_frame(scene=scene)[:3]]
    lx = []
    ly = []
    hit_count = 0
    depsgraph = bpy.context.view_layer.depsgraph

    normals = [p.normal for p in mesh.polygons]  # Compute polygon normals

    up = mathutils.Vector((0.0, 0.0, 1.0))
    view3d_area = next(a for a in bpy.context.screen.areas if a.ui_type == 'VIEW_3D')
    trans_world = (view3d_area.spaces.active.region_3d.view_matrix.inverted()).to_3x3() @ up
    trans_world.normalize()

    loop_time = time.time()
    vert_count = 0

    total_distance = 0.0
    num_edges = 0

    for idx, vert in enumerate(mesh.vertices):

        if idx + 1 < len(mesh.vertices):
            v1 = vert.co
            v2 = mesh.vertices[idx + 1].co

            # Calculate the distance between v1 and v2
            distance = (v1 - v2).length
            total_distance += distance
            num_edges += 1

    average_distance = total_distance / num_edges

    for idx, n in enumerate(normals):
        if trans_world.dot(n) >= 0:

            for v_i in mesh.polygons[idx].vertices:

                if not fast_bboxes or vert_count % 10 == 0 or average_distance < (
                        current_vertex - vertices[v_i]).length:

                    current_vertex = vertices[v_i]
                    vertex_loc = mesh_matrix_world @ current_vertex
                    direction = (vertex_loc - camera.location)
                    result = scene.ray_cast(depsgraph, origin=camera.location, direction=direction)

                    if an_obj.name == result[4].name:
                        unoccluded = True
                    else:
                        unoccluded = False

                vert_count += 1

                if unoccluded:

                    co_local = mesh.vertices[v_i].co
                    z = -co_local.z

                    if z <= 0.0:
                        # Vertex is behind the camera; ignore it
                        continue
                    else:
                        # Perspective division
                        frame = [(v / (v.z / z)) for v in frame]
                    min_x, max_x = frame[1].x, frame[2].x
                    min_y, max_y = frame[0].y, frame[1].y

                    x = (co_local.x - min_x) / (max_x - min_x)
                    y = (co_local.y - min_y) / (max_y - min_y)

                    hit_count += 1
                    lx.append(x)
                    ly.append(y)

    print("Loop time: " + str(time.time() - loop_time))
    print("Object hit: " + str(hit_count) + "/" + str(len(mesh.vertices)))
    # print("Object vert diff: " + str(vert_count) + "/" + str(len(mesh.vertices)))

    mesh_object.to_mesh_clear()
    # Image is not in view if all the mesh verts were ignored
    if not lx or not ly:
        return None
    min_x = np.clip(min(lx), 0.0, 1.0)
    min_y = np.clip(min(ly), 0.0, 1.0)
    max_x = np.clip(max(lx), 0.0, 1.0)
    max_y = np.clip(max(ly), 0.0, 1.0)

    # Image is not in view if both bounding points exist on the same side
    if min_x == max_x or min_y == max_y:
        return None

    min_y_flipped = 1.0 - max_y
    max_y_flipped = 1.0 - min_y

    width = max_x - min_x
    height = max_y_flipped - min_y_flipped
    x_center = (min_x + max_x) / 2
    y_center = (min_y_flipped + max_y_flipped) / 2

    return [x_center, y_center, width, height]


def make_bbox(scene, camera, names2labels, object_names, faster_bboxes):
    """

    Calculates the bounding box for each object in the scene.

    :param scene: Blender scene object
    :param camera: Camera object
    :param object_index_dict: Dict containing the label of the objects as values and the names of the objects as keys
    :param faster_bboxes: Faster bounding box calculation method boolean.
    :return: List of bounding boxes of objects in the scene in the YOLO XYWH format.
    """
    bpy.context.view_layer.update()

    print(object_index_dict)
    print(bpy.data.objects)

    for obj in bpy.data.objects:
        print(obj.name)

    bboxes = []

    mesh_objs = [obj for obj in bpy.data.objects if
                 obj.type == 'MESH' and not obj.hide_viewport and not obj.hide_render]
    for idx_obj, an_obj in enumerate(mesh_objs):
        if an_obj.name.startswith("object_"):
            print(an_obj.name)
            bbox = camera_view_bounds_2d(scene, camera, an_obj, faster_bboxes)
            if bbox is not None and 0.002 < min(bbox[-2:]):
                object_label = object_names[names2labels[an_obj.name]]
                bboxes.append((object_label, bbox))
                print(str(object_index_dict[an_obj.name]) + ": " + str(bbox))

    return bboxes


def save_bbox(bboxes, save_path, filename):
    """
    Saves a list of given bounding box to a text files in the specified path with the specified filename.
    All bounding boxes in the scene is saved to the same text file.

    :param bboxes: List of bounding boxes in the scene.
    :param save_path: Path to save the file.
    :param filename: file name for the bounding box text file.
    """
    write_text = ""
    with open(os.path.join(save_path, filename), 'w') as tfile:

        for bbox in bboxes:

            if bbox[1] is not None:
                obj_bbox_str = ""
                obj_bbox_str += str(bbox[0]) + " "
                for obj_bbox_ele in bbox[1]:
                    obj_bbox_str += str(obj_bbox_ele) + " "

                obj_bbox_str = obj_bbox_str.strip()
                obj_bbox_str += "\n"

                write_text += obj_bbox_str

        tfile.write(write_text)

    print("Saved bbox " + str(os.path.join(save_path, filename)))


def save_bbox_image(img_path, bbox_path, save_path, object_classes):
    """
    Draws the generated bounding boxes on to the rendered image, this can be useful for debugging. Requires opencv to be
    installed into blenders Python environment.

    :param img_path: Path to rendered image.
    :param bbox_path: Path to corresponding bounding boxes.
    :param save_path: Path to save the image with drawn bounding boxes.
    :param object_classes: List containing names that corresponds to the saved label index.
    """
    img = cv2.imread(img_path)

    height_img, width_img, _ = img.shape

    with open(bbox_path, 'r') as file:
        for line in file:
            # Split the line into individual values using whitespace as the delimiter
            values = line.split()

            # Convert the values to floats
            values = [(float(value)) for value in values]

            x_min = int((values[1] - values[3] / 2) * width_img)
            y_min = int((values[2] - values[4] / 2) * height_img)
            x_max = int((values[1] + values[3] / 2) * width_img)
            y_max = int((values[2] + values[4] / 2) * height_img)

            color = (0, 255, 0)  # Green color
            thickness = 2

            img = cv2.rectangle(img, (x_min, y_min), (x_max, y_max), color, thickness)
            object_name = object_classes[int(values[0])]
            img = cv2.putText(img, object_name, (x_min, y_min - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        cv2.imwrite(save_path, img)




if __name__ == '__main__':

    print("Starting Blender instance...")

    # Start read input arguments
    argv = sys.argv
    argv = argv[argv.index("--") + 1:]  # get all args after "--"

    filenames = json.loads(argv[-1])

    print("Amount of images to render: ", len(filenames))

    # config_path = "config-sample.json"
    json_string = argv[0]
    config_json = json.loads(json_string)

    models_path = config_json["system"]["models_path"]

    # list all models in the model path.
    files = sorted([file for file in os.listdir(models_path) if file.endswith(".obj")])
    objects_library = {}
    names2labels = {}

    # Start system parameters
    config_sys_render_engine_samples_max = config_json["system"]["render_engine_samples_max"]

    config_sys_background_texture_pool = config_json["system"]["background_texture_pool"]
    config_sys_image_texture_pool = config_json["system"]["image_texture_pool"]
    config_sys_pbr_texture_pool = config_json["system"]["pbr_texture_pool"]

    # Start user parameters
    config_user_render_image_width = config_json["user"]["render_image_width"]
    config_user_render_image_height = config_json["user"]["render_image_height"]
    config_user_render_image_format = config_json["user"]["render_image_format"]
    config_user_render_engine = config_json["user"]["render_engine"]
    config_user_eevee_postprocessing = config_json["user"]["eevee_postprocessing"]

    config_user_background_texture_type = config_json["user"]["background_texture_type"]  # 1=none, 2=image

    config_user_total_distracting_objects = config_json["user"]["total_distracting_objects"]  # equal or greater than 0
    config_user_distracting_objects_type = config_json["user"][
        "distracting_objects_type"]  # 0=random, 1=cube, 2=uvsphere, 3=icosphere, 4=cylinder, monkey=5, 6=cone
    config_user_objects_texture_type = config_json["user"][
        "objects_texture_type"]  # 0=random, 1=color, 2=image, 3=material, 4=none

    config_user_object_rotation_x_min = config_json["user"]["object_rotation_x_min"]
    config_user_object_rotation_x_max = config_json["user"]["object_rotation_x_max"]

    config_user_object_rotation_y_min = config_json["user"]["object_rotation_y_min"]
    config_user_object_rotation_y_max = config_json["user"]["object_rotation_y_max"]

    config_user_object_distance_scale_max = config_json["user"]["object_distance_scale_max"]
    config_user_object_distance_scale_min = config_json["user"]["object_distance_scale_min"]

    config_user_camera_zoom_min = config_json["user"][
        "camera_zoom_min"]  # 0.15 for 2 or more distracting objects. 0.3 for zero distracting object.
    config_user_camera_zoom_max = config_json["user"]["camera_zoom_max"]

    config_user_camera_theta_min = config_json["user"]["camera_theta_min"]
    config_user_camera_theta_max = config_json["user"]["camera_theta_max"]
    config_user_camera_phi_min = config_json["user"]["camera_phi_min"]
    config_user_camera_phi_max = config_json["user"]["camera_phi_max"]

    config_user_camera_focus_point_x_shift_min = config_json["user"]["camera_focus_point_x_shift_min"]
    config_user_camera_focus_point_x_shift_max = config_json["user"]["camera_focus_point_x_shift_max"]
    config_user_camera_focus_point_y_shift_min = config_json["user"]["camera_focus_point_y_shift_min"]
    config_user_camera_focus_point_y_shift_max = config_json["user"]["camera_focus_point_y_shift_max"]
    config_user_camera_focus_point_z_shift_min = config_json["user"]["camera_focus_point_z_shift_min"]
    config_user_camera_focus_point_z_shift_max = config_json["user"]["camera_focus_point_z_shift_max"]

    config_user_light_count_auto = False
    if config_json["user"]["light_count_auto"] == 1:
        config_user_light_count_auto = True

    config_user_light_count_min = config_json["user"]["light_count_min"]
    config_user_light_count_max = config_json["user"]["light_count_max"]

    config_user_light_energy_min = config_json["user"]["light_energy_min"]
    config_user_light_energy_max = config_json["user"]["light_energy_max"]

    config_user_min_light_color_red = config_json["user"]["light_color_red_min"]
    config_user_max_light_color_red = config_json["user"]["light_color_red_max"]
    config_user_min_light_color_green = config_json["user"]["light_color_green_min"]
    config_user_max_light_color_green = config_json["user"]["light_color_green_max"]
    config_user_min_light_color_blue = config_json["user"]["light_color_blue_min"]
    config_user_max_light_color_blue = config_json["user"]["light_color_blue_max"]
    config_user_duplicate_objects = config_json["user"]["multiple_of_same_object"]
    config_user_distractor_segmentations = config_json["user"]["include_distractors_segmentations"]
    config_user_uniform_distractor_scale = config_json["user"]["uniform_distractor_scale"]
    config_user_enable_segmentations = config_json["user"]["segmentations"]
    config_user_max_number_objects = config_json["user"]["max_objects"]  # If -1 the amount of object files will be used
    config_user_object_weights = config_json["user"]["object_weights"]
    config_user_nr_objects_weights = config_json["user"]["nr_objects_weights"]
    config_user_bbox_imgs = config_json["user"]["bbox_imgs"]
    config_user_faster_bboxes = config_json["user"]["faster_bboxes"]
    config_user_background_samples = config_json["user"]["background_samples"]
    config_user_object_label = config_json["user"]["object_label"]
    config_enable_blender_save = config_json["user"]["save_blender_files"]
    config_gpu_ordinal = config_json["gpu_ordinal_for_generation"]
    config_user_object_pair_matrix = config_json["user"]["object_pair_matrix"]

    config_sys_render_output_path = None
    config_sys_render_label_path = None

    config_sys_blender_output_path = None
    config_sys_render_log_path = None
    config_sys_render_log_filename = None
    config_sys_render_segmentation_path = None
    config_sys_render_bbox_path = None

    render_engines = ['CYCLES', 'BLENDER_EEVEE']

    object_labels = config_user_object_label
    bbox_img_labels = {int(v): k for k, v in object_labels.items()}

    if config_user_max_number_objects == -1:
        number_of_objects = len(files)
    else:
        number_of_objects = config_user_max_number_objects

    if len(config_user_object_weights) != 0:

        try:
            assert len(config_user_object_weights) == len(files)
        except AssertionError:
            print("GENERATION_FAILURE: " + "The amount of object weights needs to be the same as there are objects")
            os._exit(0)
            bpy.ops.wm.quit_blender()

        object_weights = config_user_object_weights
    else:
        object_weights = None

    if len(config_user_nr_objects_weights) != 0:

        try:
            assert number_of_objects + int(config_user_background_samples) == len(config_user_nr_objects_weights)
        except AssertionError:
            print("GENERATION_FAILURE: " + "The amount of number objects weights should be the same as the max number of objects."
             " If background samples are used one additional weight at index 0 needs to be added to represent them")
            os._exit(0)
            bpy.ops.wm.quit_blender()

        number_of_objects_weights = config_user_nr_objects_weights
    else:
        number_of_objects_weights = None


    # limit the amount of CPU resources that the Blender instance can use not to overwhelm the system.
    bpy.context.scene.render.threads_mode = 'FIXED'
    bpy.context.scene.render.threads = 2

    # enable GPU computing
    bpy.context.preferences.addons['cycles'].preferences.compute_device_type = 'CUDA'
    bpy.data.scenes["Scene"].cycles.device = "GPU"
    # select the GPU to be used for rendering
    bpy.context.preferences.addons["cycles"].preferences.get_devices()
    print(bpy.context.preferences.addons["cycles"].preferences.compute_device_type)

    available_gpus = [gpu for gpu in bpy.context.preferences.addons['cycles'].preferences.devices if
                      gpu.type == 'CUDA']

    available_gpus_names = [gpu.name for gpu in available_gpus]

    # check which GPUs are avaiable through nvidia-smi, sometime Blender manages to get access to GPUs that it shouldn't,
    # especially in a cluster.
    result = subprocess.run(['nvidia-smi', '-L'], stdout=subprocess.PIPE)
    gpu_info = result.stdout.decode('utf-8').strip().split('\n')

    nvidia_smi_gpu_names = [line.split(': ')[1].split(' (')[0] for line in gpu_info]

    print("nvidia_smi: ", nvidia_smi_gpu_names)

    filtered_gpus = [available_gpus.pop(available_gpus_names.index(gpu)) for gpu in nvidia_smi_gpu_names if gpu in available_gpus_names]

    for i, gpu in enumerate(filtered_gpus):
        print(str(i) + ": " + str(gpu))

    for d in bpy.context.preferences.addons["cycles"].preferences.devices:
        d["use"] = 0
        print(d["name"], d["use"])

    # use all available gpus.
    if config_gpu_ordinal == -1:
        for d in filtered_gpus:
            d["use"] = 1
            print(d["name"], d["use"])
    else:
        d = filtered_gpus[config_gpu_ordinal]
        d["use"] = 1
        print(d["name"], d["use"])

    if config_user_eevee_postprocessing:
        bpy.context.scene.eevee.use_bloom = True
        bpy.context.scene.eevee.use_ssr = True


    # Import file paths and check that each object has a label.
    for idx_model, model in enumerate(files):
        model_path = os.path.join(models_path, model)
        model_label = model

        bpy.ops.wm.obj_import(filepath=model_path)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        collection_name = "collection_" + model + "_object"
        bpy.ops.object.move_to_collection(collection_index=0, is_new=True,
                                          new_collection_name=collection_name)

        objects_library[model_path] = collection_name

        if config_user_objects_texture_type != -1:
            for obj in bpy.data.collections[collection_name].all_objects:
                obj.select_set(True)
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_mode(type="FACE")
                bpy.ops.mesh.select_all(action='SELECT')

                # uv unwrap objects
                bpy.ops.uv.smart_project()
                bpy.ops.uv.pack_islands(margin=0)
                bpy.ops.object.mode_set(mode='OBJECT')

        for idx, obj in enumerate(bpy.data.collections[collection_name].all_objects):
            new_obj_name = "object_" + model_label + str(idx)
            names2labels[new_obj_name] = obj.name


            try:
                assert obj.name in object_labels
            except AssertionError:
                print("GENERATION_FAILURE: " + f"Object named {obj.name} in file {model} is not in the object_labels. "
                                               f"Re-export the object with the correct name or add it to the \"object_label\" dict in the configs file.")
                os._exit(0)
                bpy.ops.wm.quit_blender()

            obj.name = new_obj_name



    # repeat render loop until there are no more files to render.
    while filenames:

        for filename in filenames[:]:

            # Start timing
            start = time.time()

            # pick the render engine to use.
            if config_user_render_engine == -1:
                render_engine = random.choice(render_engines)
            else:
                render_engine = render_engines[config_user_render_engine]

            bpy.data.scenes["Scene"].render.engine = render_engine

            object_index_dict = {}

            config_sys_render_output_path = os.path.abspath(config_json["img_work_path"])
            config_sys_render_output_filename = str(filename)
            config_sys_render_label_path = os.path.abspath(config_json["label_work_path"])
            config_sys_render_label_filename = config_sys_render_output_filename + ".txt"

            if not config_json["continuous"]:
                config_sys_blender_output_path = os.path.abspath(config_json["blender_work_path"])
                config_sys_render_blender_filename = config_sys_render_output_filename + ".blend"
                config_sys_render_log_path = os.path.abspath(config_json["log_work_path"])
                config_sys_render_log_filename = config_sys_render_output_filename + "_log.log"
                config_sys_render_segmentation_path = os.path.abspath(config_json["segmentation_path"])
                config_sys_render_segmentation_filename = config_sys_render_output_filename + ".png"
                config_sys_render_bbox_path = os.path.abspath(config_json["bbox_img_work_path"])
                config_sys_render_bbox_filename = config_sys_render_output_filename + ".png"

            config_sys_render_log_verbose = False

            # End user parameters

            used_texture_color = set()
            used_texture_image = set()
            used_texture_pbr = set()
            used_texture_procedural = set()

            try:

                # Start clean the scene
                existing_objects = [obj for obj in bpy.data.objects if
                                    obj.type == 'MESH' and obj.name.startswith("object_") and not obj.name.endswith(
                                        "_duplicate")]
                for existing_obj in existing_objects:

                    for exist_material in existing_obj.data.materials:
                        updated_material = delete_shader_nodes(exist_material)

                    existing_obj.hide_viewport = True
                    existing_obj.hide_render = True

                existing_collections = [collection for collection in bpy.data.collections if collection.name.endswith("_duplicate") or collection.name.endswith("_distractor")]

                for collection in existing_collections:
                    bpy.data.collections.remove(collection)

                for collection in bpy.data.collections:
                    collection.hide_viewport = True
                    collection.hide_render = True

                # Do not remove 3d objects, but remove distractors, ground, and walls.
                remove_objects = [obj for obj in bpy.data.objects if
                                  obj.name.endswith("_duplicate") or not obj.name.startswith("object_")]

                for remove_obj in remove_objects:
                    if remove_obj.name.endswith("_duplicate"):
                        del names2labels[remove_obj.name]

                    bpy.data.objects.remove(remove_obj, do_unlink=True)

                for block in bpy.data.meshes:
                    if block.users == 0:
                        bpy.data.meshes.remove(block)

                for block in bpy.data.materials:
                    if block.users == 0:
                        bpy.data.materials.remove(block)

                for block in bpy.data.textures:
                    if block.users == 0:
                        bpy.data.textures.remove(block)

                for block in bpy.data.images:
                    if block.users == 0:
                        bpy.data.images.remove(block)

                # End clean the scene

                print("Finished Clean")

                bpy.context.scene.render.resolution_x = config_user_render_image_width
                bpy.context.scene.render.resolution_y = config_user_render_image_height

                # Load the objects into the scene
                current_pass_object_index = 1
                object_max_size = 0.0
                objects_placement = {}
                collection_duplications = {}
                collection_count = 1

                # if background samples are allowed then there can be images without .obj files.
                if config_user_background_samples:
                    minimum_objects = 0
                else:
                    minimum_objects = 1

                # choose the number of objects to pick randomly or based on weights.
                num_objects_to_pick = np.random.choice([i for i in range(minimum_objects, number_of_objects + 1)], 1,
                                                       p=number_of_objects_weights)

                # if there is a pair matrix select the objects based on it.
                if len(config_user_object_pair_matrix) == 0:

                    obj_files = np.random.choice(files, num_objects_to_pick, p=object_weights,
                                                 replace=config_user_duplicate_objects)
                else:
                    obj_files = []
                    obj_index = list(range(len(files)))

                    for i in range(num_objects_to_pick[0]):
                        first_obj_index = np.random.choice(obj_index, 1, p=object_weights)[0]
                        obj_files.append(files[first_obj_index])
                        if len(obj_files) >= num_objects_to_pick[0]:
                            break
                        else:
                            if sum(config_user_object_pair_matrix[first_obj_index]) != 0:
                                second_obj_index = \
                                    np.random.choice(obj_index, 1, p=config_user_object_pair_matrix[first_obj_index])[0]
                                obj_files.append(files[second_obj_index])

                print("Starting model import")

                if len(obj_files) != 0:
                    for idx_model, model in enumerate(obj_files):

                        model_path = os.path.join(models_path, model)
                        model_label = model

                        selected_objects = []

                        # if the object has already been loaded
                        collection_name = objects_library[model_path]

                        if bpy.data.collections[collection_name].hide_viewport == False:
                            # if the object is already in the current scene duplicate it.
                                print("Duplicating collection: " + collection_name)

                                collection_duplications[collection_name] = collection_duplications.get(collection_name, 0) + 1

                                duplicate_collection_name = collection_name + "_" + str(collection_duplications[collection_name]) + "_duplicate"

                                for obj in bpy.data.collections[collection_name].all_objects:
                                    original_name = obj.name
                                    duplicate_name = f"{original_name}_{str(collection_duplications[collection_name])}_duplicate"

                                    obj_label = names2labels[original_name]
                                    names2labels[duplicate_name] = obj_label

                                    duplicate = obj.copy()
                                    duplicate.data = obj.data.copy()
                                    duplicate.name = duplicate_name
                                    bpy.context.collection.objects.link(duplicate)
                                    for slot in duplicate.material_slots:
                                        # Make a copy of the material
                                        new_material = slot.material.copy()
                                        # Assign the copied material to the slot
                                        slot.material = new_material

                                    selected_objects.append(bpy.data.objects[duplicate.name])

                                bpy.ops.object.select_all(action='DESELECT')

                                for selected_object in selected_objects:
                                    selected_object.select_set(True)

                                bpy.ops.object.move_to_collection(collection_index=0, is_new=True,
                                                          new_collection_name=duplicate_collection_name)

                                collection_name = duplicate_collection_name

                        else:

                            print("Using collection: ", str(bpy.data.collections[collection_name]))

                            bpy.data.collections[collection_name].hide_viewport = False
                            bpy.data.collections[collection_name].hide_render = False

                            for obj in bpy.data.collections[collection_name].all_objects:
                                print("Unhidding obj: ", obj.name)
                                selected_objects.append(obj)
                                obj.hide_viewport = False
                                obj.hide_render = False

                            # Start write to log file
                                log_message = "Use existing Collection: " + collection_name
                                print_to_log(config_sys_render_log_path, config_sys_render_log_filename, log_message,
                                             config_sys_render_log_verbose)
                            # End write to log file

                        # random rotation for object.
                        euler_x = math.radians(
                            random.uniform(config_user_object_rotation_x_min, config_user_object_rotation_x_max))
                        euler_y = math.radians(
                            random.uniform(config_user_object_rotation_y_min, config_user_object_rotation_y_max))

                        object_lowest_vertex = mathutils.Vector((10.0, 10.0, 10.0))
                        collection_max_size = 0.0

                        print("Selected_objects: " + str(bpy.data.collections[collection_name].all_objects))
                        print("objects_library: " + str(objects_library))

                        for idx, selected_object in enumerate(bpy.data.collections[collection_name].all_objects):

                            # Start write to log file
                            log_message = "Set object name: " + selected_object.name

                            object_index_dict[selected_object.name] = files.index(model)

                            print_to_log(config_sys_render_log_path, config_sys_render_log_filename, log_message,
                                         config_sys_render_log_verbose)
                            # End write to log file

                            selected_object.rotation_euler[0] = euler_x
                            selected_object.rotation_euler[1] = euler_y

                            # Start write to log file
                            log_message = "Set object rotation x: " + str(math.degrees(euler_x)) + ", y: " + str(
                                math.degrees(euler_y))
                            print_to_log(config_sys_render_log_path, config_sys_render_log_filename, log_message,
                                         config_sys_render_log_verbose)
                            # End write to log file

                            bpy.context.view_layer.update()

                            obj_vertex = get_lowest_vertex_by_object(selected_object)

                            if obj_vertex.z < object_lowest_vertex.z:
                                object_lowest_vertex = obj_vertex

                            selected_object.pass_index = current_pass_object_index
                            current_pass_object_index += 1

                            object_size = max(selected_object.dimensions)

                            if object_size > object_max_size:
                                object_max_size = object_size

                            if object_size > collection_max_size:
                                collection_max_size = object_size

                        objects_placement["collect" + str(collection_count)] = [object_lowest_vertex,
                                                                                collection_max_size]

                        collection_count += 1

                else:
                    object_max_size = 0.2

                bpy.ops.object.select_all(action='DESELECT')

                # Load the distractors into the scene
                load_distractors(current_pass_object_index, object_max_size * 0.5,
                                 config_user_total_distracting_objects,
                                 distractor_type=config_user_distracting_objects_type,
                                 distractor_segmentations=config_user_distractor_segmentations,
                                 uniform_distractor_scale=config_user_uniform_distractor_scale)

                loc_x_lb_update, loc_y_lb_update = 0.1, 0.1

                object_collections = [coll for coll in bpy.data.collections if (coll.name.endswith(
                    "_object") or coll.name.endswith("_duplicate")) and not coll.hide_viewport and not coll.hide_render]

                random.shuffle(object_collections)

                distractor_colletions = [coll for coll in bpy.data.collections if coll.name.endswith("_distractor")]
                random.shuffle(distractor_colletions)

                distractors_midpoint = len(distractor_colletions) // 2

                mesh_collections = distractor_colletions[0:distractors_midpoint] + object_collections + distractor_colletions[distractors_midpoint:]

                for idx_obj, an_collection in enumerate(mesh_collections):
                    loc_x_lb_update, loc_y_lb_update, objects_placement = place_object(idx_obj, an_collection,
                                                                                       objects_placement,
                                                                                       config_user_object_rotation_x_min,
                                                                                       config_user_object_rotation_x_max,
                                                                                       config_user_object_rotation_y_min,
                                                                                       config_user_object_rotation_y_max,
                                                                                       config_user_object_distance_scale_max,
                                                                                       config_user_object_distance_scale_min,
                                                                                       loc_x_lb_update,
                                                                                       loc_y_lb_update)

                    # Start write to log file
                    log_message = "Set object texture for: " + str(an_collection.name)
                    print_to_log(config_sys_render_log_path, config_sys_render_log_filename, log_message,
                                 config_sys_render_log_verbose)
                    # End write to log file

                    for an_obj in an_collection.all_objects:
                        an_obj = set_object_texture(an_obj, texture_type=config_user_objects_texture_type,
                                                img_dir=config_sys_image_texture_pool,
                                                pbr_dir=config_sys_pbr_texture_pool,
                                                log_path=config_sys_render_log_path,
                                                log_filename=config_sys_render_log_filename,
                                                log_verbose=config_sys_render_log_verbose)

                if len(obj_files) != 0:
                    object_area_size = 2.0

                    # Start camera initialization
                    if loc_x_lb_update > loc_y_lb_update:
                        object_area_size = loc_x_lb_update
                    else:
                        object_area_size = loc_y_lb_update
                else:
                    object_area_size = 0.3

                # Start randomly lift distractors
                distractor_objs = [obj for obj in bpy.data.objects if
                                   obj.type == 'MESH' and obj.name.startswith("distractor_")]
                lift_distractors(distractor_objs, object_max_size, 0.0, object_area_size)
                # Start randomly lift distractors

                ground_plane_diagonal = math.sqrt(object_area_size ** 2 + object_area_size ** 2)

                bpy.ops.object.camera_add(location=(0.0, 0.0, 0.0), rotation=(0.0, 0.0, 0.0))
                camera = bpy.context.selected_objects[0]
                # bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)

                camera_view_angle = math.radians(
                    math.degrees(
                        2 * math.atan(bpy.context.object.data.sensor_width / (2 * bpy.context.object.data.lens))) / 2.0)

                ground_plane_diagonal_scale = 0.5

                # Start write to log file
                log_message = "Get ground_plane_diagonal=" + str(
                    ground_plane_diagonal) + ", ground_plane_diagonal_scale=" + str(ground_plane_diagonal_scale)
                print_to_log(config_sys_render_log_path, config_sys_render_log_filename, log_message,
                             config_sys_render_log_verbose)
                # End write to log file

                r = (ground_plane_diagonal * ground_plane_diagonal_scale) / math.tan(camera_view_angle)
                theta = math.radians(random.uniform(config_user_camera_theta_min, config_user_camera_theta_max))
                phi = math.radians(random.uniform(config_user_camera_phi_min, config_user_camera_phi_max))
                x, y, z = spherical_to_cartesian(r, theta, phi)

                # Start write to log file
                log_message = "Set camera: r=" + str(r) + " phi=" + str(math.degrees(phi)) + " theta=" + str(
                    math.degrees(theta)) \
                              + " zoom_scale=" + str(ground_plane_diagonal_scale)
                print_to_log(config_sys_render_log_path, config_sys_render_log_filename, log_message,
                             config_sys_render_log_verbose)
                # End write to log file

                # Get the center of all objects in the scene

                if len(obj_files) != 0:
                    mesh_objs = [obj for obj in bpy.data.objects if
                                 obj.type == 'MESH' and obj.name.startswith("object_") and not obj.name.startswith(
                                     "distractor_") and not obj.hide_viewport and not obj.hide_render]
                elif config_user_total_distracting_objects != 0:
                    mesh_objs = [obj for obj in bpy.data.objects if
                                 obj.type == 'MESH' and obj.name.startswith(
                                     "distractor_") and not obj.hide_viewport and not obj.hide_render]

                if len(mesh_objs) != 0:
                    center_point, dimensions = calcBoundingBox(mesh_objs)
                else:
                    center_point = mathutils.Vector((0, 0, 0))

                print("Center point: ", center_point)

                true_center_x = center_point[0]
                true_center_y = center_point[1]

                x = x + true_center_x
                y = y + true_center_y

                camera.location = mathutils.Vector((x, y, z))

                # Update the scene to reflect the changes
                bpy.context.view_layer.update()

                # Randomly re-generate a center point for camera to look at
                center_point_range = math.sin(math.radians(45)) * (
                        (ground_plane_diagonal * ground_plane_diagonal_scale) / 2)

                if random.uniform(-1, 1) > 0:
                    center_point[0] += random.uniform(center_point_range * config_user_camera_focus_point_x_shift_min,
                                                      center_point_range * config_user_camera_focus_point_x_shift_max)
                else:
                    center_point[0] += -1 * random.uniform(
                        center_point_range * config_user_camera_focus_point_x_shift_min,
                        center_point_range * config_user_camera_focus_point_x_shift_max)

                if random.uniform(-1, 1) > 0:
                    center_point[1] += random.uniform(center_point_range * config_user_camera_focus_point_y_shift_min,
                                                      center_point_range * config_user_camera_focus_point_y_shift_max)
                else:
                    center_point[1] += -1 * random.uniform(
                        center_point_range * config_user_camera_focus_point_y_shift_min,
                        center_point_range * config_user_camera_focus_point_y_shift_max)

                if random.uniform(-1, 1) > 0:
                    center_point[2] += random.uniform(center_point_range * config_user_camera_focus_point_z_shift_min,
                                                      center_point_range * config_user_camera_focus_point_z_shift_max)
                else:
                    center_point[2] += random.uniform(center_point_range * config_user_camera_focus_point_z_shift_min,
                                                      center_point_range * config_user_camera_focus_point_z_shift_max)
                camera_look_at(camera, center_point)

                camera_focal_length_scale = random.uniform(config_user_camera_zoom_min, config_user_camera_zoom_max)
                camera_focal_length_scale = 0.5 - camera_focal_length_scale
                camera_focal_length_value = 50.0

                if camera_focal_length_scale > 0:
                    camera_focal_length_scale = abs(camera_focal_length_scale)
                    camera_focal_length_value = 50 + camera_focal_length_scale * 50
                    bpy.context.object.data.lens = camera_focal_length_value
                else:
                    camera_focal_length_scale = abs(camera_focal_length_scale)
                    camera_focal_length_value = 50 - camera_focal_length_scale * 50
                    bpy.context.object.data.lens = camera_focal_length_value

                bpy.context.object.data.clip_start = 0.01

                # Start write to log file
                log_message = "Set camera focal length =" + str(camera_focal_length_value)
                print_to_log(config_sys_render_log_path, config_sys_render_log_filename, log_message,
                             config_sys_render_log_verbose)
                # End write to log file

                bpy.context.view_layer.update()


                bpy.context.scene.camera = camera
                # End camera initialization

                # Create a new material and add it to the plane object
                material_background = bpy.data.materials.new(name="background")

                if config_user_background_texture_type == 1:

                    material_background = set_none_texture(material_background, color=(0.5, 0.5, 0.5, 1.0),
                                                           log_path=config_sys_render_log_path,
                                                           log_filename=config_sys_render_log_filename,
                                                           log_verbose=config_sys_render_log_verbose)

                elif config_user_background_texture_type == 2:

                    material_background.use_nodes = True
                    bsdf = material_background.node_tree.nodes["Principled BSDF"]
                    bsdf.inputs[7].default_value = 0.0

                    # Start importing image texture for backgrounds
                    valid_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp')
                    bg_files = [file for file in os.listdir(config_sys_background_texture_pool) if file.lower().endswith(valid_extensions)]
                    image_file = random.choice(bg_files)
                    image_file_path = os.path.join(config_sys_background_texture_pool, image_file)

                    tex_image = material_background.node_tree.nodes.new('ShaderNodeTexImage')
                    tex_image.image = bpy.data.images.load(os.path.abspath(image_file_path))
                    material_background.node_tree.links.new(bsdf.inputs['Base Color'], tex_image.outputs['Color'])
                # End importing image texture for backgrounds

                # Start create a ground plane
                # ground_plane_size = math.sqrt( (camera.location[0]-center_point[0])**2 + (camera.location[1]-center_point[1])**2 ) * 2.0
                ground_plane_size = r * 2.2

                bpy.ops.mesh.primitive_plane_add(size=ground_plane_size,
                                                 location=(center_point[0], center_point[1], 0.0))
                plane_object = bpy.context.selected_objects[0]
                plane_object.name = "ground"

                if plane_object.data.materials:
                    plane_object.data.materials[0] = material_background
                plane_object.data.materials.append(material_background)
                # End create a ground plane

                # Start create 4 walls
                bpy.ops.mesh.primitive_plane_add(size=ground_plane_size, location=(
                    center_point[0], center_point[1] + ground_plane_size * 0.5, ground_plane_size * 0.5),
                                                 rotation=(math.radians(90.0), 0.0, 0.0))
                wall_object_a = bpy.context.selected_objects[0]
                wall_object_a.name = "wall_a"
                if wall_object_a.data.materials:
                    wall_object_a.data.materials[0] = material_background
                wall_object_a.data.materials.append(material_background)

                bpy.ops.mesh.primitive_plane_add(size=ground_plane_size, location=(
                    center_point[0] + ground_plane_size * 0.5, center_point[1], ground_plane_size * 0.5),
                                                 rotation=(0.0, math.radians(90.0), 0.0))
                wall_object_b = bpy.context.selected_objects[0]
                wall_object_b.name = "wall_b"
                if wall_object_b.data.materials:
                    wall_object_b.data.materials[0] = material_background
                wall_object_b.data.materials.append(material_background)

                bpy.ops.mesh.primitive_plane_add(size=ground_plane_size, location=(
                    center_point[0], center_point[1] - ground_plane_size * 0.5, ground_plane_size * 0.5),
                                                 rotation=(math.radians(90.0), 0.0, 0.0))
                wall_object_c = bpy.context.selected_objects[0]
                wall_object_c.name = "wall_c"
                if wall_object_c.data.materials:
                    wall_object_c.data.materials[0] = material_background
                wall_object_c.data.materials.append(material_background)

                bpy.ops.mesh.primitive_plane_add(size=ground_plane_size, location=(
                    center_point[0] - ground_plane_size * 0.5, center_point[1], ground_plane_size * 0.5),
                                                 rotation=(0.0, math.radians(90.0), 0.0))
                wall_object_d = bpy.context.selected_objects[0]
                wall_object_d.name = "wall_d"
                if wall_object_d.data.materials:
                    wall_object_d.data.materials[0] = material_background
                wall_object_d.data.materials.append(material_background)
                # End create 4 walls

                # Start lighting initialization

                num_lights = random.randint(config_user_light_count_min, config_user_light_count_max)

                if config_user_light_count_auto:
                    num_lights = int(ground_plane_size / 0.5)
                    if num_lights == 0:
                        num_lights = 1

                # Start write to log file
                log_message = "Set num of lights: " + str(num_lights)
                print_to_log(config_sys_render_log_path, config_sys_render_log_filename, log_message,
                             config_sys_render_log_verbose)
                # End write to log file

                # num_lights = random.randint(1, 12)

                # Loop to add the lights
                for i in range(num_lights):
                    # Define a range for the random position of the lights
                    x_range = random.uniform(true_center_x - ground_plane_size / 2.0,
                                             true_center_x + ground_plane_size / 2.0)
                    y_range = random.uniform(true_center_y - ground_plane_size / 2.0,
                                             true_center_y + ground_plane_size / 2.0)
                    z_range = random.uniform(ground_plane_size, ground_plane_size)

                    # Create a new light
                    light = bpy.data.lights.new(name="point_light_" + str(i + 1), type='AREA')

                    light.size = 0.3

                    # Set the light's energy
                    light.energy = random.uniform(config_user_light_energy_min, config_user_light_energy_max)

                    # Set the light's color
                    light_color_red = random.uniform(config_user_min_light_color_red / 255.0,
                                                     config_user_max_light_color_red / 255.0)
                    light_color_green = random.uniform(config_user_min_light_color_green / 255.0,
                                                       config_user_max_light_color_green / 255.0)
                    light_color_blue = random.uniform(config_user_min_light_color_blue / 255.0,
                                                      config_user_max_light_color_blue / 255.0)

                    if config_user_background_texture_type == 1 or config_user_objects_texture_type == 5:
                        light.color = (0.5, 0.5, 0.5)
                    else:
                        light.color = (light_color_red, light_color_green, light_color_blue)

                    # Create an empty object to hold the light
                    obj = bpy.data.objects.new(name="point_light_" + str(i + 1), object_data=light)

                    # Set the object's location
                    obj.location = (x_range, y_range, z_range)

                    # Add the object to the scene
                    bpy.context.collection.objects.link(obj)

                    # Start write to log file
                    log_message = "Set lights #" + str(i) + ": " + "location: " + str(obj.location) + " energy: " + str(
                        light.energy) + " color: " + str(light.color)
                    print_to_log(config_sys_render_log_path, config_sys_render_log_filename, log_message,
                                 config_sys_render_log_verbose)
                    # End write to log file

                # End lighting initalization

                # Start save bounding box
                scene = bpy.context.scene
                camera = bpy.data.objects['Camera']

                bb_time = time.time()
                #
                object_bboxes = make_bbox(scene, camera, names2labels, object_labels, config_user_faster_bboxes)

                print(object_bboxes)

                print("BBox time: " + str(time.time() - bb_time))

                save_bbox(object_bboxes, config_sys_render_label_path, config_sys_render_label_filename)
                # End save bounding box

                # Start setup segmentation nodes
                if config_user_enable_segmentations:
                    enable_compositing(config_sys_render_segmentation_path, filename)
                    # End setup segmentation nodes

                bpy.data.scenes["Scene"].cycles.max_bounces = 32
                bpy.data.scenes["Scene"].cycles.samples = config_sys_render_engine_samples_max
                bpy.data.scenes["Scene"].cycles.use_auto_tile = True
                bpy.data.scenes["Scene"].cycles.tile_size = 2048

                bpy.context.scene.render.resolution_percentage = 100
                bpy.context.scene.render.image_settings.file_format = config_user_render_image_format  # Set the output file format
                bpy.context.scene.render.filepath = os.path.join(config_sys_render_output_path,
                                                                 config_sys_render_output_filename + "." + config_user_render_image_format)  # Set the output file path
                bpy.ops.render.render(write_still=True)  # Render the image
                # End rendering image

                # Start write to log file
                log_message = "Rendered image to path: " + str(
                    config_sys_render_output_path) + " filename: " + config_sys_render_output_filename
                print_to_log(config_sys_render_log_path, config_sys_render_log_filename, log_message,
                             config_sys_render_log_verbose)
                # End write to log file

                if config_user_bbox_imgs:
                    img_path = os.path.join(config_sys_render_output_path,
                                            config_sys_render_output_filename + "." + config_user_render_image_format)
                    bbox_path = os.path.join(config_sys_render_label_path, config_sys_render_label_filename)
                    bbox_img_path = os.path.join(config_sys_render_bbox_path, config_sys_render_bbox_filename)

                    save_bbox_image(img_path, bbox_path, bbox_img_path, bbox_img_labels)

                if config_enable_blender_save:
                    bpy.ops.wm.save_as_mainfile(
                        filepath=os.path.join(config_sys_blender_output_path, config_sys_render_blender_filename))
                # End timing
                end = time.time()

                # Start write to log file
                log_message = "Time passed: " + str(end - start)
                print_to_log(config_sys_render_log_path, config_sys_render_log_filename, log_message,
                             config_sys_render_log_verbose)
                # End write to log file

                # Progress string for tqdm
                print("PROGRESS")

                # Filename string for the generator object to keep track of generated images in case of restart.
                print("FILENAME:" + str(filename))

                # Remove rendered filename from files to be rendered.
                filenames.remove(filename)
            except Exception as e:

                # Start write to log file
                log_message = "Exception Occured: " + str(e)
                print(traceback.format_exc())
                print_to_log(config_sys_render_log_path, config_sys_render_log_filename, log_message,
                             config_sys_render_log_verbose)

        if len(filenames) != 0:
            print("Files left to render!" + str(filenames))

    print("GENERATION_SUCCESSFUL")
    bpy.ops.wm.quit_blender()
