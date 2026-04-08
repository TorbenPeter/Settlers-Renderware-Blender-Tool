from .content import Content
from .animanimation import AnimAnimation
from ..containers.morphtarget import MorphTarget
from struct import pack, unpack
import bpy

class MorphPLG(Content):

    # Blender puts all shape keys automatically 10 frames apart
    DEFAULT_MORPH_DURATION = 10.0
    ID_STAMP = 0x00000105

    def __init__(self, header):
        super().__init__(header)
        self.number_of_morph_targets = 0
        self.morph_targets = []

    def read(self, file):
        super().read(file)
        self.number_of_morph_targets, = unpack("I", self.content[:4])
        pointer = 4
        for _ in range(self.number_of_morph_targets):
            morph_target = MorphTarget()
            morph_target.read(self.content[pointer:pointer+20])
            pointer += 20
            self.morph_targets.append(morph_target)


    def build(self, object):

        shape_keys = object.data.shape_keys

        action = bpy.data.actions.new(object.data.name + "MorphAnim")
        if shape_keys.animation_data is None:
            shape_keys.animation_data_create()
        shape_keys.animation_data.action = action

        fps = AnimAnimation.DEFAULT_FPS
        scene = bpy.data.scenes[0]
        scene.render.fps = fps
        shape_keys.eval_time = 0.0
        shape_keys.keyframe_insert("eval_time", frame=scene.frame_start)
        morph_target_index = 0
        for _ in range(self.number_of_morph_targets):
            morph_target = self.morph_targets[morph_target_index]
            shape_keys.eval_time += (morph_target.end - morph_target.start)*morph_target.delta_time*fps
            shape_keys.keyframe_insert("eval_time", frame=scene.frame_start + shape_keys.eval_time)
            morph_target_index = morph_target.next
            if morph_target_index == 0:
                break

        for fcurve in action.layers[0].strips[0].channelbags[0].fcurves:
            for keyframe_point in fcurve.keyframe_points:
                keyframe_point.interpolation = "LINEAR"