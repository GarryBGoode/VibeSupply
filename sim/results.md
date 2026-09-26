# LTspice verification — results

Simulations by `sim/buck_sim.py`. Re-run everything with `.venv/Scripts/python sim/buck_sim.py`. Tests run in parallel, about 8 min in total.
Pass test names to run a subset, or `--no-sim` to re-plot existing results. Netlists, raw data and logs are in `sim/out/`; plots are in `sim/plots/`.

Run on LTspice 26.1.1, 2026-09-26. Last full run uses the LCSC-stocked parts: Coilcraft SER2918H-682, 2.5 mΩ sense resistor, FXL1040-R47 post filter, 24 mΩ polymer output cap, 2 Ω clamp.

## What is simulated

- **Controller:** ADI's LTC7801 model from the LTspice library (encrypted, pin-accurate). ISC030N10NM6 MOSFETs are modelled as an approximate VDMOS built from the datasheet values.
- **Power stage:** Coilcraft SER2918H-682 6.8 µH (2.86 mΩ), 2.5 mΩ sense resistor (2× 5 mΩ).
- **Output filter:** C1 is 11 µF of ceramics plus a 100 µF / 0.1 Ω damper. The post-filter inductor is **0.47 µH** (1.7 mΩ). C2 is 11 µF of ceramics plus a 100 µF / 24 mΩ polymer. The output shunt is 1 mΩ.
- **Input:** a source with 0.5 µH / 20 mΩ of cable, 100 µF bulk, and 20 µF of ceramics.
- **Control scheme as planned:**
  - VFB held at 0.695 V from INTVCC (61.9 k / 10 k).
  - Two ADA4522 op-amps (CV and CC) pull ITH down through BAT54 diodes.
  - Anti-windup: each op-amp's compensation network returns to ITH, not to its own output.
  - CC loop senses inductor current with an INA240A2 (behavioural model) across the 2.5 mΩ resistor.
  - **Fast current clamp:** a PNP from ITH to GND, with its base driven by a third DAC channel. It limits ITH, and so the cycle-by-cycle peak current, to Iset + 3 A.
  - Regen clamp: a hysteretic switch with 2 Ω. It turns on at Vset + 1.3 V and off at Vset + 0.7 V.
  - Pulse-skip mode; charge pump enabled; REGSD defeated with 330 k from INTVCC to SS.
- **Firmware sequence modelled:** RUN at t = 0 (the controller is ready at about 0.65 ms). The current setpoint ramps over 0.5–0.8 ms, and the voltage setpoint over 0.8–1.3 ms.

### Component values used

| Block | Values |
|---|---|
| CV amp | divider 95.3 k / 5 k (÷20.06); Rz 35.7 k, Cf 1.8 nF, Cp 100 pF; networks return to ITH |
| CC amp | Rin 10 k; Rz 2.5 k, Cf 25.4 nF, Cp 1.27 nF; networks return to ITH |
| ITH | 100 pF to GND; PNP clamp (2N3906 in the sim, BC857 class for real) |
| LTC7801 | RFREQ 71.5 k (≈300 kHz), SS 10 nF + 330 k to INTVCC, MODE 100 k/100 k (pulse-skip), DRVSET = DRVUV = CPUMP_EN = INTVCC, EXTVCC 12 V |

The frequency-domain model (calc §9) suggests Cf ≈ 1.4 nF for exactly 10 kHz. With 1.8 nF the crossover is about 8 kHz. Either is fine; the final value can be tuned on hardware.

## Results

| Test | What | Result |
|---|---|---|
| t1 | CV 24 V, load step 1 ↔ 10 A (1 µs edges) | Dip **0.63 V** (23.37 V), overshoot on release **0.60 V**, recovery ≈ 150 µs, no ringing. Steady ripple at 10 A: 9 mV pp |
| t2 | CV 24 V, PWM load 0.5 ↔ 8 A at 20 kHz and 2 kHz | 20 kHz: 23.74–24.26 V (±0.26 V), loop stays well-behaved. 2 kHz: each edge behaves like t1 (22.85–24.51 V). No sustained oscillation |
| t3 | CC 5 A, 10 mΩ short, then released | The controller stops within ~10 µs (ITH clamp). Output-cap discharge spike, then **≈19 A decaying to 5 A over ~0.5 ms** (stored energy, see below). CC→CV on release: overshoot 0.85 V |
| t4 | Regen: 3.5 A pushed back for 1 ms at 24 V | Buck stops (pulse-skip, no reverse current), **no current back to the input**. The clamp chops at ~25 V (12.6 A peaks with 2 Ω, ≈30 % duty) |
| t5 | 46 V / 20 A from 48 V, load release | Steady 45.96–45.99 V (37 mV pp) at 20 A. 0→20 A step: −2 V dip; the ITH clamp holds IL ≤ ~26 A. Release: +1.3 V |
| t6 | 1 V / 10 A from 48 V (below the min-on-time limit) | Regulates at 0.98–1.00 V, 17 mV pp — pulse-skipping is benign |

Plots: `sim/plots/t1_cv_step.png` … `t6_1v_10a.png`; zooms `zoom_t3_short.png`, `zoom_t2_glitch.png`.

## Design changes that came out of the simulation

1. **Anti-windup = compensation networks return to ITH.** The first try, a PNP clamp from the amp output to its summing node, conducted through its collector-base junction whenever the setpoint was above ITH, so it clamped the loop. It was removed.
2. **CV loop bandwidth 5 → ~10 kHz** by changing the output filter:
   - post-filter inductor 1 µH → 0.47 µH;
   - C1 damper 47 µF / 0.33 Ω → 100 µF / 0.1 Ω;
   - low-ESR (≈50 mΩ) output capacitor.

   The load-step dip halved (1.4 V → 0.65 V for 9 A). Ripple estimate is 10 mV pp.
   Sensing the voltage at C1, before the post filter, was also tried and is worse: the post-filter anti-resonance pushes the crossover to 70–90 kHz.
3. **Fast ITH clamp (new, needs a 3rd DAC channel).** Without it, a short made the CV loop demand maximum current, and the inductor reached the controller's ~42 A limit within ~5 µs. With it, the controller stops at Iset + 3 A.
4. **Inductor → Coilcraft SER2918H-682** (Würth not stocked at LCSC). Its 45.9 A Isat keeps the 2.5 mΩ sense resistor (max limit 33.6 A) safely below saturation. The Würth part would have needed 2.8 mΩ.
5. **REGSD must be defeated** (330 k from INTVCC to SS). Otherwise the LTC7801 shuts itself down whenever EXTVCC isn't switched over, for example when running from a low DC input with no 12 V aux rail.

## Things the simulation shows that firmware or hardware must handle

- **Short-circuit energy:** the output capacitors (≈ 220 µF) dump into a short. In the sim that's ~1.8 kA for a few µs through 11 mΩ; real wiring limits it. The energy in the inductors then decays slowly, because the shorted output leaves almost no voltage across them: ~18 A → Iset over ~0.5 ms.
  This is physics, not a control problem. Every switching bench supply with output caps does it. Mitigations are less C (worse transients) or a faster output switch to disconnect.
- **Start-up ramp:** a linear 0.5 ms ramp overshoots ~1 V at its end. Firmware should round off the end of the ramp (S-curve), or ramp more slowly.
- **ITH-clamp calibration:** ITH ↔ current mapping is ITH ≈ 0.358 V + I / 26.2 A/V at 2.5 mΩ (from the model). The clamp level varies with duty cycle (slope compensation) and part tolerance. Firmware should calibrate it at run time (read ITH and the INA240 output with the MCU ADC) and keep a generous margin.
- **Small reverse current at light load:** the inductor current undershoots below zero before the bottom FET turns off. That's −0.65 A at 24 V and −2.9 A at 46 V, consistent with a few hundred ns of reverse-comparator delay. The energy is tiny and goes to the input caps; the LM74800 blocks it from the charger.
- **Simulation glitch (resolved as a timestep artifact):** the t2 run at 50 ns max timestep shows one ~4 µs event where the bottom FET stays on at light load (−10 A), and it reproduces at that exact timing. Re-running the same circuit with a 20 ns max timestep (`out/t2_glitch_diag.cir`, gate signals saved) shows no event: min IL −0.66 A, the normal light-load undershoot. Variants t2b/t2c/t2d didn't show it either. Treat it as numerical, not circuit behaviour.

## Not yet simulated

- Real INA240 and op-amp input limits. ADA4522 input CM goes to V+ − 1.5 V = 3.5 V on 5 V, which is fine for DAC ≤ 2.9 V. The final op-amp choice is still open.
- The output switch (Si8751 + back-to-back FETs) and its turn-off during a fault.
- PD source behaviour (voltage transitions during operation, 5 A current limit).
- Loss/thermal verification with Infineon's own MOSFET model (to confirm K_QRR).
