# Setup notes: CPU llama.cpp runtime for TurnTrace v2 P1
#
# Binaries + model live under (gitignored out/):
#   apu_characterization/out/turntrace_v2/cpu_runtime/
#     bin/llama-server.exe          # from ggml-org/llama.cpp release b10012 win-cpu-x64
#     models/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf
#
# Start server (PowerShell):
#   $root = "apu_characterization/out/turntrace_v2/cpu_runtime"
#   & "$root/bin/llama-server.exe" -m "$root/models/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf" `
#       --port 8080 -c 2048 -t 4 --host 127.0.0.1
#
# Run dry-run:
#   py -3 -m apu_characterization.turntrace_v2.cpu_dryrun --out apu_characterization/out/turntrace_v2/cpu_dryrun
#
# Tag when green:
#   git tag v2-cpu-dryrun-pass
