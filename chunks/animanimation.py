from .content import Content
from .framelist import FrameList
from ..containers.vector3d import Vector3d
from ..containers.quat import Quat
from ..containers.keyframe import Keyframe
import bpy
from mathutils import Quaternion, Matrix, Vector
from collections import defaultdict
from struct import pack, unpack
    
class AnimAnimation(Content):

    TYPE_NORMAL = 1
    TYPE_COMPRESSED = 2
    DEFAULT_FPS = 30
    ID_STAMP = 0x0000001B

    def __init__(self, header):
        super().__init__(header)
        self.type = 0
        self.number_of_frames = 0
        self.duration = 0
        self.keyframes = []
        self.compression_range = {}

    def read(self, file):
        super().read(file)
        const, self.type, self.number_of_frames, flags, self.duration = unpack("IIIIf", self.content[:20])

        pointer = 20
        keyframe_size = Keyframe.KEYFRAME_SIZE_COMPRESSED if (self.type == AnimAnimation.TYPE_COMPRESSED) else Keyframe.KEYFRAME_SIZE_NORMAL
        for _ in range(self.number_of_frames):
            keyframe = Keyframe()
            keyframe.read(self.content[pointer:pointer+keyframe_size], self.type == AnimAnimation.TYPE_COMPRESSED)
            self.keyframes.append(keyframe)
            pointer += keyframe_size

        if self.type == AnimAnimation.TYPE_COMPRESSED:
            compression_range = unpack("6f", self.content[pointer:pointer+24])
            self.compression_range = {"Base": Vector(compression_range[:3]), "Offset": Vector(compression_range[3:])}

        bone_counter = 0
        for keyframe in self.keyframes:
            prev_keyframe = keyframe.prev_keyframe_index
            if 0 <= prev_keyframe < len(self.keyframes):
                bone_index = self.keyframes[prev_keyframe].bone_index
            else:
                bone_index = bone_counter
                bone_counter += 1
            keyframe.bone_index = bone_index

    def build(self, root=None, name=""):

        # Get armature object - if none is selected, take the first one
        if bpy.context.object is not None and bpy.context.object.type == 'ARMATURE':
            armature = bpy.context.object
        else:
            for armature in bpy.data.objects:
                if armature.data == bpy.data.armatures[0]:
                    break

        if root is None:
            root = armature.pose.bones[0].name

        action = bpy.data.actions.new(name if name != "" else root)
        if armature.animation_data is None:
            armature.animation_data_create()
        armature.animation_data.action = action

        bone_order = [root] + [child.name for child in armature.pose.bones[root].children_recursive]
        bone_order = sorted(bone_order, key = lambda x: armature.pose.bones.find(x))

        fps = AnimAnimation.DEFAULT_FPS
        scene = bpy.data.scenes[0]
        scene.render.fps = fps
        scene.frame_end = scene.frame_start + int(self.duration*fps)

        permutation = Matrix.Identity(4)
        if "Local Space" in armature:
            permutation = FrameList.LOCAL_MATRIX[armature["Local Space"]].to_4x4()

        for keyframe in self.keyframes:
            frame = scene.frame_start + keyframe.time * fps
            bone_index = bone_order[keyframe.bone_index]
            pose_bone = armature.pose.bones[bone_index]
            rest_bone = pose_bone.bone

            location = Vector(keyframe.location.as_tuple())
            rotation = Quaternion(keyframe.rotation.as_tuple()).to_matrix().to_4x4()

            if self.type == AnimAnimation.TYPE_COMPRESSED:
                location = self.compression_range["Base"] + location * self.compression_range["Offset"]

            parent_rotation = Matrix.Identity(4) @ permutation.inverted()
            if rest_bone.parent is not None:
                parent_rotation = rest_bone.parent.matrix_local

            parent_rotation = parent_rotation @ permutation
            rotation = (parent_rotation @ rotation) @ permutation.inverted()
            rotation = rest_bone.matrix_local.inverted() @ rotation
            rotation = rotation.to_quaternion()

            location = rest_bone.matrix_local.inverted() @ (parent_rotation @ location)

            pose_bone.matrix_basis = Matrix.LocRotScale(location, rotation, (1, 1, 1))
            pose_bone.keyframe_insert(data_path="rotation_quaternion", frame=frame)
            pose_bone.keyframe_insert(data_path="location", frame=frame)

        for fcurve in action.layers[0].strips[0].channelbags[0].fcurves:
            for keyframe_point in fcurve.keyframe_points:
                keyframe_point.interpolation = "LINEAR"


    def load(self, root=None):

        # Get armature object - if none is selected, take the first one
        if bpy.context.object is not None and bpy.context.object.type == 'ARMATURE':
            armature = bpy.context.object
        else:
            for armature in bpy.data.objects:
                if armature.data == bpy.data.armatures[0]:
                    break

        self.type = AnimAnimation.TYPE_NORMAL
        if "Update Locals" in armature and armature["Update Locals"]:
            self.type = AnimAnimation.TYPE_COMPRESSED

        if root is None:
            action_name = armature.animation_data.action.name
            if action_name in armature.pose.bones:
                root = action_name
            else:
                root = armature.pose.bones[0].name

        bones = {child.name for child in armature.pose.bones[root].children_recursive}
        bones.add(root)
        
        fcurves = armature.animation_data.action.layers[0].strips[0].channelbags[0].fcurves

        # Little hack to reconstruct the data path in the fcurves
        base_path = repr(armature) + "."

        keyframes = defaultdict(lambda: defaultdict(lambda: {"location": [0, 0, 0,], "rotation": [1, 0, 0, 0]}))
        for fcurve in fcurves:
            data_path_split = fcurve.data_path.split(".")
            bone_name = eval(base_path + ".".join(data_path_split[:-1])).name
            if bone_name in bones:
                for keyframe_point in fcurve.keyframe_points:
                    time, value = keyframe_point.co
                    if data_path_split[-1] == "rotation_quaternion":
                        keyframes[bone_name][time]["rotation"][fcurve.array_index] = value
                    elif data_path_split[-1] == "location":
                        keyframes[bone_name][time]["location"][fcurve.array_index] = value

        # Bring keyframes in the correct order:
        # 1. Sort by time (bone order irrelevant)
        # 2. Sort by time of the previous keyframe and secondarily by bone index
        keyframe_previous_time = {bone: -1 for bone in bones}
        keyframes = [[bone, time, keyframe] for bone, frame in keyframes.items() for time, keyframe in frame.items()]
        keyframes.sort(key = lambda x: x[1])

        for keyframe in keyframes:
            keyframe.append(keyframe_previous_time[keyframe[0]])
            keyframe_previous_time[keyframe[0]] = keyframe[1]

        keyframes.sort(key = lambda x: (x[3], armature.pose.bones.find(x[0]), x[1]))

        permutation = Matrix.Identity(4)
        if "Local Space" in armature:
            permutation = FrameList.LOCAL_MATRIX[armature["Local Space"]].to_4x4()

        if self.type == AnimAnimation.TYPE_COMPRESSED:
            compression_range = {"Min": [0, 0, 0], "Max": [0, 0, 0]}

        prev_keyframes = {bone: -1 for bone in bones}
        scene = bpy.data.scenes[0]
        for keyframe in keyframes:
            bone_name = keyframe[0]
            pose_bone = armature.pose.bones[bone_name]
            rest_bone = pose_bone.bone
            time = (keyframe[1] - scene.frame_start)/scene.render.fps

            location = Vector(keyframe[2]["location"])
            rotation = Quaternion(keyframe[2]["rotation"]).to_matrix().to_4x4()

            parent_rotation = Matrix.Identity(4) @ permutation.inverted()
            if rest_bone.parent is not None:
                parent_rotation = rest_bone.parent.matrix_local

            parent_rotation = parent_rotation @ permutation

            rotation = rest_bone.matrix_local @ rotation
            rotation = parent_rotation.inverted() @ (rotation @ permutation)
            rotation = rotation.to_quaternion()

            location = parent_rotation.inverted() @ (rest_bone.matrix_local @ location)

            self.keyframes.append(Keyframe(bone_name, time, Vector3d(*location), Quat(rotation[1], rotation[2], rotation[3], rotation[0]), prev_keyframes[bone_name]))
            prev_keyframes[bone_name] = len(self.keyframes) - 1

            if self.type == AnimAnimation.TYPE_COMPRESSED:
                for index, (current_min, current_value) in enumerate(zip(compression_range["Min"], location)):
                    if current_value < current_min:
                        compression_range["Min"][index] = current_value
                for index, (current_max, current_value) in enumerate(zip(compression_range["Max"], location)):
                    if current_value > current_max:
                        compression_range["Max"][index] = current_value

        self.duration = (scene.frame_end - scene.frame_start)/scene.render.fps

        if self.type == AnimAnimation.TYPE_COMPRESSED:
            base = (Vector(compression_range["Min"]) + Vector(compression_range["Max"])) / 2
            offset = (Vector(compression_range["Max"]) - Vector(compression_range["Min"])) / 2
            self.compression_range = {"Base": base, "Offset": offset}

        self.number_of_frames = len(self.keyframes)

        # Issue Warning when wrong FPS is set
        if scene.render.fps != AnimAnimation.DEFAULT_FPS:
            return True
        else:
            return False

    def write(self):

        content = b""
        for keyframe in self.keyframes:
            if self.type == AnimAnimation.TYPE_COMPRESSED:
                content += keyframe.write(self.compression_range)
            else:
                content += keyframe.write()

        if self.type == AnimAnimation.TYPE_COMPRESSED:
            content += pack("6f", *self.compression_range["Base"], *self.compression_range["Offset"])
        header = pack("IIIIf", 256, self.type, self.number_of_frames, 0, self.duration)
        content = header + content
        self.header.chunk_size = len(content)
        content = self.header.write() + content

        return content