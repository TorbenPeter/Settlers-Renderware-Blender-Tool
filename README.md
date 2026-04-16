# Settlers-Renderware-Blender-Tool

Blender Addon to edit Renderware Model and Animation Files. Mainly tailored to Settlers HoK and RoaE

## Suported Features

- Import & Export of any .dff model file as well as .anm and .uva animation files, including morph animations, fully in Python, without creating an in-between .json representation
- Import Materials as a shader editor node tree, including dual textures, specular maps and normal maps. You can set the file path for your textures in the addon properties
- Compute triangle strips for all meshes as well as skin splits for armatures with more than 58 bones
- Particle effects will only be attached as a custom property to the respective object for now

## How to use

- Zip the "io_renderware" folder and load it as an addon in Blender

## Things to look out for:

- Only one armature at a time will be exported. If your scene has multiple armatures, select the desired one
- All objects in the scene will be exported unless they are hidden
- Accordingly, hidden bones will not be exported. This can be used for IK bones that you don't want to export but keep in the scene
- Import & Export should be done in Object Mode only
- Every armature is assigned the custom properties "Local Space" and "Update Locals". Those should be left as they are to keep existing animations compatible. If those properties are not set, "False" is assumed
- Most imported models will have duplicate vertices. Those are required for proper UV Mapping in Renderware. You can usually remove those doubles as they will be restored on export. Be careful when removing doubles from thin geometries such as cloaks since they might break. Check your model integrity using the material preview
- All bones must have the following properties: Relative Parenting = False, Connected = False, Local Location = True, Inherit Rotation = True. If that is not the case, exported objects and animations might differ from the Blender view
- Interpolation mode for all keyframes should be "Linear", otherwise exported animations may look different ingame
- The framerate should be set to 30 FPS
- The order of UV Maps attached to a mesh is essential to the correct assignment to multiple textures
- In the Shader Editor, the name of an Image Texture Node determines the exported texture name. Texture images themselves are not exported
- Most buildings have static bones with a specific naming scheme (e.g. 300+ for fire effects, 600+ for animations, etc). Such bones require a "tag" custom property to properly function ingame. I recommend aligning those static bones along the Y axis
- Most building animations run on a subtree of the armature. To export an animation for such a subtree, the name of the root bone must be given in the filename (e.g. "sawmill_work_601.anm" for an animation with bones in the subtree starting at bone "601"). The root bone must be tagged
- Units from RoaE are often blue upon import. This is due to the masks that Blue Byte uses for specular effects as well as player colors. You can edit the shader node tree to temporarily disable them, however, they must be reenabled for a valid export
- For all animations, only the keyframes inside the current frame window are exported
- For UV animations, the name of the animation must be attached to the respective object as a custom property
- Unit animations usually consist of numerous keyframes. Those are most likely baked and not created by hand. Try to find actual key points and delete the rest for easier editing

## Thanks to

- mcb's Renderware/.json converter, where much of the Renderware file structure is documented: https://github.com/mcb5637/S5Converter
- The GTAmods wiki page that documents the Renderware file structure as well: https://gtamods.com/wiki/RenderWare_binary_stream_file