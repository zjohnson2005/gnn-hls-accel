"""Backend templates for the GraphMP layer.

These are the two template "optimizer" passes hls4ml runs to fill in the
generated C++: the config struct (sizes + typedefs) and the function call. They
are registered with ``backend.register_template(...)`` and emit a struct that
inherits ``nnet::graph_conv_config`` (defined in nnet_graph.h) plus the
``nnet::graph_conv<...>(...)`` call.
"""

from __future__ import annotations

from hls4ml.backends.template import FunctionCallTemplate, LayerConfigTemplate

from .hls_layers import (
    GraphMP,
    GraphMPDynamic,
    GraphSAGEDynamic,
    GINAggregateDynamic,
    GINConvDynamic,
    GATConvDynamic,
    EGNNDynamic,
)

_AGG_ENUM = {"sum": "agg_sum", "mean": "agg_mean", "max": "agg_max"}

graph_conv_config_template = """struct config{index} : nnet::graph_conv_config {{
    static const unsigned n_node = {n_node};
    static const unsigned n_in = {n_in};
    static const unsigned n_out = {n_out};
    static const unsigned aggregation = nnet::{agg_enum};
    static const bool normalize = {normalize};
    static const unsigned io_type = nnet::{iotype};
    static const unsigned reuse_factor = {reuse};
    static const bool store_weights_in_bram = false;
    typedef {accum_t} accum_t;
    typedef {weight_t} weight_t;
    typedef {bias_t} bias_t;
    typedef {adj_t} adj_t;
}};\n"""

graph_conv_function_template = (
    "nnet::graph_conv<{input_t}, {output_t}, {config}>({input}, {output}, {w}, {b}, {a});"
)

graph_conv_include_list = ["nnet_utils/nnet_graph.h"]


class GraphMPConfigTemplate(LayerConfigTemplate):
    def __init__(self):
        super().__init__(GraphMP)
        self.template = graph_conv_config_template

    def format(self, node):
        params = self._default_config_params(node)
        params["n_node"] = node.get_attr("n_node")
        params["n_in"] = node.get_attr("n_in")
        params["n_out"] = node.get_attr("n_out")
        params["agg_enum"] = _AGG_ENUM[str(node.get_attr("aggregation"))]
        params["normalize"] = "true" if node.get_attr("normalize") else "false"

        accum_t = node.get_attr("accum_t")
        params["accum_t"] = accum_t.name if accum_t is not None else "ap_fixed<32,12>"
        params["weight_t"] = node.get_weights("weight").type.name
        params["bias_t"] = node.get_weights("bias").type.name
        params["adj_t"] = node.get_weights("adj").type.name

        return self.template.format(**params)


class GraphMPFunctionTemplate(FunctionCallTemplate):
    def __init__(self):
        super().__init__(GraphMP, include_header=graph_conv_include_list)
        self.template = graph_conv_function_template

    def format(self, node):
        params = self._default_function_params(node)
        params["w"] = node.get_weights("weight").name
        params["b"] = node.get_weights("bias").name
        params["a"] = node.get_weights("adj").name
        return self.template.format(**params)


# ---------------------------------------------------------------------------
# Dynamic-graph variant (edge_index is a runtime input)
# ---------------------------------------------------------------------------

graph_conv_dynamic_config_template = """struct config{index} : nnet::graph_conv_config {{
    static const unsigned n_node = {n_node};
    static const unsigned n_in = {n_in};
    static const unsigned n_out = {n_out};
    static const unsigned n_edge = {n_edge};
    static const unsigned aggregation = nnet::{agg_enum};
    static const bool normalize = {normalize};
    static const unsigned io_type = nnet::{iotype};
    static const unsigned reuse_factor = {reuse};
    static const bool store_weights_in_bram = false;
    typedef {accum_t} accum_t;
    typedef {weight_t} weight_t;
    typedef {bias_t} bias_t;
    typedef {adj_t} adj_t;
}};\n"""

graph_conv_dynamic_function_template = (
    "nnet::graph_conv_dynamic<{input_t}, {index_t}, {output_t}, {config}>"
    "({input}, {edge_index}, {output}, {w}, {b});"
)


class GraphMPDynamicConfigTemplate(LayerConfigTemplate):
    def __init__(self):
        super().__init__(GraphMPDynamic)
        self.template = graph_conv_dynamic_config_template

    def format(self, node):
        params = self._default_config_params(node)
        params["n_node"] = node.get_attr("n_node")
        params["n_in"] = node.get_attr("n_in")
        params["n_out"] = node.get_attr("n_out")
        params["n_edge"] = node.get_attr("n_edge")
        params["agg_enum"] = _AGG_ENUM[str(node.get_attr("aggregation"))]
        params["normalize"] = "true" if node.get_attr("normalize") else "false"

        accum_t = node.get_attr("accum_t")
        params["accum_t"] = accum_t.name if accum_t is not None else "ap_fixed<32,12>"
        params["weight_t"] = node.get_weights("weight").type.name
        params["bias_t"] = node.get_weights("bias").type.name
        # adj_t is unused by the dynamic kernel but kept so the base struct's
        # typedef is satisfied; reuse the accum type name.
        params["adj_t"] = params["accum_t"]

        return self.template.format(**params)


class GraphMPDynamicFunctionTemplate(FunctionCallTemplate):
    def __init__(self):
        super().__init__(GraphMPDynamic, include_header=graph_conv_include_list)
        self.template = graph_conv_dynamic_function_template

    def format(self, node):
        params = self._default_function_params(node)
        feat = node.get_input_variable(node.inputs[0])
        edge = node.get_input_variable(node.inputs[1])
        params["input_t"] = feat.type.name
        params["input"] = feat.name
        params["index_t"] = edge.type.name
        params["edge_index"] = edge.name
        params["w"] = node.get_weights("weight").name
        params["b"] = node.get_weights("bias").name
        return self.template.format(**params)


# ---------------------------------------------------------------------------
# GraphSAGE variant (two weights: neighbor W_l + root-self W_r)
# ---------------------------------------------------------------------------

graph_sage_dynamic_function_template = (
    "nnet::graph_sage_dynamic<{input_t}, {index_t}, {output_t}, {config}>"
    "({input}, {edge_index}, {output}, {w}, {wr}, {b});"
)


class GraphSAGEDynamicConfigTemplate(LayerConfigTemplate):
    def __init__(self):
        super().__init__(GraphSAGEDynamic)
        self.template = graph_conv_dynamic_config_template

    def format(self, node):
        params = self._default_config_params(node)
        params["n_node"] = node.get_attr("n_node")
        params["n_in"] = node.get_attr("n_in")
        params["n_out"] = node.get_attr("n_out")
        params["n_edge"] = node.get_attr("n_edge")
        params["agg_enum"] = _AGG_ENUM[str(node.get_attr("aggregation"))]
        params["normalize"] = "false"

        accum_t = node.get_attr("accum_t")
        params["accum_t"] = accum_t.name if accum_t is not None else "ap_fixed<32,12>"
        params["weight_t"] = node.get_weights("weight").type.name
        params["bias_t"] = node.get_weights("bias").type.name
        params["adj_t"] = params["accum_t"]

        return self.template.format(**params)


class GraphSAGEDynamicFunctionTemplate(FunctionCallTemplate):
    def __init__(self):
        super().__init__(GraphSAGEDynamic, include_header=graph_conv_include_list)
        self.template = graph_sage_dynamic_function_template

    def format(self, node):
        params = self._default_function_params(node)
        feat = node.get_input_variable(node.inputs[0])
        edge = node.get_input_variable(node.inputs[1])
        params["input_t"] = feat.type.name
        params["input"] = feat.name
        params["index_t"] = edge.type.name
        params["edge_index"] = edge.name
        params["w"] = node.get_weights("weight").name
        params["wr"] = node.get_weights("root_weight").name
        params["b"] = node.get_weights("bias").name
        return self.template.format(**params)


# ---------------------------------------------------------------------------
# GINConv aggregation ((1+eps)*x_i + sum_j x_j; no weights, n_in == n_out)
# ---------------------------------------------------------------------------

gin_aggregate_config_template = """struct config{index} : nnet::graph_conv_config {{
    static const unsigned n_node = {n_node};
    static const unsigned n_in = {n_in};
    static const unsigned n_out = {n_out};
    static const unsigned n_edge = {n_edge};
    static const unsigned aggregation = nnet::agg_sum;
    static const bool normalize = false;
    static const unsigned io_type = nnet::{iotype};
    static const unsigned reuse_factor = {reuse};
    static const bool store_weights_in_bram = false;
    typedef {accum_t} accum_t;
    typedef {accum_t} weight_t;
    typedef {accum_t} bias_t;
    typedef {accum_t} adj_t;
}};\n"""

gin_aggregate_function_template = (
    "nnet::graph_gin_aggregate<{input_t}, {index_t}, {output_t}, {config}>"
    "({input}, {edge_index}, {output}, (typename {config}::accum_t)({self_coeff}));"
)


class GINAggregateDynamicConfigTemplate(LayerConfigTemplate):
    def __init__(self):
        super().__init__(GINAggregateDynamic)
        self.template = gin_aggregate_config_template

    def format(self, node):
        params = self._default_config_params(node)
        params["n_node"] = node.get_attr("n_node")
        params["n_in"] = node.get_attr("n_in")
        params["n_out"] = node.get_attr("n_out")
        params["n_edge"] = node.get_attr("n_edge")
        accum_t = node.get_attr("accum_t")
        params["accum_t"] = accum_t.name if accum_t is not None else "ap_fixed<32,12>"
        return self.template.format(**params)


class GINAggregateDynamicFunctionTemplate(FunctionCallTemplate):
    def __init__(self):
        super().__init__(GINAggregateDynamic, include_header=graph_conv_include_list)
        self.template = gin_aggregate_function_template

    def format(self, node):
        params = self._default_function_params(node)
        feat = node.get_input_variable(node.inputs[0])
        edge = node.get_input_variable(node.inputs[1])
        params["input_t"] = feat.type.name
        params["input"] = feat.name
        params["index_t"] = edge.type.name
        params["edge_index"] = edge.name
        params["self_coeff"] = repr(1.0 + float(node.get_attr("eps")))
        return self.template.format(**params)


# ---------------------------------------------------------------------------
# Single-head GATConv attention
# ---------------------------------------------------------------------------

gat_conv_function_template = (
    "nnet::graph_gat_dynamic<{input_t}, {index_t}, {output_t}, {config}>"
    "({input}, {edge_index}, {output}, {w}, {asrc}, {adst}, {b}, "
    "(typename {config}::accum_t)({slope}));"
)


class GATConvDynamicConfigTemplate(LayerConfigTemplate):
    def __init__(self):
        super().__init__(GATConvDynamic)
        self.template = graph_conv_dynamic_config_template

    def format(self, node):
        params = self._default_config_params(node)
        params["n_node"] = node.get_attr("n_node")
        params["n_in"] = node.get_attr("n_in")
        params["n_out"] = node.get_attr("n_out")
        params["n_edge"] = node.get_attr("n_edge")
        params["agg_enum"] = "agg_sum"
        params["normalize"] = "false"
        accum_t = node.get_attr("accum_t")
        params["accum_t"] = accum_t.name if accum_t is not None else "ap_fixed<32,12>"
        params["weight_t"] = node.get_weights("weight").type.name
        params["bias_t"] = node.get_weights("bias").type.name
        params["adj_t"] = params["accum_t"]
        return self.template.format(**params)


class GATConvDynamicFunctionTemplate(FunctionCallTemplate):
    def __init__(self):
        super().__init__(GATConvDynamic, include_header=graph_conv_include_list)
        self.template = gat_conv_function_template

    def format(self, node):
        params = self._default_function_params(node)
        feat = node.get_input_variable(node.inputs[0])
        edge = node.get_input_variable(node.inputs[1])
        params["input_t"] = feat.type.name
        params["input"] = feat.name
        params["index_t"] = edge.type.name
        params["edge_index"] = edge.name
        params["w"] = node.get_weights("weight").name
        params["asrc"] = node.get_weights("att_src").name
        params["adst"] = node.get_weights("att_dst").name
        params["b"] = node.get_weights("bias").name
        params["slope"] = repr(float(node.get_attr("negative_slope")))
        return self.template.format(**params)


# ---------------------------------------------------------------------------
# Full GINConv (aggregation + 2-layer ReLU MLP, self-contained)
# ---------------------------------------------------------------------------

gin_conv_config_template = """struct config{index} : nnet::graph_conv_config {{
    static const unsigned n_node = {n_node};
    static const unsigned n_in = {n_in};
    static const unsigned n_hidden = {n_hidden};
    static const unsigned n_out = {n_out};
    static const unsigned n_edge = {n_edge};
    static const unsigned aggregation = nnet::agg_sum;
    static const bool normalize = false;
    static const unsigned io_type = nnet::{iotype};
    static const unsigned reuse_factor = {reuse};
    static const bool store_weights_in_bram = false;
    typedef {accum_t} accum_t;
    typedef {weight_t} weight_t;
    typedef {bias_t} bias_t;
    typedef {accum_t} adj_t;
}};\n"""

gin_conv_function_template = (
    "nnet::graph_gin_conv_dynamic<{input_t}, {index_t}, {output_t}, {config}>"
    "({input}, {edge_index}, {output}, {w1}, {b1}, {w2}, {b2}, "
    "(typename {config}::accum_t)({self_coeff}));"
)


class GINConvDynamicConfigTemplate(LayerConfigTemplate):
    def __init__(self):
        super().__init__(GINConvDynamic)
        self.template = gin_conv_config_template

    def format(self, node):
        params = self._default_config_params(node)
        params["n_node"] = node.get_attr("n_node")
        params["n_in"] = node.get_attr("n_in")
        params["n_hidden"] = node.get_attr("n_hidden")
        params["n_out"] = node.get_attr("n_out")
        params["n_edge"] = node.get_attr("n_edge")
        accum_t = node.get_attr("accum_t")
        params["accum_t"] = accum_t.name if accum_t is not None else "ap_fixed<32,12>"
        params["weight_t"] = node.get_weights("weight1").type.name
        params["bias_t"] = node.get_weights("bias1").type.name
        return self.template.format(**params)


class GINConvDynamicFunctionTemplate(FunctionCallTemplate):
    def __init__(self):
        super().__init__(GINConvDynamic, include_header=graph_conv_include_list)
        self.template = gin_conv_function_template

    def format(self, node):
        params = self._default_function_params(node)
        feat = node.get_input_variable(node.inputs[0])
        edge = node.get_input_variable(node.inputs[1])
        params["input_t"] = feat.type.name
        params["input"] = feat.name
        params["index_t"] = edge.type.name
        params["edge_index"] = edge.name
        params["w1"] = node.get_weights("weight1").name
        params["b1"] = node.get_weights("bias1").name
        params["w2"] = node.get_weights("weight2").name
        params["b2"] = node.get_weights("bias2").name
        params["self_coeff"] = repr(1.0 + float(node.get_attr("eps")))
        return self.template.format(**params)


# ---------------------------------------------------------------------------
# EGNN (E(n)-equivariant): inputs (h, x, edge_index) -> [h' | x']
# ---------------------------------------------------------------------------

egnn_config_template = """struct config{index} : nnet::graph_conv_config {{
    static const unsigned n_node = {n_node};
    static const unsigned n_h = {n_h};
    static const unsigned n_coord = {n_coord};
    static const unsigned n_msg = {n_msg};
    static const unsigned n_hidden = {n_hidden};
    static const unsigned n_edge = {n_edge};
    static const unsigned n_in = {n_h};
    static const unsigned n_out = {n_out};
    static const unsigned aggregation = nnet::agg_sum;
    static const bool normalize = false;
    static const unsigned io_type = nnet::{iotype};
    static const unsigned reuse_factor = {reuse};
    static const bool store_weights_in_bram = false;
    typedef {accum_t} accum_t;
    typedef {weight_t} weight_t;
    typedef {bias_t} bias_t;
    typedef {accum_t} adj_t;
}};\n"""

egnn_function_template = (
    "nnet::graph_egnn_dynamic<{input_t}, {index_t}, {output_t}, {config}>"
    "({h}, {x}, {edge_index}, {output}, "
    "{ew1}, {eb1}, {ew2}, {eb2}, {xw}, {xb}, {hw1}, {hb1}, {hw2}, {hb2});"
)


class EGNNDynamicConfigTemplate(LayerConfigTemplate):
    def __init__(self):
        super().__init__(EGNNDynamic)
        self.template = egnn_config_template

    def format(self, node):
        params = self._default_config_params(node)
        params["n_node"] = node.get_attr("n_node")
        params["n_h"] = node.get_attr("n_h")
        params["n_coord"] = node.get_attr("n_coord")
        params["n_msg"] = node.get_attr("n_msg")
        params["n_hidden"] = node.get_attr("n_hidden")
        params["n_edge"] = node.get_attr("n_edge")
        params["n_out"] = node.get_attr("n_h") + node.get_attr("n_coord")
        accum_t = node.get_attr("accum_t")
        params["accum_t"] = accum_t.name if accum_t is not None else "ap_fixed<32,12>"
        params["weight_t"] = node.get_weights("e_w1").type.name
        params["bias_t"] = node.get_weights("e_b1").type.name
        return self.template.format(**params)


class EGNNDynamicFunctionTemplate(FunctionCallTemplate):
    def __init__(self):
        super().__init__(EGNNDynamic, include_header=graph_conv_include_list)
        self.template = egnn_function_template

    def format(self, node):
        params = self._default_function_params(node)
        h = node.get_input_variable(node.inputs[0])
        x = node.get_input_variable(node.inputs[1])
        edge = node.get_input_variable(node.inputs[2])
        params["input_t"] = h.type.name
        params["h"] = h.name
        params["x"] = x.name
        params["index_t"] = edge.type.name
        params["edge_index"] = edge.name
        params["ew1"] = node.get_weights("e_w1").name
        params["eb1"] = node.get_weights("e_b1").name
        params["ew2"] = node.get_weights("e_w2").name
        params["eb2"] = node.get_weights("e_b2").name
        params["xw"] = node.get_weights("x_w").name
        params["xb"] = node.get_weights("x_b").name
        params["hw1"] = node.get_weights("h_w1").name
        params["hb1"] = node.get_weights("h_b1").name
        params["hw2"] = node.get_weights("h_w2").name
        params["hb2"] = node.get_weights("h_b2").name
        return self.template.format(**params)
