# v3.1 per-task breakdown (n=5 seeds, audit PASS)

## Batch summary

| Metric | Median [IQR or range] |
|--------|------------------------|
| Batch wall (s) | 173.5 [92.4–306.8] |
| Batch host CPU (ms) | 2066.8 [1606.7–2206.8] |
| Pooled TOOL % | 20.5% |
| Pooled THREADPOOL % | 14.4% |
| Pooled ORCH % | 29.5% |
| Residual provenance % | 0.7% |

---

## LH-01

**Seeds:** n=5 · **Tools:** varies by seed

| Metric | Median [IQR] |
|--------|--------------|
| Session wall (s) | 20.4 [16.6–22.4] |
| LLM I/O wait (s) | 19.8 [16.2–21.9] |
| Remote-tool I/O wait (s) | 19.9 [16.3–22.0] |
| Host CPU (ms) | 543.7 [490.9–605.1] |
| Residual (% of host) | 0.0 [0.0–0.0] |

| Category | % host CPU (median) |
|----------|---------------------|
| TOOL | 30.8% |
| ORCH_dispatch | 28.6% |
| FRAMEWORK | 10.5% |
| TOKEN | 10.2% |
| LLM_HTTP_CPU | 8.1% |
| THREADPOOL | 5.6% |
| ORCH_setup | 3.8% |

| Step | Tool call |
|------|-----------|
| seed 0, step 1 | retrieve("vegetable garden planning by month") |
| seed 0, step 2 | retrieve("vegetable garden planning January") |
| seed 0, step 3 | retrieve("vegetable garden planning February") |
| seed 0, step 4 | retrieve("vegetable garden planning March") |
| seed 0, step 5 | retrieve("vegetable garden planning April") |
| seed 0, step 6 | retrieve("vegetable garden planning May") |
| seed 0, step 7 | retrieve("vegetable garden planning June") |
| seed 0, step 8 | retrieve("vegetable garden planning July") |
| seed 0, step 9 | retrieve("vegetable garden planning August") |
| seed 0, step 10 | retrieve("vegetable garden planning September") |
| seed 0, step 11 | retrieve("vegetable garden planning October") |
| seed 0, step 12 | retrieve("vegetable garden planning November") |
| seed 0, step 13 | retrieve("vegetable garden planning December") |
| seed 1, step 1 | retrieve("vegetable garden planning by month") |
| seed 1, step 2 | retrieve("vegetable garden planning January") |
| seed 1, step 3 | retrieve("vegetable garden planning February") |
| seed 1, step 4 | retrieve("vegetable garden planning March") |
| seed 1, step 5 | retrieve("vegetable garden planning April") |
| seed 1, step 6 | retrieve("vegetable garden planning May") |
| seed 1, step 7 | retrieve("vegetable garden planning June") |
| seed 1, step 8 | retrieve("vegetable garden planning July") |
| seed 1, step 9 | retrieve("vegetable garden planning August") |
| seed 1, step 10 | retrieve("vegetable garden planning September") |
| seed 1, step 11 | retrieve("vegetable garden planning October") |
| seed 1, step 12 | retrieve("vegetable garden planning November") |
| seed 1, step 13 | retrieve("vegetable garden planning December") |
| seed 2, step 1 | retrieve("vegetable garden planning by month") |
| seed 2, step 2 | retrieve("vegetable garden planning January") |
| seed 2, step 3 | retrieve("vegetable garden planning February") |
| seed 2, step 4 | retrieve("vegetable garden planning March") |
| seed 2, step 5 | retrieve("vegetable garden planning April") |
| seed 2, step 6 | retrieve("vegetable garden planning May") |
| seed 2, step 7 | retrieve("vegetable garden planning June") |
| seed 2, step 8 | retrieve("vegetable garden planning July") |
| seed 2, step 9 | retrieve("vegetable garden planning August") |
| seed 2, step 10 | retrieve("vegetable garden planning September") |
| seed 2, step 11 | retrieve("vegetable garden planning October") |
| seed 2, step 12 | retrieve("vegetable garden planning November") |
| seed 2, step 13 | retrieve("vegetable garden planning December") |
| seed 3, step 1 | retrieve("vegetable garden planning January") |
| seed 3, step 2 | retrieve("vegetable garden planning February") |
| seed 3, step 3 | retrieve("vegetable garden planning March") |
| seed 3, step 4 | retrieve("vegetable garden planning April") |
| seed 3, step 5 | retrieve("vegetable garden planning May") |
| seed 3, step 6 | retrieve("vegetable garden planning June") |
| seed 3, step 7 | retrieve("vegetable garden planning July") |
| seed 3, step 8 | retrieve("vegetable garden planning August") |
| seed 3, step 9 | retrieve("vegetable garden planning September") |
| seed 3, step 10 | retrieve("vegetable garden planning October") |
| seed 3, step 11 | retrieve("vegetable garden planning November") |
| seed 3, step 12 | retrieve("vegetable garden planning December") |
| seed 4, step 1 | retrieve("vegetable garden planning by month") |
| seed 4, step 2 | retrieve("June vegetable garden planning") |
| seed 4, step 3 | retrieve("February vegetable garden planning") |
| seed 4, step 4 | retrieve("January vegetable garden planning") |
| seed 4, step 5 | retrieve("August vegetable garden planning") |
| seed 4, step 6 | retrieve("March vegetable garden planning") |
| seed 4, step 7 | retrieve("April vegetable garden planning") |
| seed 4, step 8 | retrieve("May vegetable garden planning") |
| seed 4, step 9 | retrieve("November vegetable garden planning") |
| seed 4, step 10 | retrieve("September vegetable garden planning") |
| seed 4, step 11 | retrieve("July vegetable garden planning") |
| seed 4, step 12 | retrieve("October vegetable garden planning") |
| seed 4, step 13 | retrieve("December vegetable garden planning") |

---

## RH-01

**Seeds:** n=5 · **Tools:** retrieve×5

| Metric | Median [IQR] |
|--------|--------------|
| Session wall (s) | 9.0 [8.3–9.7] |
| LLM I/O wait (s) | 8.9 [7.6–9.5] |
| Remote-tool I/O wait (s) | 8.9 [7.6–9.5] |
| Host CPU (ms) | 222.0 [156.2–615.0] |
| Residual (% of host) | 0.0 [0.0–0.0] |

| Category | % host CPU (median) |
|----------|---------------------|
| TOOL | 40.8% |
| THREADPOOL | 37.0% |
| ORCH_setup | 8.3% |
| FRAMEWORK | 5.2% |
| ORCH_dispatch | 2.9% |
| TOKEN | 2.6% |
| LLM_HTTP_CPU | 2.0% |

| Step | Tool call |
|------|-----------|
| seed 0, step 1 | retrieve("the water cycle") |
| seed 0, step 2 | retrieve("how plants grow") |
| seed 0, step 3 | retrieve("birds") |
| seed 0, step 4 | retrieve("forests") |
| seed 0, step 5 | retrieve("rivers and oceans") |
| seed 1, step 1 | retrieve("the water cycle") |
| seed 1, step 2 | retrieve("how plants grow") |
| seed 1, step 3 | retrieve("rivers and oceans") |
| seed 1, step 4 | retrieve("forests") |
| seed 1, step 5 | retrieve("birds") |
| seed 2, step 1 | retrieve("the water cycle") |
| seed 2, step 2 | retrieve("forests") |
| seed 2, step 3 | retrieve("how plants grow") |
| seed 2, step 4 | retrieve("rivers and oceans") |
| seed 2, step 5 | retrieve("birds") |
| seed 3, step 1 | retrieve("how plants grow") |
| seed 3, step 2 | retrieve("rivers and oceans") |
| seed 3, step 3 | retrieve("the water cycle") |
| seed 3, step 4 | retrieve("birds") |
| seed 3, step 5 | retrieve("forests") |
| seed 4, step 1 | retrieve("the water cycle") |
| seed 4, step 2 | retrieve("how plants grow") |
| seed 4, step 3 | retrieve("forests") |
| seed 4, step 4 | retrieve("rivers and oceans") |
| seed 4, step 5 | retrieve("birds") |

---

## SO-01

**Seeds:** n=1 · **Tools:** code_exec×7

| Metric | Median [IQR] |
|--------|--------------|
| Session wall (s) | 34.0 |
| LLM I/O wait (s) | 33.8 |
| Remote-tool I/O wait (s) | 33.9 |
| Host CPU (ms) | 180.2 |
| Residual (% of host) | 0.0 |

| Category | % host CPU (median) |
|----------|---------------------|
| ORCH_dispatch | 33.2% |
| TOKEN | 17.1% |
| FRAMEWORK | 15.4% |
| LLM_HTTP_CPU | 12.4% |
| ORCH_setup | 11.1% |
| THREADPOOL | 8.4% |
| TOOL | 2.2% |

| Step | Tool call |
|------|-----------|
| 1 | code_exec("shopping_list = [
    {"item": "all-purpose flour", "q…") |
| 2 | code_exec("shopping_list = [
    {"item": "all-purpose flour", "q…") |
| 3 | code_exec("shopping_list = [
    {"item": "all-purpose flour", "q…") |
| 4 | code_exec("shopping_list = [
    {"item": "all-purpose flour", "q…") |
| 5 | code_exec("shopping_list = [
    {"item": "all-purpose flour", "q…") |
| 6 | code_exec("shopping_list = [
    {"item": "all-purpose flour", "q…") |
| 7 | code_exec("shopping_list = [
    {"item": "all-purpose flour", "q…") |

---

## SH-01

> **Excluded:** `excluded_pending_investigation` — n=1/anomalous; omit from headline CPU shares. See `SH01_DISPOSITION.md`.

**Seeds:** n=1 · **Tools:** search×3

| Metric | Median [IQR] |
|--------|--------------|
| Session wall (s) | 11.3 |
| LLM I/O wait (s) | 10.1 |
| Remote-tool I/O wait (s) | 11.3 |
| Host CPU (ms) | 175.3 |
| Residual (% of host) | 0.0 |

| Category | % host CPU (median) |
|----------|---------------------|
| FRAMEWORK | 97.6% |
| ORCH_setup | 0.9% |
| TOKEN | 0.4% |
| LLM_HTTP_CPU | 0.2% |
| THREADPOOL | 0.1% |
| ORCH_dispatch | 0.1% |

| Step | Tool call |
|------|-----------|
| 1 | search("storms") |
| 2 | search("rain") |
| 3 | search("temperature changes") |

---

## FO-01

**Seeds:** n=4 · **Tools:** search×9

| Metric | Median [IQR] |
|--------|--------------|
| Session wall (s) | 10.1 [9.3–11.7] |
| LLM I/O wait (s) | 9.4 [8.5–11.0] |
| Remote-tool I/O wait (s) | 12.5 [11.6–14.1] |
| Host CPU (ms) | 134.0 [126.2–298.4] |
| Residual (% of host) | 7.9 [6.7–10.3] |

| Category | % host CPU (median) |
|----------|---------------------|
| THREADPOOL | 31.6% |
| FRAMEWORK | 15.3% |
| ORCH_setup | 13.1% |
| ORCH_dispatch | 8.4% |
| TOKEN | 8.3% |
| RESIDUAL | 7.9% |
| LLM_HTTP_CPU | 4.4% |
| Remote_tool_IO_CPU | 1.6% |

| Step | Tool call |
|------|-----------|
| seed 1, step 1 | search("main attractions in Cairo") |
| seed 1, step 2 | search("best food in Tokyo") |
| seed 1, step 3 | search("main attractions in Tokyo") |
| seed 1, step 4 | search("Cairo weather") |
| seed 1, step 5 | search("Paris weather") |
| seed 1, step 6 | search("main attractions in Paris") |
| seed 1, step 7 | search("Tokyo weather") |
| seed 1, step 8 | search("best food in Cairo") |
| seed 1, step 9 | search("best food in Paris") |
| seed 2, step 1 | search("Cairo weather") |
| seed 2, step 2 | search("best food in Paris") |
| seed 2, step 3 | search("Paris weather") |
| seed 2, step 4 | search("main attractions in Tokyo") |
| seed 2, step 5 | search("Tokyo weather") |
| seed 2, step 6 | search("main attractions in Cairo") |
| seed 2, step 7 | search("main attractions in Paris") |
| seed 2, step 8 | search("best food in Cairo") |
| seed 2, step 9 | search("best food in Tokyo") |
| seed 3, step 1 | search("main attractions in Cairo") |
| seed 3, step 2 | search("best food in Tokyo") |
| seed 3, step 3 | search("main attractions in Tokyo") |
| seed 3, step 4 | search("Cairo weather") |
| seed 3, step 5 | search("main attractions in Paris") |
| seed 3, step 6 | search("Paris weather") |
| seed 3, step 7 | search("Tokyo weather") |
| seed 3, step 8 | search("best food in Cairo") |
| seed 3, step 9 | search("best food in Paris") |
| seed 4, step 1 | search("main attractions in Tokyo") |
| seed 4, step 2 | search("best food in Tokyo") |
| seed 4, step 3 | search("main attractions in Cairo") |
| seed 4, step 4 | search("main attractions in Paris") |
| seed 4, step 5 | search("best food in Paris") |
| seed 4, step 6 | search("Paris weather") |
| seed 4, step 7 | search("Cairo weather") |
| seed 4, step 8 | search("best food in Cairo") |
| seed 4, step 9 | search("Tokyo weather") |

---

## RH-02

**Seeds:** n=5 · **Tools:** retrieve×3

| Metric | Median [IQR] |
|--------|--------------|
| Session wall (s) | 12.7 [11.8–17.4] |
| LLM I/O wait (s) | 12.6 [11.7–17.3] |
| Remote-tool I/O wait (s) | 12.6 [11.7–17.4] |
| Host CPU (ms) | 107.4 [92.7–118.9] |
| Residual (% of host) | 0.0 [0.0–0.0] |

| Category | % host CPU (median) |
|----------|---------------------|
| TOOL | 33.4% |
| THREADPOOL | 27.6% |
| ORCH_setup | 15.2% |
| ORCH_dispatch | 7.7% |
| FRAMEWORK | 5.9% |
| LLM_HTTP_CPU | 4.4% |
| TOKEN | 3.2% |

| Step | Tool call |
|------|-----------|
| seed 0, step 1 | retrieve("baking ingredients") |
| seed 0, step 2 | retrieve("oven technique for baking") |
| seed 0, step 3 | retrieve("bread baking") |
| seed 1, step 1 | retrieve("baking ingredients") |
| seed 1, step 2 | retrieve("oven technique for baking") |
| seed 1, step 3 | retrieve("bread baking") |
| seed 2, step 1 | retrieve("bread baking") |
| seed 2, step 2 | retrieve("baking ingredients") |
| seed 2, step 3 | retrieve("oven technique for baking") |
| seed 3, step 1 | retrieve("bread baking") |
| seed 3, step 2 | retrieve("oven technique for baking") |
| seed 3, step 3 | retrieve("baking ingredients") |
| seed 4, step 1 | retrieve("bread baking") |
| seed 4, step 2 | retrieve("baking ingredients") |
| seed 4, step 3 | retrieve("oven technique for baking") |

---

## SW-01

**Seeds:** n=2 · **Tools:** retrieve×3

| Metric | Median [IQR] |
|--------|--------------|
| Session wall (s) | 6.3 [5.0–7.5] |
| LLM I/O wait (s) | 6.1 [4.9–7.3] |
| Remote-tool I/O wait (s) | 6.1 [4.9–7.3] |
| Host CPU (ms) | 103.7 [93.7–113.7] |
| Residual (% of host) | 0.0 [0.0–0.0] |

| Category | % host CPU (median) |
|----------|---------------------|
| TOOL | 37.3% |
| THREADPOOL | 26.5% |
| ORCH_setup | 14.8% |
| ORCH_dispatch | 7.0% |
| FRAMEWORK | 6.4% |
| LLM_HTTP_CPU | 4.2% |
| TOKEN | 3.7% |

| Step | Tool call |
|------|-----------|
| seed 3, step 1 | retrieve("healthy living sleep") |
| seed 3, step 2 | retrieve("healthy living exercise") |
| seed 3, step 3 | retrieve("healthy living food") |
| seed 4, step 1 | retrieve("healthy living food") |
| seed 4, step 2 | retrieve("healthy living sleep") |
| seed 4, step 3 | retrieve("healthy living exercise") |

---

## RE-01

**Seeds:** n=5 · **Tools:** varies by seed

| Metric | Median [IQR] |
|--------|--------------|
| Session wall (s) | 14.3 [10.4–84.3] |
| LLM I/O wait (s) | 14.2 [10.3–83.4] |
| Remote-tool I/O wait (s) | 14.2 [10.3–83.7] |
| Host CPU (ms) | 94.3 [49.5–919.4] |
| Residual (% of host) | 0.0 [0.0–0.4] |

| Category | % host CPU (median) |
|----------|---------------------|
| ORCH_dispatch | 27.8% |
| ORCH_setup | 19.3% |
| THREADPOOL | 14.4% |
| FRAMEWORK | 10.0% |
| LLM_HTTP_CPU | 9.1% |
| TOKEN | 8.8% |
| TOOL | 2.9% |

| Step | Tool call |
|------|-----------|
| seed 0, step 1 | code_exec("# Train 1 leaves at 9am and travels at 80 km/h
# Train…") |
| seed 0, step 2 | calculator("80 * (1 + solution[0])") |
| seed 0, step 3 | code_exec("# Re-evaluating the solution for when Train 2 catches …") |
| seed 0, step 4 | calculator("80 * (1 + 1974431)") |
| seed 1, step 1 | code_exec("# Train 1 leaves at 9am and travels at 80 km/h
# Train…") |
| seed 1, step 2 | calculator("80 * (1 + solution[0])") |
| seed 1, step 3 | code_exec("# Train 1 leaves at 9am and travels at 80 km/h
# Train…") |
| seed 1, step 4 | code_exec("# Train 1 leaves at 9am and travels at 80 km/h
# Train…") |
| seed 1, step 5 | code_exec("# Train 1 leaves at 9am and travels at 80 km/h
# Train…") |
| seed 1, step 6 | code_exec("# Train 1 leaves at 9am and travels at 80 km/h
# Train…") |
| seed 1, step 7 | code_exec("# Train 1 leaves at 9am and travels at 80 km/h
# Train…") |
| seed 1, step 8 | code_exec("# Train 1 leaves at 9am and travels at 80 km/h
# Train…") |
| seed 1, step 9 | code_exec("# Train 1 leaves at 9am and travels at 80 km/h
# Train…") |
| seed 1, step 10 | code_exec("# Train 1 leaves at 9am and travels at 80 km/h
# Train…") |
| seed 1, step 11 | code_exec("# Train 1 leaves at 9am and travels at 80 km/h
# Train…") |
| seed 1, step 12 | code_exec("# Train 1 leaves at 9am and travels at 80 km/h
# Train…") |
| seed 1, step 13 | code_exec("# Train 1 leaves at 9am and travels at 80 km/h
# Train…") |
| seed 1, step 14 | code_exec("# Train 1 leaves at 9am and travels at 80 km/h
# Train…") |
| seed 1, step 15 | code_exec("# Train 1 leaves at 9am and travels at 80 km/h
# Train…") |
| seed 1, step 16 | code_exec("# Train 1 leaves at 9am and travels at 80 km/h
# Train…") |
| seed 1, step 17 | code_exec("# Train 1 leaves at 9am and travels at 80 km/h
# Train…") |
| seed 1, step 18 | code_exec("# Train 1 leaves at 9am and travels at 80 km/h
# Train…") |
| seed 1, step 19 | code_exec("# Train 1 leaves at 9am and travels at 80 km/h
# Train…") |
| seed 1, step 20 | code_exec("# Train 1 leaves at 9am and travels at 80 km/h
# Train…") |
| seed 1, step 21 | code_exec("# Train 1 leaves at 9am and travels at 80 km/h
# Train…") |
| seed 1, step 22 | code_exec("# Train 1 leaves at 9am and travels at 80 km/h
# Train…") |
| seed 1, step 23 | code_exec("# Train 1 leaves at 9am and travels at 80 km/h
# Train…") |
| seed 1, step 24 | code_exec("# Train 1 leaves at 9am and travels at 80 km/h
# Train…") |
| seed 2, step 1 | calculator("80 * (1 + 1) / 100") |
| seed 2, step 2 | code_exec("# Train 1 leaves at 9am and travels at 80 km/h
# Train…") |
| seed 3, step 1 | code_exec("# Train 1 leaves at 9am and travels at 80 km/h
# Train…") |
| seed 3, step 2 | calculator("80 * (1 + 1) == 100 * 1") |
| seed 4, step 1 | code_exec("# Train 1 leaves at 9am and travels at 80 km/h
# Train…") |
| seed 4, step 2 | calculator("80 * (1 + solution[0])") |
| seed 4, step 3 | code_exec("# Train 1 leaves at 9am and travels at 80 km/h
# Train…") |
| seed 4, step 4 | code_exec("# Calculate the time when Train 2 catches Train 1
# Tr…") |
| seed 4, step 5 | code_exec("# Calculate the time when Train 2 catches Train 1
# Tr…") |
| seed 4, step 6 | code_exec("# Calculate the time when Train 2 catches Train 1
# Tr…") |
| seed 4, step 7 | code_exec("# Calculate the time when Train 2 catches Train 1
# Tr…") |
| seed 4, step 8 | code_exec("# Calculate the time when Train 2 catches Train 1
# Tr…") |
| seed 4, step 9 | code_exec("# Calculate the time when Train 2 catches Train 1
# Tr…") |
| seed 4, step 10 | code_exec("# Calculate the time when Train 2 catches Train 1
# Tr…") |
| seed 4, step 11 | code_exec("# Calculate the time when Train 2 catches Train 1
# Tr…") |
| seed 4, step 12 | code_exec("# Calculate the time when Train 2 catches Train 1
# Tr…") |
| seed 4, step 13 | code_exec("# Calculate the time when Train 2 catches Train 1
# Tr…") |
| seed 4, step 14 | code_exec("# Calculate the time when Train 2 catches Train 1
# Tr…") |
| seed 4, step 15 | code_exec("# Calculate the time when Train 2 catches Train 1
# Tr…") |
| seed 4, step 16 | code_exec("# Calculate the time when Train 2 catches Train 1
# Tr…") |
| seed 4, step 17 | code_exec("# Calculate the time when Train 2 catches Train 1
# Tr…") |
| seed 4, step 18 | code_exec("# Calculate the time when Train 2 catches Train 1
# Tr…") |
| seed 4, step 19 | code_exec("# Calculate the time when Train 2 catches Train 1
# Tr…") |
| seed 4, step 20 | code_exec("# Calculate the time when Train 2 catches Train 1
# Tr…") |
| seed 4, step 21 | code_exec("# Calculate the time when Train 2 catches Train 1
# Tr…") |
| seed 4, step 22 | code_exec("# Calculate the time when Train 2 catches Train 1
# Tr…") |
| seed 4, step 23 | code_exec("# Calculate the time when Train 2 catches Train 1
# Tr…") |
| seed 4, step 24 | code_exec("# Calculate the time when Train 2 catches Train 1
# Tr…") |

---

## CN-01

**Seeds:** n=3 · **Tools:** varies by seed

| Metric | Median [IQR] |
|--------|--------------|
| Session wall (s) | 5.4 [5.3–6.5] |
| LLM I/O wait (s) | 5.2 [5.2–6.3] |
| Remote-tool I/O wait (s) | 5.3 [5.2–6.3] |
| Host CPU (ms) | 86.0 [76.7–119.6] |
| Residual (% of host) | 0.0 [0.0–0.0] |

| Category | % host CPU (median) |
|----------|---------------------|
| ORCH_dispatch | 28.0% |
| ORCH_setup | 23.7% |
| FRAMEWORK | 15.2% |
| LLM_HTTP_CPU | 12.6% |
| THREADPOOL | 8.1% |
| TOKEN | 6.8% |
| TOOL | 2.9% |

| Step | Tool call |
|------|-----------|
| seed 2, step 1 | retrieve("boiling point of water at sea level") |
| seed 2, step 2 | code_exec("boiling_point_celsius = 100
boiling_point_fahrenheit =…") |
| seed 2, step 3 | calculator("200 > 1214266") |
| seed 2, step 4 | calculator("200 > 212") |
| seed 3, step 1 | calculator("100 * 9/5 + 32") |
| seed 3, step 2 | calculator("200 < 212") |
| seed 3, step 3 | code_exec("boiling_point_celsius = 100
boiling_point_fahrenheit =…") |
| seed 4, step 1 | calculator("100 * 9/5 + 32") |
| seed 4, step 2 | calculator("200 < 212") |
| seed 4, step 3 | calculator("200 < 212") |
| seed 4, step 4 | calculator("100 * 9/5 + 32") |

---

## RE-02

**Seeds:** n=5 · **Tools:** varies by seed

| Metric | Median [IQR] |
|--------|--------------|
| Session wall (s) | 7.6 [6.9–8.7] |
| LLM I/O wait (s) | 7.5 [6.4–8.5] |
| Remote-tool I/O wait (s) | 7.5 [7.0–8.6] |
| Host CPU (ms) | 76.9 [47.0–105.0] |
| Residual (% of host) | 0.0 [0.0–0.0] |

| Category | % host CPU (median) |
|----------|---------------------|
| TOOL | 24.4% |
| ORCH_setup | 22.4% |
| ORCH_dispatch | 14.8% |
| THREADPOOL | 12.4% |
| FRAMEWORK | 7.9% |
| LLM_HTTP_CPU | 7.8% |
| TOKEN | 4.4% |
| Remote_tool_IO_CPU | 0.2% |

| Step | Tool call |
|------|-----------|
| seed 0, step 1 | retrieve("benefits of sleep vs exercise") |
| seed 0, step 2 | retrieve("effects of sleep on health and performance") |
| seed 1, step 1 | retrieve("effects of sleep deprivation on health") |
| seed 1, step 2 | retrieve("benefits of sleep vs exercise") |
| seed 2, step 1 | search("benefits of sleep vs exercise") |
| seed 2, step 2 | search("sleep and exercise trade-offs") |
| seed 3, step 1 | search("sleep eight hours vs exercise benefits") |
| seed 3, step 2 | retrieve("What are the benefits of exercising for an hour?") |
| seed 3, step 3 | retrieve("What are the benefits of sleeping eight hours?") |
| seed 4, step 1 | search("sleep recommendations for adults") |
| seed 4, step 2 | search("benefits of sleep vs exercise") |

---

## SH-02

**Seeds:** n=2 · **Tools:** search×4

| Metric | Median [IQR] |
|--------|--------------|
| Session wall (s) | 7.3 [6.9–7.7] |
| LLM I/O wait (s) | 6.7 [6.2–7.1] |
| Remote-tool I/O wait (s) | 8.1 [7.7–8.5] |
| Host CPU (ms) | 67.5 [61.1–73.9] |
| Residual (% of host) | 0.2 [-0.1–0.5] |

| Category | % host CPU (median) |
|----------|---------------------|
| ORCH_setup | 27.7% |
| THREADPOOL | 23.2% |
| ORCH_dispatch | 16.5% |
| FRAMEWORK | 12.9% |
| TOKEN | 8.9% |
| LLM_HTTP_CPU | 8.7% |
| Remote_tool_IO_CPU | 1.3% |
| RESIDUAL | 0.2% |

| Step | Tool call |
|------|-----------|
| seed 0, step 1 | search("planets") |
| seed 0, step 2 | search("eclipses") |
| seed 0, step 3 | search("telescopes") |
| seed 0, step 4 | search("the moon") |
| seed 1, step 1 | search("the moon") |
| seed 1, step 2 | search("eclipses") |
| seed 1, step 3 | search("telescopes") |
| seed 1, step 4 | search("planets") |

---

## CH-02

**Seeds:** n=4 · **Tools:** varies by seed

| Metric | Median [IQR] |
|--------|--------------|
| Session wall (s) | 4.9 [4.4–5.8] |
| LLM I/O wait (s) | 4.3 [4.3–5.3] |
| Remote-tool I/O wait (s) | 4.8 [4.3–5.7] |
| Host CPU (ms) | 54.6 [48.8–59.7] |
| Residual (% of host) | 0.0 [0.0–0.0] |

| Category | % host CPU (median) |
|----------|---------------------|
| ORCH_setup | 32.3% |
| THREADPOOL | 22.0% |
| ORCH_dispatch | 15.3% |
| FRAMEWORK | 9.7% |
| LLM_HTTP_CPU | 9.6% |
| TOKEN | 6.5% |
| TOOL | 5.2% |
| Remote_tool_IO_CPU | 0.4% |

| Step | Tool call |
|------|-----------|
| seed 0, step 1 | calculator("1000 * (1 + 0.05) ** 30") |
| seed 0, step 2 | code_exec("import numpy as np; data = [1, 2, 3, 4, 5, 6, 7, 8, 9,…") |
| seed 1, step 1 | code_exec("import numpy as np; data = [1, 2, 3, 4, 5, 6, 7, 8, 9,…") |
| seed 1, step 2 | calculator("1000 * (1 + 0.05) ** 30") |
| seed 1, step 3 | search("word frequency count") |
| seed 2, step 1 | calculator("1000 * (1 + 0.05) ** 30") |
| seed 2, step 2 | code_exec("import numpy as np; data = [1, 2, 3, 4, 5, 6, 7, 8, 9,…") |
| seed 2, step 3 | search("word frequency count") |
| seed 3, step 1 | calculator("1000 * (1 + 0.05) ** 30") |
| seed 3, step 2 | code_exec("import numpy as np; data = [1, 2, 3, 4, 5, 6, 7, 8, 9,…") |
| seed 3, step 3 | search("word frequency count") |

---

## CH-01

**Seeds:** n=3 · **Tools:** calculator×1, code_exec×1

| Metric | Median [IQR] |
|--------|--------------|
| Session wall (s) | 5.7 [5.0–6.4] |
| LLM I/O wait (s) | 5.6 [4.9–6.3] |
| Remote-tool I/O wait (s) | 5.6 [4.9–6.4] |
| Host CPU (ms) | 49.8 [44.3–64.8] |
| Residual (% of host) | 0.0 [0.0–0.0] |

| Category | % host CPU (median) |
|----------|---------------------|
| ORCH_setup | 38.9% |
| ORCH_dispatch | 16.2% |
| THREADPOOL | 14.3% |
| LLM_HTTP_CPU | 10.0% |
| FRAMEWORK | 8.4% |
| TOKEN | 5.6% |
| TOOL | 4.5% |

| Step | Tool call |
|------|-----------|
| 1 | code_exec("def is_prime(n):
    if n <= 1:
        return False
 …") |
| 2 | calculator("20000 * log(20000) - 20000") |

---

## LH-02

**Seeds:** n=5 · **Tools:** (none)

| Metric | Median [IQR] |
|--------|--------------|
| Session wall (s) | 5.5 [4.5–6.3] |
| LLM I/O wait (s) | 5.5 [4.5–6.3] |
| Remote-tool I/O wait (s) | 5.5 [4.5–6.3] |
| Host CPU (ms) | 14.4 [11.3–16.2] |
| Residual (% of host) | 0.0 [0.0–0.0] |

| Category | % host CPU (median) |
|----------|---------------------|
| ORCH_setup | 76.9% |
| LLM_HTTP_CPU | 10.7% |
| FRAMEWORK | 8.4% |
| TOKEN | 3.6% |

| Step | Tool call |
|------|-----------|
| — | (none) |

