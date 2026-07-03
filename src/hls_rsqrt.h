#ifndef HLS_RSQRT_H
#define HLS_RSQRT_H

#include <stdint.h>
#include <ap_fixed.h>

// ============================================================================
// hls::sqrt-free reciprocal square root.
//
// The baseline normalization 1/sqrt(deg) instantiates an hls::sqrt core plus a
// divide -- expensive in DSPs and latency. Two replacements live here:
//
//   1. nr_rsqrt<ITERS>(x)        general positive-real 1/sqrt(x), used by the
//                                EGNN coordinate/distance datapath. Newton-
//                                Raphson seeded by the classic bit trick:
//                                    y_{n+1} = y_n * (1.5 - 0.5*x*y_n^2)
//                                ITERS=2 keeps error < ~0.2% over our range.
//
//   2. inv_sqrt_deg_lut<MAXDEG>  exact-per-degree table for the GCN degree
//                                normalization, where the argument is a small
//                                positive integer. Cheapest possible hardware:
//                                one ROM read, no iteration. Preferred for GCN.
//
// If the float bit-reinterpret in nr_rsqrt does not synthesize cleanly on a
// given Vitis version, use the LUT path for integer arguments (it covers the
// GCN case) and seed nr_rsqrt from a coarse table instead.
// ============================================================================

template <int ITERS>
inline float nr_rsqrt(float x) {
#pragma HLS INLINE
    union { float f; uint32_t u; } conv;
    conv.f = x;
    conv.u = 0x5f3759dfu - (conv.u >> 1);   // magic seed for 1/sqrt
    float y = conv.f;
    const float xhalf = 0.5f * x;
nr_iter:
    for (int i = 0; i < ITERS; i++) {
#pragma HLS UNROLL
        y = y * (1.5f - xhalf * y * y);
    }
    return y;
}

// Build a 1/sqrt(d) table for degrees d in [0, MAXDEG]. Index 0 maps to 0 so a
// zero-degree (isolated) node contributes nothing, matching the baseline.
template <typename T, int MAXDEG>
inline void build_inv_sqrt_deg_lut(T lut[MAXDEG + 1]) {
#pragma HLS INLINE
build_lut:
    for (int d = 0; d <= MAXDEG; d++) {
#pragma HLS UNROLL
        lut[d] = (d == 0) ? (T)0 : (T)nr_rsqrt<3>((float)d);
    }
}

#endif // HLS_RSQRT_H
