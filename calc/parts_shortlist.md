# Parts shortlist (JLC/LCSC)

Stock and price come from the jlcsearch.tscircuit.com mirror of the JLC parts database, taken 2026-09-26. Prices are for qty 1, in USD.
Raw query output is in `stock_check*.txt`. The mirror can lag the live site, so re-check before ordering.

## Power path

| Function | Part | LCSC | Stock | $ | Notes |
|---|---|---|---|---|---|
| PD controller | TI TPS26750SRSMR | C42166327 | 517 | 3.18 | VQFN-32 4×4 |
| EPR front end | TI TPD4S480RUKR | C43131250 | 3323 | 1.83 | QFN-20 3×3 |
| PD config EEPROM | AT24C512C-SSHD-T (64 KB) | C12371 | 47k | 0.54 | SOIC-8 (hand-solderable) |
| Ideal diode + switch ×2 | TI LM74800QDRRRQ1 | C3215600 | 2974 | 2.44 | WSON-12 3×3 (non-Q1 C7216630 also stocked) |
| Input/switch FETs | Infineon IPT015N10N5 (TOLL, 1.5 mΩ) | C108964 | 65k | 1.34 | DC-in path ×2, output switch ×2, clamp FET; the USB path could use a smaller FET |
| Buck controller | ADI LTC7801EFE#PBF (TSSOP-24-EP) | C690198 | 21 | 20.34 | **expensive and low stock — buy early, plus a spare**. QFN: C690200 (58 pcs) |
| Buck FETs ×2 | Infineon ISC030N10NM6ATMA1 | C3278643 | 3923 | 1.87 | fallback BSC040N10NS5 C534334 (19k, $1.18) |
| Main inductor | Coilcraft SER2918H-682KL (6.8 µH, 45.9 A Isat, 2.86 mΩ) | C3911802 | 33 | 6.15 | backup HCZC-2918HT-6R8-M C53202464 (2.45 mΩ, 45 A); Würth 7443640680B only via Mouser/Digi-Key |
| Post-filter inductor | FXL1040-R47-M (470 nH, 1.7 mΩ, 30 A/40 A) | C475921 | 192 | 0.28 | alt. FAUL1040-R47MT C5298178 |
| Sense resistor | 2× HoJLR2512-3W-5mR-1% in parallel (= 2.5 mΩ) | C2903482 | 83k | 0.10 | |
| Output / input shunt | HoJLR2512-3W-1mR-1% | C2903470 | 226k | 0.09 | 2-terminal: route Kelvin sense traces from the pads |
| MLCC 4.7 µF 100 V 1210 | Murata GCM32DC72A475KE02L (X7S) | C913445 | 24.6k | 0.57 | alt. Taiyo Yuden HMK325C7475KN-TE C697607 |
| Input bulk | LKME1402A101MF 100 µF 100 V (THT D10×14, 1.04 A) | C443138 | 25k | 0.17 | |
| Output polymer | PCR1J101MCL1GS 100 µF 63 V 24 mΩ (SMD) | C5154285 | 1012 | 2.29 | |
| C1 damper | SPZ1JM101G12O00RAXXX 100 µF 63 V polymer + 0.1 Ω 2512 | C2691842 | 12.5k | 0.33 | series R sets the damping precisely |
| Clamp resistor | Vishay LTO100F2R000JTE3 (2 Ω, 100 W TO-247) | C3546229 | 23 | 12.41 | 3.3 Ω not stocked; 2 Ω works (absorbs 50 W down to 10 V) |
| Fuse | Littelfuse 0997030.WXN (30 A, **58 V**, 1.85 mΩ) | C207030 | 7.9k | 0.53 | + PCB fuse holder (to pick) |
| Input TVS | SMCJ54A (1.5 kW) | C438116 | 6k | 0.10 | |
| USB-C PD port | GCT USB4105-GF-A (48 V / 5 A rated) | C3020560 | 11.5k | 1.03 | |
| XT60 | XT60PW-M (horizontal PCB) | C98732 | 54k | 0.60 | DC input and output |

## Control / sensing

| Function | Part | LCSC | Stock | $ | Notes |
|---|---|---|---|---|---|
| CV/CC op-amps | ADI ADA4522-2ARZ (SOIC-8) | C403697 | 11k | 3.22 | the part used in the LTspice runs |
| Current amp (CC loop) | TI INA240A2PWR (TSSOP-8) | C129949 | 6.9k | 2.78 | SOIC-8 version C2060768 is cheaper |
| Metering ×2 | TI INA228AIDGSR (VSSOP-10) | C2887910 | 1046 | 5.45 | |
| ITH clamp PNP | BC857B (SOT-23) | C556165 | 149k | 0.01 | |
| OR diodes | BAT54 (SOT-23) | C19726 | 819k | 0.03 | |
| Output switch driver | Vishay VOM1271T (photovoltaic, fast turn-off) | C146286 | 12k | 1.65 | 8.4 V Voc, 15 µA → ~30 ms turn-on with 2× IPT015N10N5. Si8751 isn't stocked |
| Optional 16-bit DAC | TI DAC80502DRXR | C1880990 | 2.1k | 6.73 | footprint only |

## MCU, isolation, housekeeping, UI

| Function | Part | LCSC | Stock | $ | Notes |
|---|---|---|---|---|---|
| MCU | STM32G474RET6 (LQFP-64) | C521608 | 704 | 8.60 | |
| USB isolator | ADuM3160BRWZ-RL (SOIC-16W) | C284149 | 5k | 5.77 | |
| Isolated 5 V | B0505S-1WR3 (SIP-4) | C7465178 | 93k | 0.75 | |
| Logic buck (4.2–80 V) | TI LMR38010SDDAR | C5219310 | 2.5k | 0.92 | |
| 12 V aux buck (6–100 V) | TI LM5164DDAR | C477928 | 6.3k | 1.36 | |
| I/O expander (UI board) | TCA9535PWR | C130204 | 23k | 1.08 | |
| Encoders | Alps EC11E15244G1 | C370970 | 5.5k | 2.26 | |
| Display | HS20HS072RX 2.0" 320×240 ST7789 (bare panel) | C5329582 | 2.7k | 3.77 | needs an FPC connector on the UI board |
| USB-C data port | TYPE-C 16PIN 2MD(073) | C2765186 | 1.2M | 0.07 | |

## Not stocked at LCSC / needs a decision
- Würth 7443640680B: replaced by the Coilcraft SER2918H-682 (+1 W copper loss). Could be consigned from Mouser.
- Si8751/Si8752: replaced by the VOM1271.
- 3.3 Ω LTO100: replaced by 2 Ω.
- A PCB holder for the blade fuse, a 4 mm binding-post solution, a fan header, and the heatsink are still to pick.
