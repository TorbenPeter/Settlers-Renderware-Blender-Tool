from .content import Content
from .framelist import FrameList
from ..containers.keyframe import Keyframe
from ..containers.uvkeyframe import UVKeyframe
from ..util import get_current_armature, display
import bpy
from mathutils import Quaternion, Matrix, Vector
from collections import defaultdict
from struct import pack, unpack
    
class AnimAnimation(Content):

    TYPE_NORMAL = 1
    TYPE_COMPRESSED = 2
    TYPE_LINEAR = 448
    TYPE_PARAM = 449
    DEFAULT_FPS = 30

    ID_STAMP = 0x0000001B

    def __init__(self, header):
        super().__init__(header)
        self.type = 0
        self.number_of_frames = 0
        self.duration = 0
        self.keyframes = []
        self.compression_range = {}
        self.name = ""
        self.node_uv_channels = []

    
    def is_uv_anim(self):
        return self.type == AnimAnimation.TYPE_LINEAR or self.type == AnimAnimation.TYPE_PARAM


    def read(self, file):
        super().read(file)

        const, self.type, self.number_of_frames, flags, self.duration = unpack("IIIIf", self.content[:20])

        # With ugly definitions come ugly implementations
        if self.is_uv_anim():
            self.read_uv()
            return

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

    def read_uv(self):

        # TODO
        if self.type == AnimAnimation.TYPE_LINEAR:
            Exception("Linear UV Animations are not implemented at this time")

        pointer = 24
        self.name = self.content[pointer:pointer+32].decode("latin_1").strip("\0")
        pointer += 32
        self.node_uv_channels = list(unpack("8i", self.content[pointer:pointer+32]))
        pointer += 32

        for _ in range(self.number_of_frames):
            keyframe = UVKeyframe(self.type == AnimAnimation.TYPE_LINEAR)
            keyframe.read(self.content[pointer:pointer+UVKeyframe.KEYFRAME_SIZE])
            self.keyframes.append(keyframe)
            pointer += UVKeyframe.KEYFRAME_SIZE

        node_counter = 0
        for keyframe in self.keyframes:
            prev_keyframe = keyframe.keyframe_index
            if 0 <= prev_keyframe < len(self.keyframes):
                node_index = self.keyframes[prev_keyframe].node_index
            else:
                node_index = node_counter
                node_counter += 1
            keyframe.node_index = node_index


    def build(self, root=None, name=""):

        if self.is_uv_anim():
            self.build_uv()
            return

        armature = get_current_armature()
        if armature is None or len(armature.pose.bones) == 0:
            return

        if root is None:
            root = armature.pose.bones[0].name

        action = bpy.data.actions.new(name if name != "" else root)
        if armature.animation_data is None:
            armature.animation_data_create()
        armature.animation_data.action = action

        bone_order = [root] + [child.name for child in armature.pose.bones[root].children_recursive if not child.hide]
        bone_order = sorted(bone_order, key = lambda x: armature.pose.bones.find(x))

        fps = AnimAnimation.DEFAULT_FPS
        scene = bpy.data.scenes[0]
        if bpy.context.scene is not None:
            scene = bpy.context.scene
        scene.render.fps = fps

        permutation = Matrix.Identity(4)
        if "Local Space" in armature:
            permutation = FrameList.LOCAL_MATRIX[armature["Local Space"]]

        for keyframe in self.keyframes:
            frame = scene.frame_start + keyframe.time * fps
            bone_index = bone_order[keyframe.bone_index]
            pose_bone = armature.pose.bones[bone_index]
            rest_bone = pose_bone.bone

            location = keyframe.location
            rotation = keyframe.rotation.to_matrix().to_4x4()

            if self.type == AnimAnimation.TYPE_COMPRESSED:
                location = self.compression_range["Base"] + location * self.compression_range["Offset"]

            parent_rotation = Matrix.Identity(4) @ permutation
            if rest_bone.parent is not None:
                parent_rotation = rest_bone.parent.matrix_local

            parent_rotation = parent_rotation @ permutation.inverted()
            rotation = (parent_rotation @ rotation) @ permutation
            rotation = rest_bone.matrix_local.inverted() @ rotation
            rotation = rotation.to_quaternion()

            location = rest_bone.matrix_local.inverted() @ (parent_rotation @ location)

            pose_bone.matrix_basis = Matrix.LocRotScale(location, rotation, None)
            pose_bone.keyframe_insert(data_path="rotation_quaternion", frame=frame)
            pose_bone.keyframe_insert(data_path="location", frame=frame)

        for fcurve in action.layers[0].strips[0].channelbags[0].fcurves:
            for keyframe_point in fcurve.keyframe_points:
                keyframe_point.interpolation = "LINEAR"

    def build_uv(self):

        fps = AnimAnimation.DEFAULT_FPS
        scene = bpy.data.scenes[0]
        if bpy.context.scene is not None:
            scene = bpy.context.scene
        scene.render.fps = fps

        for material in bpy.data.materials:
            if "UV Animations" in material and self.name in material["UV Animations"]:
                action = bpy.data.actions.new(self.name)
                node_tree = material.node_tree

                if node_tree.animation_data is None:
                    node_tree.animation_data_create()
                node_tree.animation_data.action = action

                uv_links = {}
                uv_transforms = {}
                for node in node_tree.nodes:
                    if node.type == "UVMAP" and node.outputs["UV"].is_linked:
                        uv_transforms[len(uv_transforms)] = [link.to_node for link in node.outputs["UV"].links if link.to_node.type == "MAPPING"]
                        uv_links[len(uv_links)] = [[link.from_socket, link.to_socket] for link in node.outputs["UV"].links]

                for keyframe in self.keyframes:

                    uv_channel = self.node_uv_channels[keyframe.node_index]

                    if uv_channel not in uv_transforms or uv_channel not in uv_links:
                        continue

                    frame = scene.frame_start + keyframe.time * fps

                    # Make sure mapping nodes exist
                    transforms = uv_transforms[uv_channel]
                    links = uv_links[uv_channel]
                    for link in links:
                        if link[1].node not in transforms:
                            transform = node_tree.nodes.new("ShaderNodeMapping")
                            transform.name = self.name
                            transform.label = self.name
                            transform.vector_type = "POINT"
                            node_tree.links.new(transform.inputs["Vector"], link[0])
                            node_tree.links.new(link[1], transform.outputs["Vector"])
                            transforms.append(transform)
                            link[1] = transform.inputs["Vector"]

                    for transform in transforms:
                        transform.inputs["Location"].default_value[0] = keyframe.position[1]
                        transform.inputs["Location"].default_value[1] = -keyframe.position[2]
                        transform.inputs["Location"].keyframe_insert(data_path="default_value", frame=frame)

                        transform.inputs["Scale"].default_value[0] = keyframe.scale[1]
                        transform.inputs["Scale"].default_value[1] = keyframe.scale[2]
                        transform.inputs["Scale"].keyframe_insert(data_path="default_value", frame=frame)

                        transform.inputs["Rotation"].default_value[1] = keyframe.position[0]
                        transform.inputs["Rotation"].default_value[2] = keyframe.scale[0]
                        transform.inputs["Rotation"].keyframe_insert(data_path="default_value", frame=frame)

                for fcurve in action.layers[0].strips[0].channelbags[0].fcurves:
                    for keyframe_point in fcurve.keyframe_points:
                        keyframe_point.interpolation = "LINEAR"


    def fetch(self, root=None):

        armature = get_current_armature()
        if armature is None or len(armature.pose.bones) == 0:
            return

        self.type = AnimAnimation.TYPE_NORMAL
        if "Update Locals" in armature and armature["Update Locals"]:
            self.type = AnimAnimation.TYPE_COMPRESSED

        if root is None:
            action_name = armature.animation_data.action.name
            if action_name in armature.pose.bones:
                root = action_name
            else:
                root = armature.pose.bones[0].name

        bones = {child.name for child in armature.pose.bones[root].children_recursive if not child.hide}
        bones.add(root)
        
        fcurves = armature.animation_data.action.layers[0].strips[0].channelbags[0].fcurves
        scene = bpy.data.scenes[0]
        if bpy.context.scene is not None:
            scene = bpy.context.scene

        # Little hack to reconstruct the data path in the fcurves
        base_path = repr(armature) + "."

        keyframes = defaultdict(lambda: defaultdict(lambda: {"location": [0, 0, 0], "rotation": [1, 0, 0, 0]}))
        for fcurve in fcurves:
            data_path_split = fcurve.data_path.split(".")
            # Never blindly eval!
            # Keyframed bone might've been deleted
            try:
                bone = eval(base_path + ".".join(data_path_split[:-1]))
            except:
                continue
            bone_name = bone.name
            if bone_name not in bones:
                continue

            for keyframe_point in fcurve.keyframe_points:
                time, value = keyframe_point.co

                # Ignore all keyframes outside the current scene time frame
                if time < scene.frame_start or time > scene.frame_end:
                    continue

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
            permutation = FrameList.LOCAL_MATRIX[armature["Local Space"]]

        if self.type == AnimAnimation.TYPE_COMPRESSED:
            compression_range = {"Min": [0, 0, 0], "Max": [0, 0, 0]}

        prev_keyframes = {bone: -1 for bone in bones}
        for keyframe in keyframes:
            bone_name = keyframe[0]
            pose_bone = armature.pose.bones[bone_name]
            rest_bone = pose_bone.bone

            time = (keyframe[1] - scene.frame_start)
            if time > 0:
                time = (time + 1e-6)/scene.render.fps

            location = Vector(keyframe[2]["location"])
            rotation = Quaternion(keyframe[2]["rotation"]).to_matrix().to_4x4()

            parent_rotation = Matrix.Identity(4) @ permutation
            if rest_bone.parent is not None:
                parent_rotation = rest_bone.parent.matrix_local

            parent_rotation = parent_rotation @ permutation.inverted()

            rotation = rest_bone.matrix_local @ rotation
            rotation = parent_rotation.inverted() @ (rotation @ permutation.inverted())
            rotation = rotation.to_quaternion()

            location = parent_rotation.inverted() @ (rest_bone.matrix_local @ location)

            self.keyframes.append(Keyframe(bone_name, time, location, rotation, prev_keyframes[bone_name]))
            prev_keyframes[bone_name] = len(self.keyframes) - 1

            if self.type == AnimAnimation.TYPE_COMPRESSED:
                for index, (current_min, current_value) in enumerate(zip(compression_range["Min"], location)):
                    if current_value < current_min:
                        compression_range["Min"][index] = current_value
                for index, (current_max, current_value) in enumerate(zip(compression_range["Max"], location)):
                    if current_value > current_max:
                        compression_range["Max"][index] = current_value

        self.duration = (scene.frame_end - scene.frame_start + 1e-6)/scene.render.fps

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
        
    def fetch_uv(self, material, name):
        self.name = name
        self.node_uv_channels = [0]*8
        self.type = AnimAnimation.TYPE_PARAM

        node_tree = material.node_tree
        if node_tree.animation_data is None or node_tree.animation_data.action is None:
            return

        fcurves = node_tree.animation_data.action.layers[0].strips[0].channelbags[0].fcurves
        scene = bpy.data.scenes[0]
        if bpy.context.scene is not None:
            scene = bpy.context.scene

        uv_links = [node.outputs["UV"].links[0].to_node for node in node_tree.nodes if node.type == "UVMAP" and node.outputs["UV"].is_linked]
        for i in range(len(uv_links)):
            self.node_uv_channels[i] = i

        base_path = repr(node_tree) + "."
        keyframes = defaultdict(lambda: defaultdict(lambda: {"Location": [0, 0, 0], "Rotation": [0, 0, 0], "Scale": [1, 1, 1]}))
        for fcurve in fcurves:
            data_path_split = fcurve.data_path.split(".")
            try:
                input = eval(base_path + ".".join(data_path_split[:-1]))
                node = input.node
            except:
                continue
            if node.type != "MAPPING":
                continue
            if node not in uv_links:
                continue

            for keyframe_point in fcurve.keyframe_points:
                time, value = keyframe_point.co

                if time < scene.frame_start or time > scene.frame_end:
                    continue

                keyframes[node][time][input.name][fcurve.array_index] = value

        keyframe_previous_time = {uv_links.index(node): -1 for node in keyframes.keys()}
        keyframe_index = {uv_links.index(node): -1 for node in keyframes.keys()}
        keyframes = [[uv_links.index(node), time, keyframe] for node, frame in keyframes.items() for time, keyframe in frame.items()]
        keyframes.sort(key = lambda x: x[1])

        for keyframe in keyframes:
            keyframe.append(keyframe_previous_time[keyframe[0]])
            keyframe_previous_time[keyframe[0]] = keyframe[1]

        keyframes.sort(key = lambda x: (x[3], x[0], x[1]))
        
        for keyframe in keyframes:
            node = keyframe[0]
            time = (keyframe[1] - scene.frame_start)/scene.render.fps
            keys = keyframe[2]
            scale = Vector((0, 1, 1))
            position = Vector((0, 0, 0))

            scale[0] = keys["Rotation"][2]
            scale[1] = keys["Scale"][0]
            scale[2] = keys["Scale"][1]

            position[0] = keys["Rotation"][1]
            position[1] = keys["Location"][0]
            position[2] = -keys["Location"][1]

            self.keyframes.append(UVKeyframe(False, node, time, scale, position, keyframe_index[node]))
            keyframe_index[node] = len(self.keyframes) - 1

        self.duration = (scene.frame_end - scene.frame_start)/scene.render.fps
        self.number_of_frames = len(self.keyframes)

        if scene.render.fps != AnimAnimation.DEFAULT_FPS:
            bpy.context.window_manager.popup_menu(display("FPS should be 30. Export results might differ from 3d view"), title="Warning", icon='ERROR')


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
        return self.header.write() + content
    
    def write_uv(self):
        content = b""
        content += pack("IIIIfI", 256, self.type, self.number_of_frames, 0, self.duration, 0)

        name = self.name + "\0"*(32 - len(self.name))
        content += name.encode("utf-8")
        content += pack("8I", *self.node_uv_channels)

        for keyframe in self.keyframes:
            content += keyframe.write()

        self.header.chunk_size = len(content)
        return self.header.write() + content