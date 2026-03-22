import bpy
from bpy_extras.io_utils import ImportHelper, ExportHelper
from re import match

from .chunks.clump import Clump
from .chunks.animanimation import AnimAnimation
from .containers.header import Header

from .chunks import Container
from .chunks import Texture

bl_info = {
    "name": "RenderWare importer/exporter for Settlers HoK/RoaE (.dff/.anm)",
    "author": "fritz_98",
    "version": (0, 0, 1),
    # "location": "File > Import-Export > Renderware Model (.dff)",
    "description": "RenderWare model and animation importer/exporter for Settlers HoK/RoaE",
    "category": "Import-Export"
}



def read_anm_file(context, filepath):
    file = open(filepath, "rb")
    
    header = Header()
    header.read(file)
    assert (header.chunk_id_stamp == AnimAnimation.ID_STAMP), "Top level Chunk must be of type Anim Animation"

    anim = AnimAnimation(header)
    anim.read(file)

    file.close()

    return anim

def write_anm_file(context, anim, filepath):
    file = open(filepath, "wb")
    string = anim.write()
    file.write(string)
    file.close()

def read_dff_file(context, filepath):
    bpy.ops.outliner.orphans_purge()

    file = open(filepath, "rb")
    
    header = Header()
    header.read(file)
    # assert (header.get_dff_version() == 0x37002), "This script is intended for Renderware Version 3.7.0.2 only"
    assert (header.chunk_id_stamp == Clump.ID_STAMP), "Top level Chunk must be of type Clump"

    clump = Clump(header)
    clump.read(file)

    file.close()

    return clump

def write_dff_file(context, clump, filepath):
    file = open(filepath, "wb")
    string = clump.write()
    file.write(string)
    file.close()

class ImportANM(bpy.types.Operator, ImportHelper):
    """Import class for Renderware ANM files (Settlers HoK/RoaE)"""
    bl_label = "Import RW ANM File"
    bl_idname = "import_animation.anm"
    bl_description = "Import class for Renderware ANM files (Settlers HoK/RoaE)"

    filename_ext = ".anm"

    filter_glob: bpy.props.StringProperty(default="*.anm", options={'HIDDEN'}, maxlen=255)
    
    def execute(self, context):
        anim = read_anm_file(context, self.filepath)
        m = match(r".*_(?P<bone_id>\d+)\.anm", self.filepath)
        root = None
        name = ""
        if m is not None:
            root = m.group("bone_id")
            name = root
        else:
            m = match(r".*_(?P<anim_name>\w+)\.anm", self.filepath)
            if m is not None:
                name = m.group("anim_name")
        anim.build(root=root, name=name)
        return {"FINISHED"}
    
class ExportANM(bpy.types.Operator, ExportHelper):
    """Export class for Renderware ANM files (Settlers HoK/RoaE)"""
    bl_label = "Export RW ANM File"
    bl_idname = "export_animation.anm"
    bl_description = "Export class for Renderware ANM files (Settlers HoK/RoaE)"

    filename_ext = ".anm"

    filter_glob: bpy.props.StringProperty(default="*.anm", options={'HIDDEN'}, maxlen=255)
    
    def execute(self, context):
        anim = AnimAnimation(Header())
        m = match(r".*_(?P<bone_id>\d+)\.anm", self.filepath)
        root = None
        if m is not None:
            root = m.group("bone_id")
        if anim.fetch(root):
            self.report({'WARNING'}, "FPS should be 30. Export results might differ from 3d view")
        write_anm_file(context, anim, self.filepath)
        return {"FINISHED"}
    
    def invoke(self, context, _event):
        import os
        if not self.filepath:
            blend_filepath = context.blend_data.filepath
            if not blend_filepath:
                # Get armature object - if none is selected, take the first one
                if bpy.context.object is not None and bpy.context.object.type == 'ARMATURE':
                    armature = bpy.context.object
                else:
                    for armature in bpy.data.objects:
                        if armature.data == bpy.data.armatures[0]:
                            break
                blend_filepath = "untitled_" + armature.animation_data.action.name
            else:
                blend_filepath = os.path.splitext(blend_filepath)[0]

            self.filepath = blend_filepath + self.filename_ext

        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class ImportDFF(bpy.types.Operator, ImportHelper):
    """Import class for Renderware 3.7.0.2 DFF files (Settlers HoK/RoaE)"""
    bl_label = "Import RW DFF File"
    bl_idname = "import_model.dff"
    bl_description = "Import class for Renderware 3.7.0.2 DFF files (Settlers HoK/RoaE)"

    filename_ext = ".dff"

    filter_glob: bpy.props.StringProperty(default="*.dff", options={'HIDDEN'}, maxlen=255)

    # List of operator properties, the attributes will be assigned
    # to the class instance from the operator settings before calling.
    import_geometries: bpy.props.BoolProperty(
        name="Import Geometries",
        description="Import all geometries included",
        default=True,
    )

    import_frames: bpy.props.BoolProperty(
        name="Import Frames",
        description="Import all frames included. Some geometries may be displaced if frames are not imported",
        default=True,
    )

    ignore_unknown_chunks: bpy.props.BoolProperty(
        name="Ignore unknown chunks",
        description="Ignore chunk types for which there is no import/export module",
        default=False,
    )
    
    def execute(self, context):
        Texture.TEXTURE_PATH = context.preferences.addons[__package__].preferences.texture_path
        Container.IGNORE_UNKNOWN_CHUNKS = self.ignore_unknown_chunks

        clump = read_dff_file(context, self.filepath)
        clump.build(self.import_geometries, self.import_frames)
        return {"FINISHED"}
    
class ExportDFF(bpy.types.Operator, ExportHelper):
    """Export class for Renderware 3.7.0.2 DFF files (Settlers HoK/RoaE)"""
    bl_label = "Export RW DFF File"
    bl_idname = "export_model.dff"
    bl_description = "Export class for Renderware 3.7.0.2 DFF files (Settlers HoK/RoaE)"

    filename_ext = ".dff"

    filter_glob: bpy.props.StringProperty(default="*.dff", options={'HIDDEN'}, maxlen=255)
    
    def execute(self, context):
        clump = Clump(Header())
        clump.fetch()
        write_dff_file(context, clump, self.filepath)
        return {"FINISHED"}

class ImportDFFPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    texture_path: bpy.props.StringProperty(
        # default = "",
        default = "C:\\Spiele\\theSettlers5\\base\\shr\\graphics\\Textures\\",
        name = "Texture file path",
        description = "Path to Texures for imported models",
        subtype = 'FILE_PATH'
    )

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.prop(self, "texture_path", text="Path to Texures")

# Only needed if you want to add into a dynamic menu
def menu_func_import(self, context):
    self.layout.operator(ImportDFF.bl_idname, text="Renderware Model (.dff)")
    self.layout.operator(ImportANM.bl_idname, text="Renderware Animation (.anm)")

def menu_func_export(self, context):
    self.layout.operator(ExportDFF.bl_idname, text="Renderware Model (.dff)")
    self.layout.operator(ExportANM.bl_idname, text="Renderware Animation (.anm)")

# Register and add to the "file selector" menu (required to use F3 search "Text Import Operator" for quick access)
def register():
    bpy.utils.register_class(ImportDFF)
    bpy.utils.register_class(ImportDFFPreferences)
    bpy.utils.register_class(ImportANM)
    bpy.utils.register_class(ExportDFF)
    bpy.utils.register_class(ExportANM)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

def unregister():
    bpy.utils.unregister_class(ImportDFF)
    bpy.utils.unregister_class(ImportDFFPreferences)
    bpy.utils.unregister_class(ImportANM)
    bpy.utils.unregister_class(ExportDFF)
    bpy.utils.unregister_class(ExportANM)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)