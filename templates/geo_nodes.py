"""
templates/geo_nodes.py
Vibe-Modeler 程序化几何节点（Geometry Nodes）生成器
支持程序化地形置换、带避让区的植被与碎石散布、悬浮微粒
兼容 Blender 4.x / 5.x：全部按插槽名字取接口，不按序号（5.x 的随机值节点只保留当前类型的插槽，按序号取会越界）
"""

GEO_NODES_SNIPPETS = {
    "_gn_helpers": """
def _gn_sock(sockets, name, stype=None):
    '''按名字取插槽；同名插槽有多个时（4.x 随机值节点按类型分组），取启用的、类型匹配的那个。'''
    for s in sockets:
        if s.name == name and getattr(s, "enabled", True) and (stype is None or s.type == stype):
            return s
    for s in sockets:
        if s.name == name:
            return s
    raise KeyError(f"socket {name} not found")

def _gn_new_group(name):
    group = bpy.data.node_groups.new(name=name, type="GeometryNodeTree")
    if hasattr(group, "interface"):
        group.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        group.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    else:
        group.inputs.new("NodeSocketGeometry", "Geometry")
        group.outputs.new("NodeSocketGeometry", "Geometry")
    return group, group.nodes.new("NodeGroupInput"), group.nodes.new("NodeGroupOutput")
""",

    "terrain_displacement": """
def apply_gn_terrain_displacement(target_obj, height_scale=1.2, noise_scale=0.25, subdivide_level=5):
    '''
    用几何节点给网格做起伏地形。会先自动细分（subdivide_level），所以传一个 4 个顶点的平面也能起伏。
    注意：地形起伏后，物体要用 placement 模板里的 snap_to_ground 重新贴地，不要再假设地面在 Z=0。
    '''
    group, in_node, out_node = _gn_new_group("GN_TerrainDisplace")
    subdiv = group.nodes.new("GeometryNodeSubdivideMesh")
    _gn_sock(subdiv.inputs, "Level").default_value = subdivide_level
    set_pos = group.nodes.new("GeometryNodeSetPosition")
    noise = group.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = noise_scale
    noise.inputs["Detail"].default_value = 3.0
    noise.inputs["Roughness"].default_value = 0.5
    v_math = group.nodes.new("ShaderNodeVectorMath")
    v_math.operation = "MULTIPLY"
    v_math.inputs[1].default_value = (0.0, 0.0, height_scale)

    group.links.new(in_node.outputs[0], _gn_sock(subdiv.inputs, "Mesh"))
    group.links.new(_gn_sock(subdiv.outputs, "Mesh"), _gn_sock(set_pos.inputs, "Geometry"))
    group.links.new(noise.outputs["Fac"], v_math.inputs[0])
    group.links.new(v_math.outputs["Vector"], _gn_sock(set_pos.inputs, "Offset"))
    group.links.new(_gn_sock(set_pos.outputs, "Geometry"), out_node.inputs[0])

    mod = target_obj.modifiers.new(name="GN_Displace", type="NODES")
    mod.node_group = group
    return mod
""",

    "surface_scatter": """
def apply_gn_surface_scatter(surface_obj, instance_obj, density=10.0, min_scale=0.5, max_scale=1.2,
                             avoid_objects=None, avoid_radius=0.6, seed=0):
    '''
    在表面散布物体（草簇、石子、野花、碎晶），带随机旋转和缩放。
    avoid_objects：主角等物体列表，这些物体周围 avoid_radius 米内不撒，防止草和石头长穿主角。
    instance_obj 会被自动隐藏（只作为散布的样本）。
    顺序要求：先把主角贴地摆好，再调用这个函数。
    '''
    group, in_node, out_node = _gn_new_group("GN_SurfaceScatter")

    distribute = group.nodes.new("GeometryNodeDistributePointsOnFaces")
    _gn_sock(distribute.inputs, "Density").default_value = density
    _gn_sock(distribute.inputs, "Seed").default_value = seed
    group.links.new(in_node.outputs[0], _gn_sock(distribute.inputs, "Mesh"))
    points_socket = _gn_sock(distribute.outputs, "Points")

    # 避让区：离任一主角太近的点删掉
    # 导入模型是空物体父级，本身没有几何，要展开到它下面的网格，否则距离恒为 0、所有点都会被删掉
    avoid_meshes = []
    for av in (avoid_objects or []):
        stack = [av]
        while stack:
            o = stack.pop()
            stack.extend(o.children)
            if o.type == 'MESH' and o not in avoid_meshes:
                avoid_meshes.append(o)
    if avoid_meshes:
        too_close = None
        for av in avoid_meshes:
            info = group.nodes.new("GeometryNodeObjectInfo")
            _gn_sock(info.inputs, "Object").default_value = av
            info.transform_space = 'RELATIVE'
            prox = group.nodes.new("GeometryNodeProximity")
            prox.target_element = 'FACES'
            group.links.new(_gn_sock(info.outputs, "Geometry"), prox.inputs[0])
            cmp = group.nodes.new("FunctionNodeCompare")
            cmp.data_type = 'FLOAT'
            cmp.operation = 'LESS_THAN'
            _gn_sock(cmp.inputs, "B", "VALUE").default_value = avoid_radius
            group.links.new(_gn_sock(prox.outputs, "Distance"), _gn_sock(cmp.inputs, "A", "VALUE"))
            if too_close is None:
                too_close = _gn_sock(cmp.outputs, "Result")
            else:
                bor = group.nodes.new("FunctionNodeBooleanMath")
                bor.operation = 'OR'
                group.links.new(too_close, bor.inputs[0])
                group.links.new(_gn_sock(cmp.outputs, "Result"), bor.inputs[1])
                too_close = bor.outputs[0]
        delete = group.nodes.new("GeometryNodeDeleteGeometry")
        delete.domain = 'POINT'
        group.links.new(points_socket, _gn_sock(delete.inputs, "Geometry"))
        group.links.new(too_close, _gn_sock(delete.inputs, "Selection"))
        points_socket = _gn_sock(delete.outputs, "Geometry")

    inst_info = group.nodes.new("GeometryNodeObjectInfo")
    _gn_sock(inst_info.inputs, "Object").default_value = instance_obj
    inst_info.transform_space = 'ORIGINAL'
    instance_on = group.nodes.new("GeometryNodeInstanceOnPoints")

    rand_rot = group.nodes.new("FunctionNodeRandomValue")
    rand_rot.data_type = 'FLOAT_VECTOR'
    _gn_sock(rand_rot.inputs, "Min", "VECTOR").default_value = (0.0, 0.0, 0.0)
    _gn_sock(rand_rot.inputs, "Max", "VECTOR").default_value = (0.0, 0.0, 6.283)
    rand_scale = group.nodes.new("FunctionNodeRandomValue")
    rand_scale.data_type = 'FLOAT'
    _gn_sock(rand_scale.inputs, "Min", "VALUE").default_value = min_scale
    _gn_sock(rand_scale.inputs, "Max", "VALUE").default_value = max_scale

    group.links.new(points_socket, _gn_sock(instance_on.inputs, "Points"))
    group.links.new(_gn_sock(inst_info.outputs, "Geometry"), _gn_sock(instance_on.inputs, "Instance"))
    group.links.new(_gn_sock(rand_rot.outputs, "Value", "VECTOR"), _gn_sock(instance_on.inputs, "Rotation"))
    group.links.new(_gn_sock(rand_scale.outputs, "Value", "VALUE"), _gn_sock(instance_on.inputs, "Scale"))

    join = group.nodes.new("GeometryNodeJoinGeometry")
    group.links.new(in_node.outputs[0], join.inputs[0])
    group.links.new(_gn_sock(instance_on.outputs, "Instances"), join.inputs[0])
    group.links.new(join.outputs[0], out_node.inputs[0])

    mod = surface_obj.modifiers.new(name="GN_Scatter", type="NODES")
    mod.node_group = group
    instance_obj.hide_render = True
    instance_obj.hide_set(True)
    return mod
""",

    "floating_motes": """
def apply_gn_floating_motes(emitter_obj, count=60, spread=4.0, mote_radius=0.03, seed=0):
    '''在发射物体上方生成空中漂浮的微尘、萤火或光斑（给它们配一个发光材质才看得见）。'''
    group, in_node, out_node = _gn_new_group("GN_FloatingMotes")

    distribute = group.nodes.new("GeometryNodeDistributePointsOnFaces")
    _gn_sock(distribute.inputs, "Density").default_value = count
    _gn_sock(distribute.inputs, "Seed").default_value = seed
    set_pos = group.nodes.new("GeometryNodeSetPosition")
    rand_offset = group.nodes.new("FunctionNodeRandomValue")
    rand_offset.data_type = 'FLOAT_VECTOR'
    _gn_sock(rand_offset.inputs, "Min", "VECTOR").default_value = (-spread, -spread, 0.5)
    _gn_sock(rand_offset.inputs, "Max", "VECTOR").default_value = (spread, spread, spread * 1.5)

    sphere = group.nodes.new("GeometryNodeMeshIcoSphere")
    _gn_sock(sphere.inputs, "Radius").default_value = mote_radius
    _gn_sock(sphere.inputs, "Subdivisions").default_value = 1
    instance_on = group.nodes.new("GeometryNodeInstanceOnPoints")
    join = group.nodes.new("GeometryNodeJoinGeometry")

    group.links.new(in_node.outputs[0], _gn_sock(distribute.inputs, "Mesh"))
    group.links.new(_gn_sock(distribute.outputs, "Points"), _gn_sock(set_pos.inputs, "Geometry"))
    group.links.new(_gn_sock(rand_offset.outputs, "Value", "VECTOR"), _gn_sock(set_pos.inputs, "Offset"))
    group.links.new(_gn_sock(set_pos.outputs, "Geometry"), _gn_sock(instance_on.inputs, "Points"))
    group.links.new(_gn_sock(sphere.outputs, "Mesh"), _gn_sock(instance_on.inputs, "Instance"))
    group.links.new(in_node.outputs[0], join.inputs[0])
    group.links.new(_gn_sock(instance_on.outputs, "Instances"), join.inputs[0])
    group.links.new(join.outputs[0], out_node.inputs[0])

    mod = emitter_obj.modifiers.new(name="GN_Motes", type="NODES")
    mod.node_group = group
    return mod
""",
}
