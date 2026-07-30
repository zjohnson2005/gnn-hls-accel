# AF-002 provenance re-capture — diff against committed artifacts

Fresh capture: `analysis/aipc-c1/reprobe_af002_2026-07-29`

The committed artifacts under `analysis/` are read-only (spec section 9.1) and were not modified. Every hash below is computed from bytes on disk at report time, never transcribed (blueprint AF-002).

## SHA-256 of committed artifacts

| Artifact | Bytes | Encoding | SHA-256 |
|---|---:|---|---|
| `analysis/_c1_machine_probe.txt` | 1402 | utf-16-le | `b6917b7ad7eb6dff899ec855eab9b41fa087510fa104efd1357f518e4bdc83e0` |
| `analysis/_c1_drivers_probe.txt` | 7848 | utf-16-le | `9b95cdf75961f23897bda5d97ad5fb4b778ff1d4ad60632b1826cd1f447f0a9d` |
| `analysis/_c1_mem_probe.txt` | 264 | utf-16-le | `f83cd5d261fa29ba7f732567d9683ac5632ab0cdb285ea06d68e6a755dc7804c` |
| `analysis/_c1_tools_probe.txt` | 15464 | utf-16-le | `8c5544481eb0025274eb221a19cf52cb81d8521b625a47417fb9ef322360871f` |
| `analysis/_c1_probe.txt` | 94 | utf-16-le | `f8c333e43ca98b1de9438e8abb2bf481547419ccd7f2af86d718bb7235d28573` |

## SHA-256 of fresh capture

| File | Bytes | Encoding | SHA-256 |
|---|---:|---|---|
| `drivers_probe.txt` | 1737 | utf-8 (no BOM) | `c6cf9d2c98026586924ef3b83f074a2529da9c9599dd6b7c48c94c30d741ae69` |
| `machine_probe.txt` | 685 | utf-8 (no BOM) | `df65511b50c0d13d922cf4dfa160c518bf5142957129240b5967d8b2b91591bc` |
| `mem_probe.txt` | 3897 | utf-8 (no BOM) | `68003bd9744f467e60ec25a7cfe8bab91b6ec4359d295766398be15c792ec4f5` |
| `reprobe_context.txt` | 345 | utf-8 (no BOM) | `d36fa011778d67205e75f2f2111c1a13efe116f0f530cf396733409f192a79ff` |
| `tools_probe.txt` | 364 | utf-8 (no BOM) | `0bfdfe109422614ff80608ee60761babb2e9581af01c1e53701ddbe05c090456` |
| `topology_probe.txt` | 1342 | utf-8 (no BOM) | `d433be0951216f784b9482a3e8234a805b1281d28d34c966dc6ce223f860803b` |

## Load-bearing claim attestation

`committed` = attested by one of the five original artifacts. `fresh` = attested by this re-capture. A claim that is fresh-only was previously carried by MACHINE.md with no artifact behind it.

| Claim | Committed | Fresh | Status |
|---|:---:|:---:|---|
| E1 CPU SKU string | yes | yes | confirmed by both |
| E2 graphics PCI device ID | yes | yes | confirmed by both |
| chassis | yes | yes | confirmed by both |
| OS build 26200 | yes | yes | confirmed by both |
| total physical memory 15,976 MB | yes | yes | confirmed by both |
| memory bank capacity 2 GiB | no | yes | **GAP CLOSED** by re-capture |
| memory bank count 8 | no | yes | **GAP CLOSED** by re-capture |
| ConfiguredClockSpeed 7467 | no | yes | **GAP CLOSED** by re-capture |
| SPD Speed field 9600 | no | yes | **GAP CLOSED** by re-capture |
| core count 8 | no | yes | **GAP CLOSED** by re-capture |
| logical processor count 8 | no | yes | **GAP CLOSED** by re-capture |
| EfficiencyClass field | no | yes | **GAP CLOSED** by re-capture |
| no SMT | no | yes | **GAP CLOSED** by re-capture |
| CPUID family/model/stepping | no | yes | **GAP CLOSED** by re-capture |

## Per-artifact unified diff

### `analysis/_c1_machine_probe.txt`

Identical after whitespace normalisation.

### `analysis/_c1_drivers_probe.txt`

101 diff line(s). The two captures ran different commands (the originals used `wmic`, removed on 25H2), so a large diff is expected; what matters is the claim table above.

```diff
--- analysis/_c1_drivers_probe.txt
+++ reprobe_af002_2026-07-29/drivers_probe.txt
@@ -11,70 +11,29 @@
                             oem31.inf
-=== NPU-ish devices ===
-> Device Description:         Intel(R) Graphics
-  Class Name:                 Display
-  Class GUID:                 {4d36e968-e325-11ce-bfc1-08002be10318}
-  Manufacturer Name:          Intel Corporation
-  Status:                     Started
-  Driver Name:                oem32.inf
-  Extension Driver Names:     oem157.inf
-> Device Description:         Intel(R) Graphics Software
-  Class Name:                 SoftwareComponent
-  Class GUID:                 {5c4c3332-344d-483c-8739-259e934c9cc8}
-  Manufacturer Name:          Intel Corporation
-  Status:                     Started
-  Driver Name:                oem34.inf
-> Device Description:         Intel(R) NPU
-  Class Name:                 ComputeAccelerator
-  Class GUID:                 {f01a9d53-3ff6-48d2-9f97-c8a7004be10c}
-  Manufacturer Name:          Intel Corporation
-  Status:                     Started
-  Driver Name:                oem127.inf
-  Extension Driver Names:     oem66.inf
-> Driver Name:                input.inf
-  Instance ID:                ACPI\ACPI000E\3&11583659&0
-  Device Description:         ACPI Wake Alarm
-  Class Name:                 System
-  Class GUID:                 {4d36e97d-e325-11ce-bfc1-08002be10318}
-  Manufacturer Name:          (Standard system devices)
-> Driver Name:                input.inf
-  Instance ID:                ACPI\INT33A1\1
-  Device Description:         Intel(R) Power Engine Plug-in
-  Class Name:                 System
-  Class GUID:                 {4d36e97d-e325-11ce-bfc1-08002be10318}
-  Manufacturer Name:          Intel Corporation
-> Driver Name:                input.inf
-  Instance ID:                SOUNDWIRE\SDCA_FUNCTION_10&MAN_01FA&FUNC_3556&TYPE_01&VER_01&ADR_01&LID_02&UID_02&SUBSYS_
-0DBA1028\7&2a4a8a8f&0&0000000000000001
-  Device Description:         CS35L57 amp (right woofer)
-  Class Name:                 MEDIA
-  Class GUID:                 {4d36e96c-e325-11ce-bfc1-08002be10318}
-  Manufacturer Name:          Microsoft
-> Driver Name:                input.inf
-  Instance ID:                ACPI\INTC10E1\CVSS
-  Device Description:         Intel(R) Vision Driver Extension
-  Class Name:                 System
-  Class GUID:                 {4d36e97d-e325-11ce-bfc1-08002be10318}
-  Manufacturer Name:          Intel
-> Device Description:         Microsoft Input Configuration Device
-  Class Name:                 HIDClass
-  Class GUID:                 {745a17a0-74d3-11d0-b6fe-00a0c90f57da}
-  Manufacturer Name:          Microsoft
-  Status:                     Started
-  Driver Name:                mtconfig.inf
-> Driver Name:                input.inf
-  Instance ID:                ROOT\RDPBUS\0000
-  Device Description:         Remote Desktop Device Redirector Bus
-  Class Name:                 System
-  Class GUID:                 {4d36e97d-e325-11ce-bfc1-08002be10318}
-  Manufacturer Name:          Microsoft
-=== driver store search ===
-Name
-----
-iigd_dch.inf_amd64_60a6f5e7b3adf3e4
-iigd_ext.inf_amd64_973fb1a57817120e
-iigd_ext.inf_amd64_fbd0f1b5091ac11d
-input.inf_amd64_a22d0c7b993d162a
-npu.inf_amd64_08aa998631b6cdd8
-npu.inf_amd64_c174cd41587112dd
-npu_extension.inf_amd64_ab612625b567ce4f
-xinputhid.inf_amd64_842a5b4e321d8ac6
+=== compute accelerators (pnputil) ===
+Microsoft PnP Utility
+Instance ID:                PCI\VEN_8086&DEV_B03E&SUBSYS_0DBA1028&REV_08\3&11583659&0&58
+Device Description:         Intel(R) NPU
+Class Name:                 ComputeAccelerator
+Class GUID:                 {f01a9d53-3ff6-48d2-9f97-c8a7004be10c}
+Manufacturer Name:          Intel Corporation
+Status:                     Started
+Driver Name:                oem127.inf
+Extension Driver Names:     oem66.inf
+=== iGPU and NPU driver versions via CIM ===
+DeviceName    : Intel(R) NPU
+DriverVersion : 32.0.100.4724
+DriverDate    : 3/18/2026 8:00:00 PM
+InfName       : oem127.inf
+DeviceID      : PCI\VEN_8086&DEV_B03E&SUBSYS_0DBA1028&REV_08\3&11583659&0&58
+DeviceName    : Intel(R) Graphics Software
+DriverVersion : 32.0.101.9999
+DriverDate    : 12/31/2023 7:00:00 PM
+InfName       : oem34.inf
+DeviceID      : SWD\DRIVERENUM\IGS&4&27F49065&0
+DeviceName    : Intel(R) Graphics
+DriverVersion : 32.0.101.8622
+DriverDate    : 2/18/2026 7:00:00 PM
+InfName       : oem32.inf
+DeviceID      : PCI\VEN_8086&DEV_B090&SUBSYS_0DBA1028&REV_00\3&11583659&0&10
+=== driver store search (elevated=False) ===
+PROBE_SKIPPED: pnputil /enum-drivers requires elevation; not elevated in this session.
```

### `analysis/_c1_mem_probe.txt`

138 diff line(s). The two captures ran different commands (the originals used `wmic`, removed on 25H2), so a large diff is expected; what matters is the claim table above.

```diff
--- analysis/_c1_mem_probe.txt
+++ reprobe_af002_2026-07-29/mem_probe.txt
@@ -1,3 +1,133 @@
-=== memory SPD via wmic ===
+=== memory banks via CIM Win32_PhysicalMemory (NEW: wmic is removed on 25H2) ===
+BankLabel            :
+DeviceLocator        : Motherboard
+Capacity             : 2147483648
+Speed                : 9600
+ConfiguredClockSpeed : 7467
+ConfiguredVoltage    : 500
+SMBIOSMemoryType     : 35
+FormFactor           : 0
+Manufacturer         :
+PartNumber           :
+SerialNumber         :
+BankLabel            :
+DeviceLocator        : Motherboard
+Capacity             : 2147483648
+Speed                : 9600
+ConfiguredClockSpeed : 7467
+ConfiguredVoltage    : 500
+SMBIOSMemoryType     : 35
+FormFactor           : 0
+Manufacturer         :
+PartNumber           :
+SerialNumber         :
+BankLabel            :
+DeviceLocator        : Motherboard
+Capacity             : 2147483648
+Speed                : 9600
+ConfiguredClockSpeed : 7467
+ConfiguredVoltage    : 500
+SMBIOSMemoryType     : 35
+FormFactor           : 0
+Manufacturer         :
+PartNumber           :
+SerialNumber         :
+BankLabel            :
+DeviceLocator        : Motherboard
+Capacity             : 2147483648
+Speed                : 9600
+ConfiguredClockSpeed : 7467
+ConfiguredVoltage    : 500
+SMBIOSMemoryType     : 35
+FormFactor           : 0
+Manufacturer         :
+PartNumber           :
+SerialNumber         :
+BankLabel            :
+DeviceLocator        : Motherboard
+Capacity             : 2147483648
+Speed                : 9600
+ConfiguredClockSpeed : 7467
+ConfiguredVoltage    : 500
+SMBIOSMemoryType     : 35
+FormFactor           : 0
+Manufacturer         :
+PartNumber           :
+SerialNumber         :
+BankLabel            :
+DeviceLocator        : Motherboard
+Capacity             : 2147483648
+Speed                : 9600
+ConfiguredClockSpeed : 7467
+ConfiguredVoltage    : 500
+SMBIOSMemoryType     : 35
+FormFactor           : 0
+Manufacturer         :
+PartNumber           :
+SerialNumber         :
+BankLabel            :
+DeviceLocator        : Motherboard
+Capacity             : 2147483648
+Speed                : 9600
+ConfiguredClockSpeed : 7467
+ConfiguredVoltage    : 500
+SMBIOSMemoryType     : 35
+FormFactor           : 0
+Manufacturer         :
+PartNumber           :
+SerialNumber         :
+BankLabel            :
+DeviceLocator        : Motherboard
+Capacity             : 2147483648
+Speed                : 9600
+ConfiguredClockSpeed : 7467
+ConfiguredVoltage    : 500
+SMBIOSMemoryType     : 35
+FormFactor           : 0
+Manufacturer         :
+PartNumber           :
+SerialNumber         :
+=== memory bank count and total ===
+bank_count=8
+total_bytes=17179869184
+per_bank_bytes=2147483648,2147483648,2147483648,2147483648,2147483648,2147483648,2147483648,2147483648
+=== memory array via CIM Win32_PhysicalMemoryArray ===
+Status                :
+Name                  : Physical Memory Array
+Replaceable           :
+Location              : 3
+Caption               : Physical Memory Array
+Description           : Physical Memory Array
+InstallDate           :
+CreationClassName     : Win32_PhysicalMemoryArray
+Manufacturer          :
+Model                 :
+OtherIdentifyingInfo  :
+PartNumber            :
+PoweredOn             :
+SerialNumber          :
+SKU                   :
+Tag                   : Physical Memory Array 0
+Version               :
+Depth                 :
+Height                :
+HotSwappable          :
+Removable             :
+Weight                :
+Width                 :
+MaxCapacity           : 16777216
+MaxCapacityEx         : 16777216
+MemoryDevices         : 8
+MemoryErrorCorrection : 3
+Use                   : 3
+PSComputerName        :
+CimClass              : root/cimv2:Win32_PhysicalMemoryArray
+CimInstanceProperties : {Caption, Description, InstallDate, Name...}
+CimSystemProperties   : Microsoft.Management.Infrastructure.CimSystemProperties
+=== OS-reported total ===
+TotalPhysicalMemory=16752234496
 === AC status ===
-Battery life report saved to file path C:\Users\zjohn\AppData\Local\Temp\br.html.
+BatteryStatus=1
+EstimatedChargeRemaining=23
+PowerOnline=False
+Discharging=True
```

### `analysis/_c1_tools_probe.txt`

89 diff line(s). The two captures ran different commands (the originals used `wmic`, removed on 25H2), so a large diff is expected; what matters is the claim table above.

```diff
--- analysis/_c1_tools_probe.txt
+++ reprobe_af002_2026-07-29/tools_probe.txt
@@ -1,78 +1,9 @@
 === where PresentMon ===
-C:\Users\zjohn\AppData\Local\Programs\Microsoft VS Code\1b50d58d73\resources\app\node_modules\@microsoft\dev-tunnels-ssh\sshRpcMessageStream.d.ts.map
-C:\Users\zjohn\AppData\Local\Programs\Microsoft VS Code\1b50d58d73\resources\app\node_modules\@microsoft\dev-tunnels-ssh\sshRpcMessageStream.js
-C:\Users\zjohn\AppData\Local\Programs\Microsoft VS Code\3c631b164c\resources\app\node_modules\@microsoft\dev-tunnels-ssh\sshRpcMessageStream.d.ts.map
-C:\Users\zjohn\AppData\Local\Programs\Microsoft VS Code\3c631b164c\resources\app\node_modules\@microsoft\dev-tunnels-ssh\sshRpcMessageStream.js
-C:\Users\zjohn\AppData\Local\Programs\Microsoft VS Code\4fe60c8b1c\resources\app\node_modules\@microsoft\dev-tunnels-ssh\sshRpcMessageStream.d.ts.map
-C:\Users\zjohn\AppData\Local\Programs\Microsoft VS Code\4fe60c8b1c\resources\app\node_modules\@microsoft\dev-tunnels-ssh\sshRpcMessageStream.js
-C:\Users\zjohn\AppData\Local\Programs\Microsoft VS Code\6928394f91\resources\app\node_modules\@microsoft\dev-tunnels-ssh\sshRpcMessageStream.d.ts.map
-C:\Users\zjohn\AppData\Local\Programs\Microsoft VS Code\6928394f91\resources\app\node_modules\@microsoft\dev-tunnels-ssh\sshRpcMessageStream.js
-C:\Users\zjohn\AppData\Local\Programs\Microsoft VS Code\6a44c352bd\resources\app\node_modules\@microsoft\dev-tunnels-ssh\sshRpcMessageStream.d.ts.map
-C:\Users\zjohn\AppData\Local\Programs\Microsoft VS Code\6a44c352bd\resources\app\node_modules\@microsoft\dev-tunnels-ssh\sshRpcMessageStream.js
-C:\Users\zjohn\AppData\Local\Programs\Microsoft VS Code\7e7950df89\resources\app\node_modules\@microsoft\dev-tunnels-ssh\sshRpcMessageStream.d.ts.map
-C:\Users\zjohn\AppData\Local\Programs\Microsoft VS Code\7e7950df89\resources\app\node_modules\@microsoft\dev-tunnels-ssh\sshRpcMessageStream.js
-C:\Users\zjohn\AppData\Local\Programs\Microsoft VS Code\93cfdd489c\resources\app\node_modules\@microsoft\dev-tunnels-ssh\sshRpcMessageStream.d.ts.map
-C:\Users\zjohn\AppData\Local\Programs\Microsoft VS Code\93cfdd489c\resources\app\node_modules\@microsoft\dev-tunnels-ssh\sshRpcMessageStream.js
-C:\Users\zjohn\AppData\Local\Programs\Microsoft VS Code\fcf604774b\resources\app\node_modules\@microsoft\dev-tunnels-ssh\sshRpcMessageStream.d.ts.map
-C:\Users\zjohn\AppData\Local\Programs\Microsoft VS Code\fcf604774b\resources\app\node_modules\@microsoft\dev-tunnels-ssh\sshRpcMessageStream.js
-C:\Users\zjohn\AppData\Local\Programs\Microsoft VS Code\ffa3c3f656\resources\app\node_modules\@microsoft\dev-tunnels-ssh\sshRpcMessageStream.d.ts.map
-C:\Users\zjohn\AppData\Local\Programs\Microsoft VS Code\ffa3c3f656\resources\app\node_modules\@microsoft\dev-tunnels-ssh\sshRpcMessageStream.js
-C:\Users\zjohn\AppData\Local\Programs\Python\Python311\Lib\test\audiodata\pluck-pcm16.aiff
-C:\Users\zjohn\AppData\Local\Programs\Python\Python311\Lib\test\audiodata\pluck-pcm16.au
-C:\Users\zjohn\AppData\Local\Programs\Python\Python311\Lib\test\audiodata\pluck-pcm16.wav
-C:\Users\zjohn\AppData\Local\Programs\Python\Python311\Lib\test\audiodata\pluck-pcm24.aiff
-C:\Users\zjohn\AppData\Local\Programs\Python\Python311\Lib\test\audiodata\pluck-pcm24.au
-C:\Users\zjohn\AppData\Local\Programs\Python\Python311\Lib\test\audiodata\pluck-pcm24.wav
-C:\Users\zjohn\AppData\Local\Programs\Python\Python311\Lib\test\audiodata\pluck-pcm32.aiff
-C:\Users\zjohn\AppData\Local\Programs\Python\Python311\Lib\test\audiodata\pluck-pcm32.au
-C:\Users\zjohn\AppData\Local\Programs\Python\Python311\Lib\test\audiodata\pluck-pcm32.wav
-C:\Users\zjohn\AppData\Local\Programs\Python\Python311\Lib\test\audiodata\pluck-pcm8.aiff
-C:\Users\zjohn\AppData\Local\Programs\Python\Python311\Lib\test\audiodata\pluck-pcm8.au
-C:\Users\zjohn\AppData\Local\Programs\Python\Python311\Lib\test\audiodata\pluck-pcm8.wav
-C:\Users\zjohn\AppData\Local\Programs\Python\Python314\Lib\test\audiodata\pluck-pcm16.wav
-C:\Users\zjohn\AppData\Local\Programs\Python\Python314\Lib\test\audiodata\pluck-pcm24-ext.wav
-C:\Users\zjohn\AppData\Local\Programs\Python\Python314\Lib\test\audiodata\pluck-pcm24.wav
-C:\Users\zjohn\AppData\Local\Programs\Python\Python314\Lib\test\audiodata\pluck-pcm32.wav
-C:\Users\zjohn\AppData\Local\Programs\Python\Python314\Lib\test\audiodata\pluck-pcm8.wav
-C:\Users\zjohn\Downloads\llamacpp-bin\bin\llama-bench-impl.dll
-C:\Users\zjohn\Downloads\llamacpp-bin\bin\llama-bench.exe
-C:\Users\zjohn\Downloads\llamacpp-bin\bin\llama-server-impl.dll
-C:\Users\zjohn\Downloads\llamacpp-bin\bin\llama-server.exe
-C:\Users\zjohn\Downloads\llamacpp-src\.devops\openvino.Dockerfile
-C:\Users\zjohn\Downloads\llamacpp-src\.github\actions\linux-setup-openvino
-C:\Users\zjohn\Downloads\llamacpp-src\.github\actions\windows-setup-openvino
-C:\Users\zjohn\Downloads\llamacpp-src\.github\workflows\build-openvino.yml
-C:\Users\zjohn\Downloads\llamacpp-src\docs\backend\OPENVINO.md
-C:\Users\zjohn\Downloads\llamacpp-src\examples\llama-eval\llama-server-simulator.py
-C:\Users\zjohn\Downloads\llamacpp-src\ggml\include\ggml-openvino.h
-C:\Users\zjohn\Downloads\llamacpp-src\ggml\src\ggml-openvino
-C:\Users\zjohn\Downloads\llamacpp-src\ggml\src\ggml-openvino\openvino
-C:\Users\zjohn\Downloads\llamacpp-src\ggml\src\ggml-openvino\ggml-openvino-extra.cpp
-C:\Users\zjohn\Downloads\llamacpp-src\ggml\src\ggml-openvino\ggml-openvino-extra.h
-C:\Users\zjohn\Downloads\llamacpp-src\ggml\src\ggml-openvino\ggml-openvino.cpp
-C:\Users\zjohn\Downloads\llamacpp-src\requirements\requirements-compare-llama-bench.txt
-C:\Users\zjohn\Downloads\llamacpp-src\scripts\compare-llama-bench.py
-C:\Users\zjohn\Downloads\llamacpp-src\tools\llama-bench
-C:\Users\zjohn\Downloads\llamacpp-src\tools\llama-bench\llama-bench.cpp
-C:\Users\zjohn\Projects\gnn-hls-accel\apu_characterization\out\turntrace_v2\cpu_runtime\bin\llama-bench-impl.dll
-C:\Users\zjohn\Projects\gnn-hls-accel\apu_characterization\out\turntrace_v2\cpu_runtime\bin\llama-bench.exe
-C:\Users\zjohn\Projects\gnn-hls-accel\apu_characterization\out\turntrace_v2\cpu_runtime\bin\llama-server-impl.dll
-C:\Users\zjohn\Projects\gnn-hls-accel\apu_characterization\out\turntrace_v2\cpu_runtime\bin\llama-server.exe
-C:\Users\zjohn\Projects\gnn-hls-accel\apu_characterization\out\turntrace_v2\cpu_runtime\llama-server-qwen.err.log
-C:\Users\zjohn\Projects\gnn-hls-accel\apu_characterization\out\turntrace_v2\cpu_runtime\llama-server-qwen.out.log
-C:\Users\zjohn\Projects\gnn-hls-accel\apu_characterization\out\turntrace_v2\cpu_runtime\llama-server.err.log
-C:\Users\zjohn\Projects\gnn-hls-accel\apu_characterization\out\turntrace_v2\cpu_runtime\llama-server.log
-=== PATH hits ===
-Name        Source
-----        ------
-python.exe  C:\Users\zjohn\AppData\Local\Microsoft\WindowsApps\python.exe
-python3.exe C:\Users\zjohn\AppData\Local\Microsoft\WindowsApps\python3.exe
-=== winget list relevant ===
-Intel┬« Graphics Software
-MSIX\AppUp.IntelArcSoftware_26.18.2353.0_x64__8j3eq9eme6ctt                             26.18.2353.0
-Power Automate
-MSIX\Microsoft.PowerAutomateDesktop_1.0.2117.0_x64__8wekyb3d8bbwe                       1.0.2117.0
-Windows ML Runtime Intel OpenVINO Execution Provider 1.8
-MSIX\WindowsWorkload.EP.Intel.OpenVINO.1.8_1.8.73.0_x64__8wekyb3d8bbwe                  1.8.73.0
-Windows ML Runtime Intel OpenVINO Execution Provider 1.8
-MSIX\WindowsWorkload.EP.Intel.OpenVINO.Framework.1.8_1.8.76.0_x64__8wekyb3d8bbwe        1.8.76.0
+Name   : presentmon.exe
+Source : C:\Users\zjohn\AppData\Local\Microsoft\WinGet\Packages\Intel.PresentMon.Console_Microsoft.Winget.Source_8wekyb
+         3d8bbwe\presentmon.exe
+=== python interpreters ===
+ -V:3.14 *        Python 3.14 (64-bit)
+ -V:3.11          Python 3.11 (64-bit)
+=== git version ===
+git version 2.55.0.windows.2
```

### `analysis/_c1_probe.txt`

No fresh counterpart. This artifact carries no hardware content (a timestamp, the hostname, and `done`), so there is nothing to re-capture or contradict.

