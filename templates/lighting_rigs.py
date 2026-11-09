"""
templates/lighting_rigs.py
Vibe-Modeler 唯美光影布光预设库
"""

LIGHTING_RIG_SNIPPETS = {
    "golden_hour": """
def setup_golden_hour_lighting():
    # 1. 暖金主光 (Sun Light, 45度倾斜照入)
    sun_data = bpy.data.lights.new(name="Sun_Key", type='SUN')
    sun_data.energy = 4.5
    sun_data.color = (1.0, 0.72, 0.45) # 温暖金橙
    sun_data.angle = math.radians(4.0) # 柔和阴影边缘
    sun_obj = bpy.data.objects.new(name="Sun_Key", object_data=sun_data)
    bpy.context.collection.objects.link(sun_obj)
    sun_obj.rotation_euler = (math.radians(55), math.radians(15), math.radians(-45))

    # 2. 冷靛蓝天光填充 (Sky Ambient Fill)
    world = bpy.context.scene.world
    if world and world.node_tree:
        bg = world.node_tree.nodes.get("Background")
        if bg:
            bg.inputs['Color'].default_value = (0.2, 0.35, 0.65, 1.0)
            bg.inputs['Strength'].default_value = 0.8

    # 3. 轮廓光 (Rim Area Light)
    rim_data = bpy.data.lights.new(name="Rim_Light", type='AREA')
    rim_data.energy = 150.0
    rim_data.color = (1.0, 0.85, 0.6)
    rim_data.size = 3.0
    rim_obj = bpy.data.objects.new(name="Rim_Light", object_data=rim_data)
    bpy.context.collection.objects.link(rim_obj)
    rim_obj.location = (0, 6, 4)
    rim_obj.rotation_euler = (math.radians(-45), 0, math.radians(180))
""",

    "dreamy_cyber_night": """
def setup_dreamy_cyber_lighting():
    # 1. 青蓝主光 (Cyan Key Light)
    key_data = bpy.data.lights.new(name="Key_Cyan", type='AREA')
    key_data.energy = 220.0
    key_data.color = (0.1, 0.8, 0.95)
    key_data.size = 4.0
    key_obj = bpy.data.objects.new(name="Key_Cyan", object_data=key_data)
    bpy.context.collection.objects.link(key_obj)
    key_obj.location = (-4, -4, 5)
    key_obj.rotation_euler = (math.radians(45), math.radians(-20), math.radians(-35))

    # 2. 品红轮廓勾勒 (Magenta Rim Light)
    rim_data = bpy.data.lights.new(name="Rim_Magenta", type='AREA')
    rim_data.energy = 300.0
    rim_data.color = (0.95, 0.15, 0.6)
    rim_data.size = 3.0
    rim_obj = bpy.data.objects.new(name="Rim_Magenta", object_data=rim_data)
    bpy.context.collection.objects.link(rim_obj)
    rim_obj.location = (4, 5, 3.5)
    rim_obj.rotation_euler = (math.radians(-35), math.radians(25), math.radians(145))
"""
}
