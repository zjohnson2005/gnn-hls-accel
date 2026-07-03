"""hls4ml IR layer for the GNN extension.

`GraphMP` here is the hls4ml-side counterpart to the PyTorch module of the same
name in ``torch_modules.py``. It inherits from ``hls4ml.model.layers.Layer`` and
is registered with ``register_layer`` so the rest of the hls4ml pipeline
(optimizers, writer, backend templates) treats it as a first-class layer.

`initialize()` declares the output tensor and the three weight tensors the
kernel consumes (combine weight, bias, and the baked-in adjacency), mirroring
how ``Dense`` declares its weight/bias.
"""

from __future__ import annotations

import numpy as np

import hls4ml.model.layers as _layers
from hls4ml.model.attributes import Attribute, TypeAttribute, WeightAttribute
from hls4ml.model.types import IntegerPrecisionType

Layer = _layers.Layer


class GraphMP(Layer):
    """Fixed-graph message-passing layer (combine + aggregate)."""

    _expected_attributes = [
        Attribute("n_node"),
        Attribute("n_in"),
        Attribute("n_out"),
        Attribute("aggregation", value_type=str, default="sum"),
        Attribute("normalize", value_type=bool, default=False),
        WeightAttribute("weight"),
        WeightAttribute("bias"),
        WeightAttribute("adj"),
        TypeAttribute("weight"),
        TypeAttribute("bias"),
        TypeAttribute("adj"),
        TypeAttribute("accum"),
    ]

    def initialize(self):
        n_node = self.attributes["n_node"]
        n_out = self.attributes["n_out"]

        # Output is one feature vector per node: [N, F_out] (flattened by io_parallel).
        self.add_output_variable([n_node, n_out])

        # Combine weight (W: [n_in, n_out]) and bias ([n_out]).
        self.add_weights_variable(name="weight", var_name="w{index}")
        self.add_bias()

        # Adjacency baked in as a constant weight ([n_node, n_node]).
        self.add_weights_variable(name="adj", var_name="a{index}")

    def add_bias(self, quantizer=None):
        """Like Layer.add_bias but defaults to a real zero-bias of length n_out."""
        data = self.get_attr("bias_data", None)
        precision = None
        type_name = None
        if data is None:
            data = np.zeros(self.attributes["n_out"])
            precision = IntegerPrecisionType(width=1, signed=False)
            type_name = "bias{index}_t"
            quantizer = None
        self.add_weights_variable(
            name="bias", var_name="b{index}", type_name=type_name, precision=precision, data=data, quantizer=quantizer
        )


def _add_zero_bias(layer, quantizer=None):
    """Add a real zero-bias of length n_out when the module has no bias."""
    data = layer.get_attr("bias_data", None)
    precision = None
    type_name = None
    if data is None:
        data = np.zeros(layer.attributes["n_out"])
        precision = IntegerPrecisionType(width=1, signed=False)
        type_name = "bias{index}_t"
        quantizer = None
    layer.add_weights_variable(
        name="bias", var_name="b{index}", type_name=type_name, precision=precision, data=data, quantizer=quantizer
    )


class GraphMPDynamic(Layer):
    """Dynamic-graph message-passing layer. Two inputs: node features + edge_index."""

    _expected_attributes = [
        Attribute("n_node"),
        Attribute("n_in"),
        Attribute("n_out"),
        Attribute("n_edge"),
        Attribute("aggregation", value_type=str, default="sum"),
        Attribute("normalize", value_type=bool, default=False),
        WeightAttribute("weight"),
        WeightAttribute("bias"),
        TypeAttribute("weight"),
        TypeAttribute("bias"),
        TypeAttribute("accum"),
    ]

    def initialize(self):
        n_node = self.attributes["n_node"]
        n_out = self.attributes["n_out"]
        self.add_output_variable([n_node, n_out])
        self.add_weights_variable(name="weight", var_name="w{index}")
        self.add_bias()

    add_bias = _add_zero_bias


class GraphSAGEDynamic(Layer):
    """Dynamic-graph GraphSAGE layer. Two weights: neighbor (W_l) + root (W_r)."""

    _expected_attributes = [
        Attribute("n_node"),
        Attribute("n_in"),
        Attribute("n_out"),
        Attribute("n_edge"),
        Attribute("aggregation", value_type=str, default="mean"),
        Attribute("normalize", value_type=bool, default=False),
        WeightAttribute("weight"),
        WeightAttribute("root_weight"),
        WeightAttribute("bias"),
        TypeAttribute("weight"),
        TypeAttribute("root_weight"),
        TypeAttribute("bias"),
        TypeAttribute("accum"),
    ]

    def initialize(self):
        n_node = self.attributes["n_node"]
        n_out = self.attributes["n_out"]
        self.add_output_variable([n_node, n_out])
        self.add_weights_variable(name="weight", var_name="w{index}")
        self.add_weights_variable(name="root_weight", var_name="wr{index}")
        self.add_bias()

    add_bias = _add_zero_bias


class GINAggregateDynamic(Layer):
    """GINConv aggregation (no weights): (1+eps)*x_i + sum_j x_j. n_in == n_out."""

    _expected_attributes = [
        Attribute("n_node"),
        Attribute("n_in"),
        Attribute("n_out"),
        Attribute("n_edge"),
        Attribute("eps", value_type=float, default=0.0),
        TypeAttribute("accum"),
    ]

    def initialize(self):
        n_node = self.attributes["n_node"]
        n_out = self.attributes["n_out"]
        self.add_output_variable([n_node, n_out])


class GINConvDynamic(Layer):
    """Full GINConv with 2-layer ReLU MLP: agg -> Linear -> ReLU -> Linear."""

    _expected_attributes = [
        Attribute("n_node"),
        Attribute("n_in"),
        Attribute("n_hidden"),
        Attribute("n_out"),
        Attribute("n_edge"),
        Attribute("eps", value_type=float, default=0.0),
        WeightAttribute("weight1"),
        WeightAttribute("bias1"),
        WeightAttribute("weight2"),
        WeightAttribute("bias2"),
        TypeAttribute("weight1"),
        TypeAttribute("bias1"),
        TypeAttribute("weight2"),
        TypeAttribute("bias2"),
        TypeAttribute("accum"),
    ]

    def initialize(self):
        n_node = self.attributes["n_node"]
        n_out = self.attributes["n_out"]
        self.add_output_variable([n_node, n_out])
        self.add_weights_variable(name="weight1", var_name="w1_{index}")
        self.add_weights_variable(name="bias1", var_name="b1_{index}")
        self.add_weights_variable(name="weight2", var_name="w2_{index}")
        self.add_weights_variable(name="bias2", var_name="b2_{index}")


class GATConvDynamic(Layer):
    """Single-head GAT attention layer. Weights: W + att_src + att_dst + bias."""

    _expected_attributes = [
        Attribute("n_node"),
        Attribute("n_in"),
        Attribute("n_out"),
        Attribute("n_edge"),
        Attribute("negative_slope", value_type=float, default=0.2),
        WeightAttribute("weight"),
        WeightAttribute("att_src"),
        WeightAttribute("att_dst"),
        WeightAttribute("bias"),
        TypeAttribute("weight"),
        TypeAttribute("att_src"),
        TypeAttribute("att_dst"),
        TypeAttribute("bias"),
        TypeAttribute("accum"),
    ]

    def initialize(self):
        n_node = self.attributes["n_node"]
        n_out = self.attributes["n_out"]
        self.add_output_variable([n_node, n_out])
        self.add_weights_variable(name="weight", var_name="w{index}")
        self.add_weights_variable(name="att_src", var_name="asrc{index}")
        self.add_weights_variable(name="att_dst", var_name="adst{index}")
        self.add_bias()

    add_bias = _add_zero_bias


class EGNNDynamic(Layer):
    """E(n)-equivariant GNN layer. Inputs (h, x, edge_index); output [h'|x']."""

    _expected_attributes = [
        Attribute("n_node"),
        Attribute("n_h"),
        Attribute("n_coord"),
        Attribute("n_msg"),
        Attribute("n_hidden"),
        Attribute("n_edge"),
        WeightAttribute("e_w1"),
        WeightAttribute("e_b1"),
        WeightAttribute("e_w2"),
        WeightAttribute("e_b2"),
        WeightAttribute("x_w"),
        WeightAttribute("x_b"),
        WeightAttribute("h_w1"),
        WeightAttribute("h_b1"),
        WeightAttribute("h_w2"),
        WeightAttribute("h_b2"),
        TypeAttribute("e_w1"),
        TypeAttribute("e_b1"),
        TypeAttribute("e_w2"),
        TypeAttribute("e_b2"),
        TypeAttribute("x_w"),
        TypeAttribute("x_b"),
        TypeAttribute("h_w1"),
        TypeAttribute("h_b1"),
        TypeAttribute("h_w2"),
        TypeAttribute("h_b2"),
        TypeAttribute("accum"),
    ]

    def initialize(self):
        n_node = self.attributes["n_node"]
        n_out = self.attributes["n_h"] + self.attributes["n_coord"]
        self.add_output_variable([n_node, n_out])
        for name, var in (
            ("e_w1", "ew1_{index}"), ("e_b1", "eb1_{index}"),
            ("e_w2", "ew2_{index}"), ("e_b2", "eb2_{index}"),
            ("x_w", "xw_{index}"), ("x_b", "xb_{index}"),
            ("h_w1", "hw1_{index}"), ("h_b1", "hb1_{index}"),
            ("h_w2", "hw2_{index}"), ("h_b2", "hb2_{index}"),
        ):
            self.add_weights_variable(name=name, var_name=var)


def register():
    """Register the GraphMP IR layers with hls4ml (idempotent)."""
    if "GraphMP" not in _layers.layer_map:
        _layers.register_layer("GraphMP", GraphMP)
    if "GraphMPDynamic" not in _layers.layer_map:
        _layers.register_layer("GraphMPDynamic", GraphMPDynamic)
    if "GraphSAGEDynamic" not in _layers.layer_map:
        _layers.register_layer("GraphSAGEDynamic", GraphSAGEDynamic)
    if "GINAggregateDynamic" not in _layers.layer_map:
        _layers.register_layer("GINAggregateDynamic", GINAggregateDynamic)
    if "GINConvDynamic" not in _layers.layer_map:
        _layers.register_layer("GINConvDynamic", GINConvDynamic)
    if "GATConvDynamic" not in _layers.layer_map:
        _layers.register_layer("GATConvDynamic", GATConvDynamic)
    if "EGNNDynamic" not in _layers.layer_map:
        _layers.register_layer("EGNNDynamic", EGNNDynamic)
