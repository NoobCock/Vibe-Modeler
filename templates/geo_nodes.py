"""
templates/geo_nodes.py
Vibe-Modeler 程序化几何节点（Geometry Nodes）生成器
支持程序化地形置换、植被与粒子散布、悬浮微粒与曲线实体化
兼容 Blender 3.x, 4.x 以及 5.x 版本
"""

GEO_NODES_SNIPPETS = {
    "terrain_displacement": """
def apply_gn_terrain_displacement(target_obj, height_scale=1.2, noise_scale=0.25):
    '''使用几何节点对网格应用程序化起伏地形置换'''
    group = bpy.data.node_groups.new(name="GN_TerrainDisplace", type="GeometryNodeTree")
    
    # 兼容 4.0+ / 5.0+ 接口声明
    if hasattr(group, "interface"):
        group.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        group.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    
    in_node = group.nodes.new("NodeGroupInput")
    out_node = group.nodes.new("NodeGroupOutput")
    set_pos = group.nodes.new("GeometryNodeSetPosition")
    noise = group.nodes.new("ShaderNodeTexNoise")
    v_math = group.nodes.new("ShaderNodeVectorMath")
    
    noise.inputs["Scale"].default_value = noise_scale
    noise.inputs["Detail"].default_value = 3.0
    noise.inputs["Roughness"].default_value = 0.5
    
    v_math.operation = "MULTIPLY"
    v_math.inputs[1].default_value = (0.0, 0.0, height_scale)
    
    group.links.new(in_node.outputs[0], set_pos.inputs["Geometry"])
    group.links.new(noise.outputs["Fac"], v_math.inputs[0])
    group.links.new(v_math.outputs["Vector"], set_pos.inputs["Offset"])
    group.links.new(set_pos.outputs["Geometry"], out_node.inputs[0])
    
    mod = target_obj.modifiers.new(name="GN_Displace", type="NODES")
    mod.node_group = group
    return mod
""",

    "surface_scatter": """
def apply_gn_surface_scatter(surface_obj, instance_obj, density=10.0, min_scale=0.5, max_scale=1.2):
    '''在表面程序化散布物体（如草簇、石子、野花、碎水晶），带随机旋转与缩放'''
    group = bpy.data.node_groups.new(name="GN_SurfaceScatter", type="GeometryNodeTree")
    if hasattr(group, "interface"):
        group.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        group.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
        
    in_node = group.nodes.new("NodeGroupInput")
    out_node = group.nodes.new("NodeGroupOutput")
    
    distribute = group.nodes.new("GeometryNodeDistributePointsOnFaces")
    distribute.inputs["Density"].default_value = density
    
    inst_info = group.nodes.new("GeometryNodeObjectInfo")
    inst_info.inputs["Object"].default_value = instance_obj
    inst_info.transform_space = 'RELATIVE'
    
    instance_on = group.nodes.new("GeometryNodeInstanceOnPoints")
    
    # 随机旋转 (Z轴随机旋转)
    rand_rot = group.nodes.new("FunctionNodeRandomValue")
    rand_rot.data_type = 'FLOAT_VECTOR'
    rand_rot.inputs[7].default_value = (0, 0, 0)
    rand_rot.inputs[8].default_value = (0, 0, 6.28)
    
    # 随机缩放
    rand_scale = group.nodes.new("FunctionNodeRandomValue")
    rand_scale.data_type = 'FLOAT'
    rand_scale.inputs[2].default_value = min_scale
    rand_scale.inputs[3].default_value = max_scale
    
    join = group.nodes.new("GeometryNodeJoinGeometry")
    
    group.links.new(in_node.outputs[0], distribute.inputs["Mesh"])
    group.links.new(distribute.outputs["Points"], instance_on.inputs["Points"])
    group.links.new(inst_info.outputs["Geometry"], instance_on.inputs["Instance"])
    group.links.new(rand_rot.outputs["Value"], instance_on.inputs["Rotation"])
    group.links.new(rand_scale.outputs["Value"], instance_on.inputs["Scale"])
    
    # 合并地表本身与散布实例
    group.links.new(in_node.outputs[0], join.inputs["Geometry"])
    group.links.new(instance_on.outputs["Instances"], join.inputs["Geometry"])
    group.links.new(join.outputs["Geometry"], out_node.inputs[0])
    
    mod = surface_obj.modifiers.new(name="GN_Scatter", type="NODES")
    mod.node_group = group
    return mod
""",

    "floating_motes": """
def apply_gn_floating_motes(emitter_obj, count=60, spread=4.0, mote_radius=0.03):
    '''在主体周围生成空中漂浮的发光微尘/萤火/光斑'''
    group = bpy.data.node_groups.new(name="GN_FloatingMotes", type="GeometryNodeTree")
    if hasattr(group, "interface"):
        group.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        group.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
        
    in_node = group.nodes.new("NodeGroupInput")
    out_node = group.nodes.new("NodeGroupOutput")
    
    distribute = group.nodes.new("GeometryNodeDistributePointsOnFaces")
    distribute.inputs["Density"].default_value = count
    
    # 随机偏移提升到半空中
    set_pos = group.nodes.new("GeometryNodeSetPosition")
    rand_offset = group.nodes.new("FunctionNodeRandomValue")
    rand_offset.data_type = 'FLOAT_VECTOR'
    rand_offset.inputs[7].default_value = (-spread, -spread, 0.5)
    rand_offset.inputs[8].default_value = (spread, spread, spread * 1.5)
    
    sphere = group.nodes.new("GeometryNodeMeshIcoSphere")
    sphere.inputs["Radius"].default_value = mote_radius
    sphere.inputs["Subdivisions"].default_value = 1
    
    instance_on = group.nodes.new("GeometryNodeInstanceOnPoints")
    join = group.nodes.new("GeometryNodeJoinGeometry")
    
    group.links.new(in_node.outputs[0], distribute.inputs["Mesh"])
    group.links.new(distribute.outputs["Points"], set_pos.inputs["Geometry"])
    group.links.new(rand_offset.outputs["Value"], set_pos.inputs["Offset"])
    group.links.new(set_pos.outputs["Geometry"], instance_on.inputs["Points"])
    group.links.new(sphere.outputs["Mesh"], instance_on.inputs["Instance"])
    
    group.links.new(in_node.outputs[0], join.inputs["Geometry"])
    group.links.new(instance_on.outputs["Instances"], join.inputs["Geometry"])
    group.links.new(join.outputs["Geometry"], out_node.inputs[0])
    
    mod = emitter_obj.modifiers.new(name="GN_Motes", type="NODES")
    mod.node_group = group
    return mod
"""
}
