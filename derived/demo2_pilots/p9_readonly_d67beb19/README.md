# DEMO-2 pilot P9, read-only part (record id d67beb19-57e2-45ba-a130-81466b4f681e)

Task AT, 2026-10-16 15:17 ET. Host queries only (WMI
Win32_PhysicalMemory, powercfg /getactivescheme, Win32_Battery, uptime s);
no measurement. Raw output: xps.txt, t2s.txt (CR stripped).

- XPS (computadora): 8 x 2 GiB LPDDR5X, rated Speed 9600, ConfiguredClockSpeed
  7467 MT/s; Manufacturer and PartNumber blank in WMI. Power scheme Best
  Performance (ec87a53a...). BatteryStatus 2 (AC), charge 96%.
- T2S (EVO-T2S): 8 x 8 GiB Micron MT62F4G32D8DV-023WTF, Speed and
  ConfiguredClockSpeed 8533 MT/s. Power scheme High performance
  (8c5e7fda...). No Win32_Battery instance.

Not done in this record: the P9 10-minute drift run (a measurement). It is
blocked on the XPS (Chrome, Edge and Claude desktop running) and not
allowed on the T2S in Task AT.
