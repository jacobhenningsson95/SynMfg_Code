# Configuring OBJ Files for the Pipeline

The pipeline reads only `.obj` files. All files used for generation must be located within a single folder, specified 
in the [config file](../../../config-sample.json). The objects contained in these files must also be listed in the
[config file](../../../config-sample.json), with their corresponding integer labels, e.g.,
`{"L-Bracket": "0", "U-Bracket": "1", "Angle_Bracket": "2",...}`.

## Example

This system allows the same object to be included in multiple `.obj` files, which is useful for assembled objects
with different variations that consists of smaller components. 
For example, a fastened "panel" might use either a "screw" or "bolt". These would be represented in files as follows:

- `Panel_Screw.obj` containing `{Panel, Screw}`
- `Panel_bolt.obj`  containing `{Panel, Bolt}`

In total, three classes— `{"Panel":"0", "Screw":"1", "Bolt":"2"}` —would be defined under "object_label" in the
[config file](../../../config-sample.json).


## Checking and changing name of objects

The code will automatically verify if all objects in the provided `.obj` files are included in `object_label`. 
If an object is found without a corresponding label, an error will be displayed. 
Object names can be checked and adjusted using Blender.

To view the object names, import the file into Blender and look at the Outliner:

<img src="../../../Figures/obj_file_object_wrong_name.png" alt="Image 1" width="500"/>

The top name represents the object name, while the bottom shows the mesh name. 
In this example, both names are incorrect and must be changed to match the object name, "Angele_Bracket" in the default 
[config file](../../../config-sample.json). Double-click the names to edit them:

<img src="../../../Figures/obj_file_object_correct_name.png" alt="Image 1" width="500"/>
