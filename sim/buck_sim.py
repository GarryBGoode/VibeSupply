"""
LTspice verification of the power stage + external CV/CC loops (see PLAN.md, calc/results.md) — 140 W / 10 A design.

Run:     .venv/Scripts/python sim/buck_sim.py [test ...]      (no args = all tests)
Output:  sim/out/<test>.cir/.raw/.log, sim/plots/<test>.png; results are summarised by hand in sim/results.md

Circuit: LTC7803 (ADI model from the LTspice library), 2x CSD18531Q5A approximated as VDMOS, 300 kHz,
Coilcraft SER2918H-103 10 µH, 2.0 mΩ sense, C1 + RC damper, 0.47 µH post filter, C2 + polymer, 1 mΩ output shunt.
LTC7803 VFB is held at ~0.70 V, EXTVCC from the 12 V aux rail; ITH is driven by two ADA4522 op-amps through a Schottky diode-OR.
The pre-pivot LTC7801 version of this script is in git (d8d0a65).
"""

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from spicelib import RawRead

LTSPICE = r"C:\Program Files\ADI\LTspice\LTspice.exe"
HERE = Path(__file__).parent
OUTDIR, PLOTDIR = HERE / "out", HERE / "plots"
K_DIV = (91.9e3 + 10e3) / 10e3        # CV divider ratio (Vout / Vdivided): 2.9 V DAC -> 29.6 V
R_SNS = 2.0e-3                        # controller sense shunt (2x 4 mΩ): low-duty peak limit 22.5/25/27.5 A, below SER2918H-103 Isat 32 A
H_I = 100 * R_SNS                     # INA240A3 across R_SNS: V per A of inductor current (14.5 A = 2.9 V)
# ITH <-> average inductor current, measured with t0_ith_probe (see sim/results.md)
ITH0, ITH_A_PER_V = 0.45, 25.0   # D <= 0.75; near D = 0.9 the offset rises to ~1.0 V (t088_ith_map)
I_CLAMP_MARGIN = 3.0                  # A above Iset for the cycle-by-cycle ITH clamp
VBE_CLAMP = 0.60

# Compensation (calc §9: CV zero 2.5 kHz / pole 50 kHz / fc 10 kHz, CC zero 2.5 kHz / pole 50 kHz / fc 10 kHz)
COMP = dict(cv_rz="47.5k", cv_cf="1.3n", cv_cp="68p", cc_rin="10k", cc_rz="2.4k", cc_cf="27n", cc_cp="1.3n")

# CSD18531Q5A approximation (datasheet: Rds(on) 4.4/5.8 mΩ @4.5 V, 3.5 mΩ @10 V, Vth 1.8 V, Ciss 3.2 nF,
# Coss 380 pF, Crss 11 pF @30 V, Qg 18 nC @4.5 V, Qoss 32 nC, Qrr 100 nC @300 A/µs).
FET_MODEL = (".model CSD18531Q5A VDMOS(Rg=1.2 Vto=1.8 Rd=2m Rs=0.5m Rb=1m Kp=190 Lambda=0.03 "
             "Cgdmin=11p Cgdmax=1n A=0.25 Cgs=3.2n Cjo=2.5n M=0.5 Is=200p VJ=0.9 N=1.1 TT=12n "
             "mfg=approx Vds=60 Ron=4.4m Qg=18n)")

TEMPLATE = """* {title}
.lib LTC7803.sub
.lib ADA4522-1.sub
{fet_model}
.model CMDSH4E D(Is=5u Rs=0.5 N=1.2 Cjo=15p M=.3 Eg=.69 Xti=2 BV=40)
.model BAT54 D(Is=.1u Rs=2.2 N=1 Cjo=12p M=.3 Eg=.69 Xti=2)
.model 2N3906 PNP(IS=1E-14 VAF=100 BF=200 IKF=0.4 XTB=1.5 BR=4 CJC=4.5E-12 CJE=10E-12 RB=20 RC=0.1 RE=0.1 TR=250E-9 TF=350E-12)
.model SWCLAMP SW(Ron=10m Roff=10Meg Vt=0 Vh=0.3)
.model SWLOAD SW(Ron=1m Roff=1Meg Vt=0.5 Vh=0.1)

* ---- input: source + cable + input caps
Vin vsrc 0 {vin}
Lcab vsrc vcab 0.5u Rser=20m
Cbulk vcab 0 100u Rser=0.2
Rbus vcab vin 1m
Cin vin 0 18u Rser=2m

* ---- controller
* pin order = SpiceOrder of LTC7803.asy (32 positions, gaps are unused)
XU1 senn freq nc3 mode 0 0 run nc8 nc9 nc10 nc11 nc12 nc13 nc14 nc15 nc16 nc17 nc18 intvcc extvcc nc21 vinc bg boost sw tg nc27 nc28 ss ith vfb senp LTC7803
Rvinc vin vinc 10
Cvinc vinc 0 1u
Vext extvcc 0 12
Vrun run 0 PWL(0 0 10u 3.3)
Css ss 0 10n
Rfb1 intvcc vfb 61.9k
Rfb2 vfb 0 10k
Cith ith 0 100p
Rmode intvcc mode {mode_top}
Rfreq freq 0 124k
Cboost boost sw 0.1u
Dboost intvcc boost CMDSH4E
Cintvcc intvcc 0 4.7u

* ---- power stage
M1 vin tg sw CSD18531Q5A
M2 sw bg 0 CSD18531Q5A
L1 sw senp 10u Rser=2.86m
Rsns senp senn {rsns}
C1 senn 0 12u Rser=2m
Cd senn 0 100u Rser=0.1
Lf senn vout 0.47u Rser=1.7m
C2 vout 0 12u Rser=2m
Cel vout 0 100u Rser=0.024
Rsh vout vload 1m
Rbleed vload 0 10k

* ---- sensing (INA240A3 behavioural, gain 100, 400 kHz BW)
Bina isr 0 V=limit(100*(V(senp)-V(senn)),0,4.9)
Risn isr isn 1k
Cisn isn 0 398p

* ---- setpoints (MCU DACs)
Vdacv dacv 0 {dacv}
Vdaci daci 0 {daci}
V5 va5 0 5

{loops}

* ---- regen clamp: on above Vset + 1.3 V (or above 33 V absolute), off 0.6 V lower (hysteretic comparator)
Bclctl clctl 0 V=max(V(vload)-{kdiv}*V(dacv)-1.0, V(vload)-32.7)
Rclamp vload clmp 2.0
Sclamp clmp 0 clctl 0 SWCLAMP

* ---- load
{load}

.tran 0 {tstop} 0 {maxstep}
.options plotwinsize=0
.save V(vout) V(vload) V(senn) V(sw) V(ith) V(cvo) V(cco) V(isn) V(dacv) V(daci) V(vin) V(tg) V(bg) I(L1) I(Rsh) I(Rclamp) I(Lcab)
.end
"""

LOOPS = """* ---- CV error amp (inverting type II on the output divider) -> diode-OR into ITH
Rtop vout cvm 91.9k
Rbot cvm 0 10k
XCV dacv cvm va5 0 cvo ADA4522-1
Rcvz cvm cvz {cv_rz}
Ccvf cvz {fbn_cv} {cv_cf}
Ccvp cvm {fbn_cv} {cv_cp}
Dcv ith cvo BAT54

* ---- CC error amp (on inductor-current sense) -> diode-OR into ITH
Rccin isn ccm {cc_rin}
XCC daci ccm va5 0 cco ADA4522-1
Rccz ccm ccz {cc_rz}
Cccf ccz {fbn_cc} {cc_cf}
Cccp ccm {fbn_cc} {cc_cp}
Dcc ith cco BAT54

* ---- fast current clamp: PNP pulls ITH down when ITH > Vclb + Vbe (Vclb from a 3rd DAC channel)
Qclamp 0 vclb ith 2N3906
Vclb vclb 0 {vclb}
Rclb_dummy vclb 0 1G"""

# ITH forced from a source through 100 Ω (overrides the internal EA): steps to map ITH -> average inductor current
PROBE_LOOPS = """* ---- ITH probe: force ITH in steps, no external loops
Rithf ithf ith 100
Vithf ithf 0 PWL(0 0 0.6m 0 0.61m 0.5 1.2m 0.5 1.21m 0.6 1.8m 0.6 1.81m 0.7 2.4m 0.7 2.41m 0.8 3.0m 0.8 3.01m 0.9 3.6m 0.9 3.61m 1.0 4.2m 1.0)
Vcvo cvo 0 0
Vcco cco 0 0"""
PROBE_LEVELS = [(0.5, 1.2e-3), (0.6, 1.8e-3), (0.7, 2.4e-3), (0.8, 3.0e-3), (0.9, 3.6e-3), (1.0, 4.2e-3)]


@dataclass
class Test:
    name: str
    title: str
    vin: float
    vset: float                 # V (output)
    iset: float                 # A
    load: str                   # SPICE lines
    tstop: float
    windows: dict = field(default_factory=dict)    # name -> (t0, t1) for metrics
    dacv: str = ""              # override (PWL) for the V setpoint
    mode: str = "pulse-skip"
    antiwindup: bool = True
    ith_clamp: bool = True
    probe: bool = False
    probe_map: bool = False
    ith_off: float = ITH0          # ITH at zero current for this test's duty cycle (firmware: from Vset/Vin)
    maxstep: str = "50n"

    def netlist(self) -> str:
        # firmware sequence: RUN at 0, soft start done ~0.6 ms, current limit set at 0.5-0.8 ms, V ramp 0.8-1.3 ms
        dacv = self.dacv or f"PWL(0 0 0.8m 0 1.3m {self.vset / K_DIV:.5f})"
        # Anti-windup: return the compensation networks to the OR node (ITH) instead of each amp's own output.
        fbn_cv, fbn_cc = ("ith", "ith") if self.antiwindup else ("cvo", "cco")
        vclb = (f"PWL(0 0 0.5m 0 0.8m {max(0.0, self.ith_off + (self.iset + I_CLAMP_MARGIN) / ITH_A_PER_V - VBE_CLAMP):.4f})"
                if self.ith_clamp else "5")
        loops = PROBE_LOOPS if self.probe else LOOPS.format(fbn_cv=fbn_cv, fbn_cc=fbn_cc, vclb=vclb, **COMP)
        return TEMPLATE.format(
            title=self.title, fet_model=FET_MODEL, vin=self.vin, dacv=dacv,
            daci=f"PWL(0 0 0.5m 0 0.8m {self.iset * H_I:.5f})",
            rsns=f"{R_SNS}", loops=loops,
            # MODE: internal 100 k to GND; 100 k to INTVCC = pulse-skip, INTVCC = forced continuous, floating = Burst
            mode_top={"pulse-skip": "100k", "fcm": "1", "burst": "1G"}[self.mode],
            load=self.load, tstop=self.tstop, maxstep=self.maxstep, kdiv=f"{K_DIV:.4f}")


def iload_pwl(points):
    return "PWL(" + " ".join(f"{t} {i}" for t, i in points) + ")"


E = 1e-6   # 1 µs edges
TESTS = [
    Test("t0_ith_probe", "ITH forced 0.5 ... 1.0 V, 0.5 Ω load, 30 V in", 30, 24, 10,
         "Rload vload 0 0.5", 4.2e-3, {f"ith_{v:.1f}": (t - 0.2e-3, t) for v, t in PROBE_LEVELS},
         dacv="PWL(0 2.9)", probe=True, ith_clamp=False),
    Test("t050_ith_map", "ITH map at D ≈ 0.50: CV 15.0 V from 30 V, load 2/4/6/8/10 A, no ITH clamp", 30, 15.0, 12,
         f"Iload vload 0 {iload_pwl([(0, 0), (1.5e-3, 0), (1.51e-3, 2), (2.0e-3, 2), (2.01e-3, 4), (2.5e-3, 4), (2.51e-3, 6), (3.0e-3, 6), (3.01e-3, 8), (3.5e-3, 8), (3.51e-3, 10)])}",
         4.0e-3, {f"i_{i}": (t - 0.15e-3, t) for i, t in [(2, 2.0e-3), (4, 2.5e-3), (6, 3.0e-3), (8, 3.5e-3), (10, 4.0e-3)]}, ith_clamp=False, probe_map=True),
    Test("t075_ith_map", "ITH map at D ≈ 0.75: CV 22.5 V from 30 V, load 2/4/6/8/10 A, no ITH clamp", 30, 22.5, 12,
         f"Iload vload 0 {iload_pwl([(0, 0), (1.5e-3, 0), (1.51e-3, 2), (2.0e-3, 2), (2.01e-3, 4), (2.5e-3, 4), (2.51e-3, 6), (3.0e-3, 6), (3.01e-3, 8), (3.5e-3, 8), (3.51e-3, 10)])}",
         4.0e-3, {f"i_{i}": (t - 0.15e-3, t) for i, t in [(2, 2.0e-3), (4, 2.5e-3), (6, 3.0e-3), (8, 3.5e-3), (10, 4.0e-3)]}, ith_clamp=False, probe_map=True),
    Test("t088_ith_map", "ITH map at D ≈ 0.88: CV 26.5 V from 30 V, load 2/4/6/8/10 A, no ITH clamp", 30, 26.5, 12,
         f"Iload vload 0 {iload_pwl([(0, 0), (1.5e-3, 0), (1.51e-3, 2), (2.0e-3, 2), (2.01e-3, 4), (2.5e-3, 4), (2.51e-3, 6), (3.0e-3, 6), (3.01e-3, 8), (3.5e-3, 8), (3.51e-3, 10)])}",
         4.0e-3, {f"i_{i}": (t - 0.15e-3, t) for i, t in [(2, 2.0e-3), (4, 2.5e-3), (6, 3.0e-3), (8, 3.5e-3), (10, 4.0e-3)]}, ith_clamp=False, probe_map=True),
    Test("t1_cv_step", "CV 24 V from 30 V DC, load step 1 A <-> 10 A", 30, 24, 11,
         f"Iload vload 0 {iload_pwl([(0, 0), (1.5e-3, 0), (1.51e-3, 1), (2.5e-3, 1), (2.5e-3+E, 10), (3.5e-3, 10), (3.5e-3+E, 1)])}",
         4.5e-3, {"step_up": (2.45e-3, 3.4e-3), "step_down": (3.45e-3, 4.5e-3), "steady_10A": (3.2e-3, 3.45e-3)}),
    Test("t2_cv_pwm", "CV 24 V from 30 V DC, PWM load 0.5 <-> 8 A at 20 kHz then 2 kHz", 30, 24, 11,
         "Iload vload 0 PWL(0 0 1.5m 0 1.51m 0.5)\n"
         "Ipwm1 vload 0 PULSE(0 7.5 2m 1u 1u 24u 50u 20)\n"
         "Ipwm2 vload 0 PULSE(0 7.5 3.2m 1u 1u 249u 500u 4)",
         5.5e-3, {"pwm_20k": (2.2e-3, 3.0e-3), "pwm_2k": (3.2e-3, 5.2e-3)}),
    Test("t3_cc_short", "CC 5 A at 24 V set (30 V DC), 10 mΩ short at 2.5 ms, released at 4 ms", 30, 24, 5,
         "Iload vload 0 PWL(0 0 1.5m 0 1.51m 1)\n"
         "Sshort vload shrt sctl 0 SWLOAD\nRshort shrt 0 10m\nVsctl sctl 0 PWL(0 0 2.5m 0 2.501m 1 4m 1 4.001m 0)",
         6e-3, {"short": (2.45e-3, 4.0e-3), "release": (3.95e-3, 6e-3)}),
    Test("t4_regen", "Regen: 24 V set from 28 V PD, external source pushes 3.5 A back for 1 ms", 28, 24, 10,
         f"Iload vload 0 {iload_pwl([(0, 0), (1.5e-3, 0), (1.51e-3, 0.5), (2.5e-3, 0.5), (2.5e-3+E, -3.5), (3.5e-3, -3.5), (3.5e-3+E, 0.5)])}",
         4.5e-3, {"regen": (2.45e-3, 3.6e-3), "after": (3.5e-3, 4.5e-3)}),
    Test("t5_26v5_10a", "26.5 V / 10 A from 30 V DC (88 % duty), then load release", 30, 26.5, 11,
         "Rload vload 0 R=if(time<1.5m,1k,if(time<3.5m,2.65,1k))",
         4.5e-3, {"steady": (2.8e-3, 3.4e-3), "release": (3.45e-3, 4.5e-3)}, ith_off=1.0),
    Test("t6_1v_10a", "1 V / 10 A from 31 V (min on-time region)", 31, 1.0, 11,
         "Rload vload 0 R=if(time<1.5m,1k,0.1)",
         3.0e-3, {"steady": (2.3e-3, 3.0e-3)}),
    Test("t7_dropout", "Dropout: 28 V PD in, 28 V set (above Vin) at ~4.5 A, then 26.5 V", 28, 28, 8,
         "Rload vload 0 R=if(time<1.5m,1k,6.2)",
         4.5e-3, {"dropout": (2.3e-3, 3.0e-3), "26v5": (3.8e-3, 4.5e-3)},
         dacv=f"PWL(0 0 0.8m 0 1.3m {28/K_DIV:.5f} 3.0m {28/K_DIV:.5f} 3.3m {26.5/K_DIV:.5f})", ith_off=1.0),
    Test("t8_long_idle", "Long idle: 24 V set from 30 V, output held 0.8 V high by an external source for 3 ms, then 5 A load", 30, 24, 6,
         f"Iload vload 0 {iload_pwl([(0, 0), (1.5e-3, 0), (1.51e-3, 0.5), (2.0e-3, 0.5), (2.01e-3, 0), (5.0e-3, 0), (5.01e-3, 5)])}\n"
         "Bhold vload 0 I=if(time>2m & time<5m, -limit((24.8-V(vload))*20, -0.2, 3), 0)",
         6.5e-3, {"idle": (4.5e-3, 5.0e-3), "resume": (5.0e-3, 6.5e-3)}),
]


def window(t, y, w):
    m = (t >= w[0]) & (t <= w[1])
    return y[m]


def analyse(test: Test, t, get):
    vout, il, ish = get("V(vload)"), get("I(L1)"), get("I(Rsh)")
    ith, icl, iin = get("V(ith)"), get("I(Rclamp)"), -get("I(Lcab)")
    res = {}
    for name, w in test.windows.items():
        v, i, io, th, c, ii = (window(t, x, w) for x in (vout, il, ish, ith, icl, iin))
        res[name] = dict(vmin=v.min(), vmax=v.max(), ilmax=i.max(), ilmin=i.min(), ilmean=i.mean(), iomax=io.max(),
                         iomean=io.mean(), ithmax=th.max(), ithmin=th.min(), ithmean=th.mean(), iclmax=c.max(),
                         iinmin=ii.min())
    return res


def plot(test: Test, t, get):
    PLOTDIR.mkdir(exist_ok=True)
    fig, ax = plt.subplots(4, 1, figsize=(11, 9), sharex=True)
    ms = t * 1e3
    ax[0].plot(ms, get("V(vload)"), lw=0.8, label="Vout (terminals)")
    ax[0].plot(ms, get("V(dacv)") * K_DIV, lw=0.8, ls="--", label="Vset")
    ax[0].set_ylabel("V"); ax[0].legend(loc="upper right")
    ax[1].plot(ms, get("I(L1)"), lw=0.5, label="I(L1) inductor")
    ax[1].plot(ms, get("I(Rsh)"), lw=0.8, label="I out (shunt)")
    ax[1].plot(ms, get("V(daci)") / H_I, lw=0.8, ls="--", label="Iset")
    ax[1].plot(ms, get("I(Rclamp)"), lw=0.8, label="I clamp")
    ax[1].set_ylabel("A"); ax[1].legend(loc="upper right")
    ax[2].plot(ms, get("V(ith)"), lw=0.8, label="ITH")
    ax[2].plot(ms, get("V(cvo)"), lw=0.8, label="CV amp out")
    ax[2].plot(ms, get("V(cco)"), lw=0.8, label="CC amp out")
    ax[2].set_ylabel("V"); ax[2].legend(loc="upper right")
    ax[3].plot(ms, get("V(vin)"), lw=0.8, label="Vin (after cable)")
    ax[3].plot(ms, -get("I(Lcab)"), lw=0.5, label="I in (A)")
    ax[3].set_ylabel("V / A"); ax[3].legend(loc="upper right"); ax[3].set_xlabel("ms")
    fig.suptitle(test.title)
    fig.tight_layout()
    fig.savefig(PLOTDIR / f"{test.name}.png", dpi=110)
    plt.close(fig)


def main(names, simulate=True):
    tests = [t for t in TESTS if not names or t.name in names]
    OUTDIR.mkdir(exist_ok=True)
    procs = []
    for test in tests:                      # LTspice runs are independent -> start them all in parallel
        cir = OUTDIR / f"{test.name}.cir"
        cir.write_text(test.netlist(), encoding="utf-8")
        procs.append((test, subprocess.Popen([LTSPICE, "-b", str(cir)]) if simulate else None))
    summary = {}
    for test, p in procs:
        if p:
            p.wait(timeout=3600)
        cir = OUTDIR / f"{test.name}.cir"
        log = cir.with_suffix(".log").read_text(encoding="latin-1", errors="replace")
        raw = RawRead(str(cir.with_suffix(".raw")))
        t = np.abs(raw.get_trace("time").get_wave())
        get = lambda n, raw=raw: raw.get_trace(n).get_wave()
        plot(test, t, get)
        res = analyse(test, t, get)
        summary[test.name] = res
        el = [l for l in log.splitlines() if "elapsed" in l.lower()]
        print(f"== {test.name}: {test.title}   ({el[0] if el else ''})")
        for k, v in res.items():
            print(f"   {k:12s} " + "  ".join(f"{a}={b:.3f}" for a, b in v.items()))
        if test.probe or test.probe_map:
            pts = [(v["ithmean"], v["ilmean"]) for v in res.values() if v["ilmean"] > 0.5]
            if len(pts) >= 2:
                x, y = np.array(pts).T
                slope, icpt = np.polyfit(x, y, 1)
                print(f"   ITH map: I_L = {slope:.1f} A/V * (ITH - {-icpt/slope:.3f} V)  from {len(pts)} points")
    return summary


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    main([a for a in args if a != "--no-sim"], simulate="--no-sim" not in args)
