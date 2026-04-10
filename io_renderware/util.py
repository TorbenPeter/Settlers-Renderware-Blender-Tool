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
            if not armature.hide_get() and armature.type == "ARMATURE":
                break
        else:
            armature = None

    # If the above fails, take the first armature in the data
    # TODO: Technically, this could be undesired behaviour. Up for debate
    if armature is None:
        for armature in bpy.data.objects:
            if not armature.hide_get() and armature.type == "ARMATURE":
                break
        else:
            armature = None

    return armature

# Technically, this should not require a total_length parameter
# However, it makes it more comfortable and quick to use
def apply_vertex_remap(vertices, remap, total_length):
    base_length = len(vertices)
    vertices.extend( None for _ in range((total_length-len(vertices))) )
    for vertex in range(base_length):
        remap_vertices = remap[vertex]
        for remap_vertex in remap_vertices:
            vertices[remap_vertex] = vertices[vertex]