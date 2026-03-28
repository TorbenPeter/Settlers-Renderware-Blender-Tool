import bpy

# Little hack to display errors/warnings outside of an Operator. Do not try this at home
def display(label):
    return lambda self, context: self.layout.label(text = label)

def get_current_armature():

    armature = None

    if len(bpy.data.armatures) == 0:
        return armature

    # See if current context is an armature
    if bpy.context.object is not None and bpy.context.object.type == "ARMATURE":
        return bpy.context.object
    elif bpy.context.collection is not None:
        # If not, search the colletion in the current context
        for armature in bpy.context.collection.objects:
            if armature.type == "ARMATURE":
                break
        else:
            armature = None

    # If the above fails, take the first armature in the data
    # TODO: Technically, this could be undesired behaviour. Up for debate
    if armature is None:
        for armature in bpy.data.objects:
            if armature.data == bpy.data.armatures[0]:
                break
        else:
            armature = None

    return armature