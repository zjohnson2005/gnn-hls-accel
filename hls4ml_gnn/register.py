"""One-call registration of the GNN extension into hls4ml.

Usage::

    import hls4ml_gnn
    hls4ml_gnn.register()          # wires all four hls4ml seams
    # ... then use the normal hls4ml flow:
    cfg = hls4ml.utils.config_from_pytorch_model(model, (N, F_in), ...)
    hmodel = hls4ml.converters.convert_from_pytorch_model(model, hls_config=cfg, ...)
    hmodel.compile(); hmodel.predict(x); hmodel.build()

This registers, against hls4ml's public Extension API:
  1. the GraphMP IR layer        (hls4ml.model.layers.register_layer)
  2. the PyTorch handler           (register_pytorch_layer_handler)
  3. config + function templates    (backend.register_template)
  4. the nnet_graph.h kernel source (backend.register_source)

It is idempotent: calling it more than once (e.g. in a REPL) is safe.
"""

from __future__ import annotations

import os

_BACKENDS = ("Vivado", "Vitis")
_registered = False


def register(backends=_BACKENDS):
    """Register the GraphMP layer with hls4ml. Safe to call repeatedly."""
    global _registered

    import hls4ml
    from hls4ml.converters.pytorch_to_hls import layer_handlers, register_pytorch_layer_handler

    from . import hls_layers
    from .converters import (
        parse_egnn_dynamic_layer,
        parse_gat_conv_dynamic_layer,
        parse_gin_aggregate_dynamic_layer,
        parse_gin_conv_dynamic_layer,
        parse_graph_conv_dynamic_layer,
        parse_graph_conv_layer,
        parse_graph_sage_dynamic_layer,
    )
    from .templates import (
        EGNNDynamicConfigTemplate,
        EGNNDynamicFunctionTemplate,
        GATConvDynamicConfigTemplate,
        GATConvDynamicFunctionTemplate,
        GINAggregateDynamicConfigTemplate,
        GINAggregateDynamicFunctionTemplate,
        GINConvDynamicConfigTemplate,
        GINConvDynamicFunctionTemplate,
        GraphMPConfigTemplate,
        GraphMPDynamicConfigTemplate,
        GraphMPDynamicFunctionTemplate,
        GraphMPFunctionTemplate,
        GraphSAGEDynamicConfigTemplate,
        GraphSAGEDynamicFunctionTemplate,
    )

    # 1. IR layers (fixed-graph + dynamic-graph + GraphSAGE)
    hls_layers.register()

    # 2. PyTorch front-end handlers
    if "GraphMP" not in layer_handlers:
        register_pytorch_layer_handler("GraphMP", parse_graph_conv_layer)
    if "GraphMPDynamic" not in layer_handlers:
        register_pytorch_layer_handler("GraphMPDynamic", parse_graph_conv_dynamic_layer)
    if "GraphSAGEDynamic" not in layer_handlers:
        register_pytorch_layer_handler("GraphSAGEDynamic", parse_graph_sage_dynamic_layer)
    if "GINAggregateDynamic" not in layer_handlers:
        register_pytorch_layer_handler("GINAggregateDynamic", parse_gin_aggregate_dynamic_layer)
    if "GINConvDynamic" not in layer_handlers:
        register_pytorch_layer_handler("GINConvDynamic", parse_gin_conv_dynamic_layer)
    if "GATConvDynamic" not in layer_handlers:
        register_pytorch_layer_handler("GATConvDynamic", parse_gat_conv_dynamic_layer)
    if "EGNNDynamic" not in layer_handlers:
        register_pytorch_layer_handler("EGNNDynamic", parse_egnn_dynamic_layer)

    # 3 + 4. Templates and kernel source, per backend
    here = os.path.dirname(os.path.abspath(__file__))
    nnet_header = os.path.join(here, "nnet_graph.h")
    templates = (
        GraphMPConfigTemplate,
        GraphMPFunctionTemplate,
        GraphMPDynamicConfigTemplate,
        GraphMPDynamicFunctionTemplate,
        GraphSAGEDynamicConfigTemplate,
        GraphSAGEDynamicFunctionTemplate,
        GINAggregateDynamicConfigTemplate,
        GINAggregateDynamicFunctionTemplate,
        GINConvDynamicConfigTemplate,
        GINConvDynamicFunctionTemplate,
        GATConvDynamicConfigTemplate,
        GATConvDynamicFunctionTemplate,
        EGNNDynamicConfigTemplate,
        EGNNDynamicFunctionTemplate,
    )
    for backend_id in backends:
        backend = hls4ml.backends.get_backend(backend_id)
        for tmpl in templates:
            try:
                backend.register_template(tmpl)
            except Exception:
                # already registered for this backend in a previous call
                pass
        backend.register_source(nnet_header)

    _registered = True
    return _registered
