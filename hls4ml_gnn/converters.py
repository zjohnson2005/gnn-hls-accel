"""PyTorch -> hls4ml converter handler for GraphMP.

Registered with ``hls4ml.converters.register_pytorch_layer_handler('GraphMP',
parse_graph_conv_layer)``. The pytorch front-end calls this when it hits a
``torch_modules.GraphMP`` leaf module; it reads the module's parameters and
returns the attribute dict + output shape that the hls4ml ``GraphMP`` IR layer
consumes.

Handler signature is fixed by hls4ml's pytorch parser:
    (operation, layer_name, input_names, input_shapes, node, class_object,
     data_reader, config)
"""

from __future__ import annotations


def parse_graph_conv_layer(
    operation, layer_name, input_names, input_shapes, node, class_object, data_reader, config
):
    assert operation == "GraphMP", f"unexpected operation {operation!r}"

    layer = {}
    layer["class_name"] = "GraphMP"
    layer["name"] = layer_name
    if input_names is not None:
        layer["inputs"] = input_names

    layer["n_node"] = int(class_object.n_node)
    layer["n_in"] = int(class_object.in_features)
    layer["n_out"] = int(class_object.out_features)
    layer["aggregation"] = str(class_object.aggregation)
    layer["normalize"] = bool(class_object.normalize)

    # torch Linear weight is [out, in]; the kernel indexes W[k*n_out + o] = W[in][out].
    layer["weight_data"] = class_object.weight.detach().cpu().numpy().T.copy()
    if getattr(class_object, "bias", None) is not None:
        layer["bias_data"] = class_object.bias.detach().cpu().numpy()
    else:
        layer["bias_data"] = None

    # Adjacency baked in as a constant weight, row-major [n_node, n_node].
    layer["adj_data"] = class_object.adj.detach().cpu().numpy().copy()

    # Output keeps the input rank with the last (feature) dim swapped to n_out.
    output_shape = list(input_shapes[0])
    output_shape[-1] = layer["n_out"]

    return layer, output_shape


def parse_graph_conv_dynamic_layer(
    operation, layer_name, input_names, input_shapes, node, class_object, data_reader, config
):
    assert operation == "GraphMPDynamic", f"unexpected operation {operation!r}"

    layer = {}
    layer["class_name"] = "GraphMPDynamic"
    layer["name"] = layer_name
    # Two inputs: [node_features, edge_index]. Order follows the forward() signature.
    if input_names is not None:
        layer["inputs"] = list(input_names)

    layer["n_node"] = int(class_object.n_node)
    layer["n_in"] = int(class_object.in_features)
    layer["n_out"] = int(class_object.out_features)
    layer["n_edge"] = int(class_object.n_edge)
    layer["aggregation"] = str(class_object.aggregation)
    layer["normalize"] = bool(class_object.normalize)

    layer["weight_data"] = class_object.weight.detach().cpu().numpy().T.copy()
    if getattr(class_object, "bias", None) is not None:
        layer["bias_data"] = class_object.bias.detach().cpu().numpy()
    else:
        layer["bias_data"] = None

    # Output shape from the node-feature input (inputs[0]); last dim -> n_out.
    output_shape = list(input_shapes[0])
    output_shape[-1] = layer["n_out"]

    return layer, output_shape


def parse_gin_aggregate_dynamic_layer(
    operation, layer_name, input_names, input_shapes, node, class_object, data_reader, config
):
    assert operation == "GINAggregateDynamic", f"unexpected operation {operation!r}"

    layer = {}
    layer["class_name"] = "GINAggregateDynamic"
    layer["name"] = layer_name
    if input_names is not None:
        layer["inputs"] = list(input_names)

    layer["n_node"] = int(class_object.n_node)
    layer["n_in"] = int(class_object.in_features)
    layer["n_out"] = int(class_object.in_features)  # aggregation preserves width
    layer["n_edge"] = int(class_object.n_edge)
    layer["eps"] = float(class_object.eps)

    output_shape = list(input_shapes[0])
    output_shape[-1] = layer["n_out"]

    return layer, output_shape


def parse_gin_conv_dynamic_layer(
    operation, layer_name, input_names, input_shapes, node, class_object, data_reader, config
):
    assert operation == "GINConvDynamic", f"unexpected operation {operation!r}"

    layer = {}
    layer["class_name"] = "GINConvDynamic"
    layer["name"] = layer_name
    if input_names is not None:
        layer["inputs"] = list(input_names)

    layer["n_node"] = int(class_object.n_node)
    layer["n_in"] = int(class_object.in_features)
    layer["n_hidden"] = int(class_object.hidden_features)
    layer["n_out"] = int(class_object.out_features)
    layer["n_edge"] = int(class_object.n_edge)
    layer["eps"] = float(class_object.eps)

    # Linear weights stored [in, out] for the kernel's W[k*out + o] indexing.
    layer["weight1_data"] = class_object.weight1.detach().cpu().numpy().T.copy()
    layer["bias1_data"] = class_object.bias1.detach().cpu().numpy()
    layer["weight2_data"] = class_object.weight2.detach().cpu().numpy().T.copy()
    layer["bias2_data"] = class_object.bias2.detach().cpu().numpy()

    output_shape = list(input_shapes[0])
    output_shape[-1] = layer["n_out"]

    return layer, output_shape


def parse_egnn_dynamic_layer(
    operation, layer_name, input_names, input_shapes, node, class_object, data_reader, config
):
    assert operation == "EGNNDynamic", f"unexpected operation {operation!r}"

    layer = {}
    layer["class_name"] = "EGNNDynamic"
    layer["name"] = layer_name
    # Three inputs: [h, x, edge_index] following the forward() signature.
    if input_names is not None:
        layer["inputs"] = list(input_names)

    layer["n_node"] = int(class_object.n_node)
    layer["n_h"] = int(class_object.n_h)
    layer["n_coord"] = int(class_object.n_coord)
    layer["n_msg"] = int(class_object.n_msg)
    layer["n_hidden"] = int(class_object.n_hidden)
    layer["n_edge"] = int(class_object.n_edge)

    def _w(mod):
        return mod.weight.detach().cpu().numpy().T.copy()  # [out, in] -> [in, out]

    def _b(mod):
        return mod.bias.detach().cpu().numpy().copy()

    phi_e = class_object.phi_e
    phi_h = class_object.phi_h
    phi_x = class_object.phi_x

    layer["e_w1_data"] = _w(phi_e[0])
    layer["e_b1_data"] = _b(phi_e[0])
    layer["e_w2_data"] = _w(phi_e[2])
    layer["e_b2_data"] = _b(phi_e[2])
    layer["x_w_data"] = phi_x.weight.detach().cpu().numpy().reshape(-1).copy()
    layer["x_b_data"] = phi_x.bias.detach().cpu().numpy().reshape(1).copy()
    layer["h_w1_data"] = _w(phi_h[0])
    layer["h_b1_data"] = _b(phi_h[0])
    layer["h_w2_data"] = _w(phi_h[2])
    layer["h_b2_data"] = _b(phi_h[2])

    # Output is the concatenation [h' | x'] -> last dim n_h + n_coord.
    output_shape = list(input_shapes[0])
    output_shape[-1] = layer["n_h"] + layer["n_coord"]

    return layer, output_shape


def parse_gat_conv_dynamic_layer(
    operation, layer_name, input_names, input_shapes, node, class_object, data_reader, config
):
    assert operation == "GATConvDynamic", f"unexpected operation {operation!r}"

    layer = {}
    layer["class_name"] = "GATConvDynamic"
    layer["name"] = layer_name
    if input_names is not None:
        layer["inputs"] = list(input_names)

    layer["n_node"] = int(class_object.n_node)
    layer["n_in"] = int(class_object.in_features)
    layer["n_out"] = int(class_object.out_features)
    layer["n_edge"] = int(class_object.n_edge)
    layer["negative_slope"] = float(class_object.negative_slope)

    layer["weight_data"] = class_object.weight.detach().cpu().numpy().T.copy()
    layer["att_src_data"] = class_object.att_src.detach().cpu().numpy().reshape(-1).copy()
    layer["att_dst_data"] = class_object.att_dst.detach().cpu().numpy().reshape(-1).copy()
    if getattr(class_object, "bias", None) is not None:
        layer["bias_data"] = class_object.bias.detach().cpu().numpy()
    else:
        layer["bias_data"] = None

    output_shape = list(input_shapes[0])
    output_shape[-1] = layer["n_out"]

    return layer, output_shape


def parse_graph_sage_dynamic_layer(
    operation, layer_name, input_names, input_shapes, node, class_object, data_reader, config
):
    assert operation == "GraphSAGEDynamic", f"unexpected operation {operation!r}"

    layer = {}
    layer["class_name"] = "GraphSAGEDynamic"
    layer["name"] = layer_name
    if input_names is not None:
        layer["inputs"] = list(input_names)

    layer["n_node"] = int(class_object.n_node)
    layer["n_in"] = int(class_object.in_features)
    layer["n_out"] = int(class_object.out_features)
    layer["n_edge"] = int(class_object.n_edge)
    layer["aggregation"] = str(class_object.aggregation)
    layer["normalize"] = False

    # Two weights: neighbor (W_l) and root/self (W_r); both stored [in, out].
    layer["weight_data"] = class_object.weight.detach().cpu().numpy().T.copy()
    layer["root_weight_data"] = class_object.root_weight.detach().cpu().numpy().T.copy()
    if getattr(class_object, "bias", None) is not None:
        layer["bias_data"] = class_object.bias.detach().cpu().numpy()
    else:
        layer["bias_data"] = None

    output_shape = list(input_shapes[0])
    output_shape[-1] = layer["n_out"]

    return layer, output_shape
