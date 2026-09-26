# LTspice verification — results (140 W / 10 A design, LTC7803)

Simulations by `sim/buck_sim.py`. Re-run everything with `.venv/Scripts/python sim/buck_sim.py`; the tests run in parallel
(~30 min on this machine). Pass test names to run a subset, or `--no-sim` to re-plot existing results.
Netlists, raw data and logs: `sim/out/`; plots: `sim/plots/`. Raw console output of the last full run: `sim/out/run_all.txt`.

Run on LTspice 26.1.1, 2026-09-27. The pre-pivot LTC7801 / 20 A results are in git (`d8d0a65`).

## What is simulated

- **Controller:** ADI's LTC7803 model from the LTspice library (encrypted, pin-accurate). RFREQ 124 k → **300 kHz**,
  MODE 100 k to INTVCC (pulse-skip), TRACK/SS 10 nF, **EXTVCC 12 V**, external boost diode INTVCC → BOOST, 0.1 µF boost cap.
- **FETs:** 2× CSD18531Q5A, modelled as an approximate VDMOS from the datasheet (Rds(on) 4.4 mΩ @4.5 V, Ciss 3.2 nF,
  Coss 380 pF, Crss 11 pF, Qrr via TT = 12 ns).
- **Power stage:** SER2918H-103 10 µH (2.86 mΩ), **2.0 mΩ** sense resistor.
- **Output filter:** C1 = 12 µF ceramics + 100 µF / 0.1 Ω damper, **0.47 µH** post filter (1.7 mΩ), C2 = 12 µF ceramics + 100 µF / 24 mΩ polymer, 1 mΩ output shunt.
- **Input:** source with 0.5 µH / 20 mΩ of cable, 100 µF bulk, 18 µF ceramics.
- **Control scheme (unchanged from the 20 A design):**
  - VFB held at 0.695 V from INTVCC (61.9 k / 10 k) — above the 0.56 V foldback threshold, below the 0.88 V FB-OVP.
  - CV and CC ADA4522 op-amps pull ITH down through BAT54 diodes; compensation networks return to ITH (anti-windup).
  - CC loop senses the inductor current: INA240A3 (gain 100, behavioural) across the 2.0 mΩ resistor → 0.2 V/A.
  - Fast ITH clamp: PNP from ITH to GND, base from a 3rd DAC channel, set to Iset + 3 A using the ITH map below.
  - Regen clamp: 2 Ω, on at Vset + 1.3 V (or 32.7 V absolute), hysteretic.
- **Firmware sequence modelled:** RUN at t = 0; current setpoint ramps over 0.5–0.8 ms, voltage setpoint over 0.8–1.3 ms.

### Component values used

| Block | Values |
|---|---|
| CV amp | divider 91.9 k / 10 k (÷10.19); Rz 47.5 k, Cf 1.3 nF, Cp 68 pF |
| CC amp | Rin 10 k; Rz 2.4 k, Cf 27 nF, Cp 1.3 nF |
| ITH | 100 pF to GND; PNP clamp (2N3906 in the sim, BC857 class for real) |

## Results

| Test | What | Result |
|---|---|---|
| t0 | ITH forced 0.5 … 1.0 V (probe) | I_L = 23.2 A/V × (ITH − 0.40 V) at low duty (2.0 mΩ). With 2.5 mΩ it was 17.8 A/V, matching the calc's 17.5 A/V assumption |
| t0 50/75/88 | ITH map at D ≈ 0.5 / 0.75 / 0.88 (CV, load steps 2–10 A) | 25.0 A/V, offset 0.46 V / 25.0 A/V, 0.44 V / **15.1 A/V, offset 0.80 V** — near D = 0.9 slope compensation shifts and flattens the map |
| t1 | CV 24 V from 30 V, load step 1 ↔ 10 A (1 µs edges) | Dip **1.0 V** (23.0 V), overshoot on release 0.67 V, no ringing. Steady ripple at 10 A: **6 mV pp** |
| t2 | CV 24 V, PWM load 0.5 ↔ 8 A at 20 kHz and 2 kHz | 20 kHz: 23.55–24.62 V; 2 kHz: 22.3–24.75 V (each edge like t1). Loop stays well-behaved |
| t3 | CC 5 A, 10 mΩ short, then released | Output-cap dump spike (ideal wiring), main inductor ≤ 23.5 A for one cycle (< 32 A Isat), then 5 A. Release: CC-limited ramp back to 24 V, 0.8 V overshoot |
| t4 | Regen: 3.5 A pushed back for 1 ms at 24 V (28 V PD in) | Buck stops (pulse-skip), clamp chops at ~25 V (12.6 A peaks). Input current ≥ −0.1 A (no real backfeed) |
| t5 | **26.5 V / 10 A from 30 V** (D ≈ 0.88), then release | Holds **26.47–26.51 V at 10.0 A**, but ITH sits at its 1.40 V maximum: this is the edge. Release: +1.3 V, clamp catches it |
| t6 | 1 V / 10 A from 31 V (min on-time region) | 0.990 V, flat — fine |
| t7 | Dropout: 28 V set from 28 V PD at ~4.3 A, then 26.5 V | Does **not** reach 100 % duty under load: output 26.3–26.6 V with ITH at its maximum (the same slope-compensation limit as t5). 26.5 V at 4.3 A regulates. **Practical ceiling from USB-C ≈ 26.5 V at ≈ 4.3 A** |
| t8 | Long idle: output held 0.8 V above Vset for 3 ms, then a 5 A step | Resumes cleanly (dip 1.4 V); the charge pump keeps the boost cap up while idle |

Plots: `sim/plots/t*.png`, zoom of the 200 kHz sub-harmonic oscillation: `zoom_highduty.png`.

## Design changes that came out of the simulation

1. **fsw 200 → 300 kHz.** At 200 kHz the LTC7803 showed period doubling (sub-harmonic oscillation) at D ≥ 0.8: its internal
   slope-compensation ramp is a fixed voltage per cycle, so a lower frequency gives a slower ramp against the same inductor down-slope.
   300 kHz and 400 kHz were clean. Cost: ~0.8 W more loss than 200 kHz.
2. **R_SENSE 2.5 → 2.0 mΩ.** Slope compensation also lowers the available peak current at high duty. With 2.5 mΩ, ITH at its maximum gave
   only ~9.4 A at 27 V from 30 V. 2.0 mΩ gives 10 A at 26.5 V (t5); 1.5 mΩ held 27 V beyond 11.5 A but its low-duty hard limit (up to
   37 A) would exceed the inductor's 32 A Isat. **Spec consequence: 10 A up to ≈ Vin − 3.5 V** (from USB-C the 140 W budget limits first anyway).
3. **EXTVCC from ≥ 7 V (use the 12 V aux rail), not 5 V.** With EXTVCC = 5 V the EXTVCC LDO is in dropout (INTVCC ≈ 4.9 V), the boost
   supply sits at ~4.3 V and sags to ~3.3 V after a high-duty start. After an idle period (start-up overshoot) the controller then refused to
   switch for > 1 ms while the output collapsed, and restarted with a 33 A inductor peak. With EXTVCC = 7 V or 12 V: INTVCC = 5.15 V, clean restart.
4. **External boost diode** INTVCC → BOOST (the LTC7803 has none inside; a low-leakage Schottky, ADI uses a CMDSH-4E).
5. **ITH clamp must be duty-aware.** The ITH ↔ current map is ~25 A/V with ~0.45 V offset up to D ≈ 0.75, but ~15 A/V with 0.8 V offset
   near D ≈ 0.9. Firmware knows Vin and Vset, so it computes the clamp from the duty, and should calibrate at run time
   (read ITH and the INA240 output with the ADC).

## Things the simulation shows that firmware or hardware must handle

- **Output envelope near dropout (LTspice):** 30 V DC → 10 A up to 26.5 V; 28 V PD → ≈ 26.5 V max at ≈ 4.3 A (the 140 W budget
  would allow ~4.9 A there). A lower R_SENSE would buy a bit more, at the cost of the low-duty hard limit exceeding the inductor Isat.
- **High duty = no headroom.** At 26.5 V / 10 A from 30 V ITH is already at its maximum. Firmware should limit Iset to what the
  duty allows (≈ 10 A up to Vin − 3.5 V, tapering above), otherwise the output sags instead of the CC loop taking over cleanly.
- **Sense signal is small** (ΔIL·R_SENSE ≈ 5 mV vs LTC's recommended 10–20 mV): Kelvin-route the sense lines and fit the RC filter at
  the SENSE pins. The sim is noise-free, so noise pick-up is a layout item.
- **Short-circuit energy:** as before, the output caps dump into a short; the ITH clamp stops the controller within a cycle.
- **Start-up ramp:** the linear 0.5 ms ramp overshoots ~0.8 V at its end (and the overshoot is what triggered the idle stall with EXTVCC = 5 V).
  Firmware should round off the end of the ramp or ramp more slowly.
- **Light-load reverse current:** −0.35 A inductor undershoot at light load in pulse-skip; brief negative source current (≤ 1 A, cable/input-cap
  ringing) after load release and shorts. The LM74800 ideal diodes block it from the charger.
- **Clamp margin vs transients:** the ITH clamp at Iset + 3 A also limits how hard the loop can recover from a load step close to Iset
  (t1: Iset 11 A, 10 A step → clamp active during recovery). A larger margin trades short-circuit peak for faster recovery.

## Not yet simulated

- Real INA240 and op-amp input limits (ADA4522 input CM to V+ − 1.5 V = 3.5 V on 5 V — DAC ≤ 2.9 V is fine; a setpoint above ~3.4 V
  made the CC amp misbehave in a test, so keep all DAC setpoints ≤ 2.9 V).
- Output switch (VOM1271 + back-to-back FETs) turn-off during a fault; PD source behaviour (voltage transitions, 5 A limit).
- FET losses/thermal with TI's own MOSFET models (to confirm K_QRR and the VDMOS approximation).
