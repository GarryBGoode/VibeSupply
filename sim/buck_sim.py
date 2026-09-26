"""
LTspice verification of the power stage + external CV/CC loops (see PLAN.md, calc/results.md).

Run:     .venv/Scripts/python sim/buck_sim.py [test ...]      (no args = all tests)
Output:  sim/out/<test>.cir/.raw/.log, sim/plots/<test>.png, sim/results.md

Circuit: LTC7801 (ADI model from the LTspice library), ISC030N10NM6 approximated as VDMOS,
Coilcraft SER2918H-682 6.8 µH, 2.5 mΩ sense, C1 + RC damper, 1 µH post filter, C2 + electrolytic, 1 mΩ output shunt.
LTC7801 VFB is held at ~0.70 V; ITH is driven by two ADA4522 op-amps through a Schottky diode-OR.
"""

import math
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
K_DIV = (95.3e3 + 5e3) / 5e3          # CV divider ratio (Vout / Vdivided)
R_SNS = 2.5e-3                        # controller sense shunt (2x 5 mΩ): peak limit 26.4/30/33.6 A, below SER2918H Isat 45.9 A
H_I = 50 * R_SNS                      # INA240A2 across R_SNS: V per A of inductor current (20 A = 2.8 V, VREF 2.9 V)
# ITH <-> inductor current (measured with sim/out/ith_probe.cir at 2.5 mΩ, scaled to R_SNS)
ITH0, ITH_A_PER_V = 0.358, 26.2 * 2.5e-3 / R_SNS
I_CLAMP_MARGIN = 3.0                  # A above Iset for the cycle-by-cycle ITH clamp
VBE_CLAMP = 0.60

# Compensation (from calc §9: CV zero 1.25 kHz / pole 25 kHz / fc 5 kHz, CC zero 2.5 kHz / pole 50 kHz / fc 10 kHz)
# CV values re-derived for the revised output filter (0.47 µH post filter, 100 µF/0.1 Ω damper, low-ESR output cap):
# fc ≈ 10 kHz, zero 2.5 kHz, pole 40 kHz.
COMP = dict(cv_rz="35.7k", cv_cf="1.8n", cv_cp="100p", cc_rin="10k", cc_rz="2.5k", cc_cf="25.4n", cc_cp="1.27n")

# ISC030N10NM6 approximation (datasheet: Rds 2.6/3.0 mΩ, Vth 2.8 V, Ciss 4 nF, Coss 900 pF, Crss 15 pF @50 V,
# Qg 55 nC, Qrr ~266 nC @1000 A/µs). Parameters scaled from LTspice's Infineon BSC060N10NS3 VDMOS model.
FET_MODEL = (".model ISC030N10NM6 VDMOS(Rg=1.05 Vto=2.8 Rd=1.6m Rs=0.4m Rb=0.8m Kp=350 Lambda=0.03 "
             "Cgdmin=15p Cgdmax=2n A=0.25 Cgs=3.9n Cjo=5n M=0.35 Is=200p VJ=0.9 N=1.1 TT=10n "
             "mfg=approx Vds=100 Ron=3m Qg=55n)")

TEMPLATE = """* {title}
.lib LTC7801.sub
.lib ADA4522-1.sub
{fet_model}
.model BAT54 D(Is=.1u Rs=2.2 N=1 Cjo=12p M=.3 Eg=.69 Xti=2)
.model 2N3906 PNP(IS=1E-14 VAF=100 BF=200 IKF=0.4 XTB=1.5 BR=4 CJC=4.5E-12 CJE=10E-12 RB=20 RC=0.1 RE=0.1 TR=250E-9 TF=350E-12)
.model SWCLAMP SW(Ron=10m Roff=10Meg Vt=0 Vh=0.3)
.model SWLOAD SW(Ron=1m Roff=1Meg Vt=0.5 Vh=0.1)

* ---- input: source + cable + input caps
Vin vsrc 0 {vin}
Lcab vsrc vcab 0.5u Rser=20m
Cbulk vcab 0 100u Rser=0.2
Rbus vcab vin 1m
Cin vin 0 20u Rser=2m

* ---- controller
* pin order = SpiceOrder of LTC7801.asy (39 positions, gaps are unused)
XU1 0 nc2 senp senn ss vfb ith mode nc9 {cpump} nc11 nc12 0 pgood nc15 nc16 freq intvcc intvcc tg sw boost nc23 bg nc25 drvcc nc27 drvcc nc29 vinc nc31 extvcc nc33 run nc35 nc36 nc37 intvcc 0 LTC7801
Rvinc vin vinc 10
Cvinc vinc 0 1u
Vext extvcc 0 12
Vrun run 0 PWL(0 0 10u 3.3)
Css ss 0 10n
Rss intvcc ss 330k
Rfb1 intvcc vfb 61.9k
Rfb2 vfb 0 10k
Cith ith 0 100p
Rmode1 intvcc mode {mode_top}
Rmode2 mode 0 100k
Rpg intvcc pgood 100k
Rfreq freq 0 71.5k
Cboost boost sw 0.1u
Cdrvcc drvcc 0 4.7u
Cintvcc intvcc 0 1u

* ---- power stage
M1 vin tg sw ISC030N10NM6
M2 sw bg 0 ISC030N10NM6
L1 sw senp 6.8u Rser=2.86m
Rsns senp senn {rsns}
C1 senn 0 11u Rser=1.5m
Cd senn 0 100u Rser=0.1
Lf senn vout 0.47u Rser=1.7m
C2 vout 0 11u Rser=1.5m
Cel vout 0 100u Rser=0.024
Rsh vout vload 1m
Rbleed vload 0 10k

* ---- sensing (INA240A2 behavioural, 400 kHz BW)
Bina isr 0 V=limit(50*(V(senp)-V(senn)),0,4.9)
Risn isr isn 1k
Cisn isn 0 398p

* ---- setpoints (MCU DACs)
Vdacv dacv 0 {dacv}
Vdaci daci 0 {daci}
V5 va5 0 5

* ---- CV error amp (inverting type II on the output divider) -> diode-OR into ITH
Rtop vout cvm 95.3k
Rbot cvm 0 5k
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
Rclb_dummy vclb 0 1G

* ---- regen clamp: on above Vset + 1.3 V, off below Vset + 0.7 V (hysteretic comparator)
Bclctl clctl 0 V=V(vload)-{kdiv}*V(dacv)-1.0
Rclamp vload clmp 2.0
Sclamp clmp 0 clctl 0 SWCLAMP

* ---- load
{load}

.tran 0 {tstop} 0 {maxstep}
.options plotwinsize=0
.save V(vout) V(vload) V(senn) V(sw) V(ith) V(cvo) V(cco) V(isn) V(dacv) V(daci) V(vin) I(L1) I(Rsh) I(Rclamp) I(Lcab)
.end
"""


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
    cpump: bool = True
    antiwindup: bool = True
    ith_clamp: bool = True
    maxstep: str = "50n"

    def netlist(self) -> str:
        # firmware sequence: RUN at 0, controller ready ~0.65 ms, current limit set at 0.5-0.8 ms, V ramp 0.8-1.3 ms
        dacv = self.dacv or f"PWL(0 0 0.8m 0 1.3m {self.vset / K_DIV:.5f})"
        # Anti-windup: return the compensation networks to the OR node (ITH) instead of each amp's own output.
        # The amp that is not in control then keeps an integrator state that tracks the real ITH, so it can take
        # over after only its output slew (~3 µs), not after unwinding a capacitor from the rail.
        fbn_cv, fbn_cc = ("ith", "ith") if self.antiwindup else ("cvo", "cco")
        return TEMPLATE.format(
            title=self.title, fet_model=FET_MODEL, vin=self.vin, dacv=dacv,
            daci=f"PWL(0 0 0.5m 0 0.8m {self.iset * H_I:.5f})",
            vclb=f"PWL(0 0 0.5m 0 0.8m {max(0.0, ITH0 + (self.iset + I_CLAMP_MARGIN) / ITH_A_PER_V - VBE_CLAMP):.4f})" if self.ith_clamp else "5",
            rsns=f"{R_SNS}",
            mode_top={"pulse-skip": "100k", "fcm": "1", "burst": "1G"}[self.mode],
            cpump="intvcc" if self.cpump else "0",
            fbn_cv=fbn_cv, fbn_cc=fbn_cc, load=self.load, tstop=self.tstop, maxstep=self.maxstep,
            kdiv=f"{K_DIV:.4f}", **COMP)


def iload_pwl(points):
    return "PWL(" + " ".join(f"{t} {i}" for t, i in points) + ")"


E = 1e-6   # 1 µs edges
TESTS = [
    Test("t1_cv_step", "CV 24 V, load step 1 A <-> 10 A", 48, 24, 15,
         f"Iload vload 0 {iload_pwl([(0, 0), (1.5e-3, 0), (1.51e-3, 1), (2.5e-3, 1), (2.5e-3+E, 10), (3.5e-3, 10), (3.5e-3+E, 1)])}",
         4.5e-3, {"step_up": (2.45e-3, 3.4e-3), "step_down": (3.45e-3, 4.5e-3), "steady_10A": (3.2e-3, 3.45e-3)}),
    Test("t2_cv_pwm", "CV 24 V, PWM load 0.5 <-> 8 A at 20 kHz then 2 kHz", 48, 24, 15,
         "Iload vload 0 PWL(0 0 1.5m 0 1.51m 0.5)\n"
         "Ipwm1 vload 0 PULSE(0 7.5 2m 1u 1u 24u 50u 20)\n"
         "Ipwm2 vload 0 PULSE(0 7.5 3.2m 1u 1u 249u 500u 4)",
         5.5e-3, {"pwm_20k": (2.2e-3, 3.0e-3), "pwm_2k": (3.2e-3, 5.2e-3)}),
    Test("t2b_pwm_nocpump", "t2 with CPUMP_EN=GND (boost refresh)", 48, 24, 15,
         "Iload vload 0 PWL(0 0 1.5m 0 1.51m 0.5)\n"
         "Ipwm2 vload 0 PULSE(0 7.5 2.0m 1u 1u 249u 500u 6)",
         5.2e-3, {"pwm_2k": (2.0e-3, 5.2e-3)}, cpump=False),
    Test("t2c_pwm_burst", "t2 in Burst mode", 48, 24, 15,
         "Iload vload 0 PWL(0 0 1.5m 0 1.51m 0.5)\n"
         "Ipwm2 vload 0 PULSE(0 7.5 2.0m 1u 1u 249u 500u 6)",
         5.2e-3, {"pwm_2k": (2.0e-3, 5.2e-3)}, mode="burst"),
    Test("t2d_pwm_ref", "t2 reference (pulse-skip, charge pump)", 48, 24, 15,
         "Iload vload 0 PWL(0 0 1.5m 0 1.51m 0.5)\n"
         "Ipwm2 vload 0 PULSE(0 7.5 2.0m 1u 1u 249u 500u 6)",
         5.2e-3, {"pwm_2k": (2.0e-3, 5.2e-3)}),
    Test("t3_cc_short", "CC 5 A at 24 V set, 10 mΩ short at 2.5 ms, released at 4 ms", 48, 24, 5,
         "Iload vload 0 PWL(0 0 1.5m 0 1.51m 1)\n"
         "Sshort vload shrt sctl 0 SWLOAD\nRshort shrt 0 10m\nVsctl sctl 0 PWL(0 0 2.5m 0 2.501m 1 4m 1 4.001m 0)",
         6e-3, {"short": (2.45e-3, 4.0e-3), "release": (3.95e-3, 6e-3)}),
    Test("t4_regen", "Regen: 24 V set, external source pushes 4 A back for 1 ms", 48, 24, 10,
         f"Iload vload 0 {iload_pwl([(0, 0), (1.5e-3, 0), (1.51e-3, 0.5), (2.5e-3, 0.5), (2.5e-3+E, -3.5), (3.5e-3, -3.5), (3.5e-3+E, 0.5)])}",
         4.5e-3, {"regen": (2.45e-3, 3.6e-3), "after": (3.5e-3, 4.5e-3)}),
    Test("t5_46v_20a", "46 V / 20 A (DC input 48 V), then load release", 48, 46, 20.5,
         "Rload vload 0 {PWL}".replace("{PWL}", "R=if(time<1.5m,1k,if(time<3.5m,2.3,1k))"),
         4.5e-3, {"steady": (2.8e-3, 3.4e-3), "release": (3.45e-3, 4.5e-3)}),
    Test("t6_1v_10a", "1 V / 10 A from 48 V (min on-time region)", 48, 1.0, 12,
         "Rload vload 0 R=if(time<1.5m,1k,0.1)",
         3.0e-3, {"steady": (2.3e-3, 3.0e-3)}),
]


def run(test: Test):
    OUTDIR.mkdir(exist_ok=True)
    cir = OUTDIR / f"{test.name}.cir"
    cir.write_text(test.netlist(), encoding="utf-8")
    subprocess.run([LTSPICE, "-b", str(cir)], check=True, timeout=1800)
    log = cir.with_suffix(".log").read_text(encoding="latin-1", errors="replace")
    raw = RawRead(str(cir.with_suffix(".raw")))
    t = np.abs(raw.get_trace("time").get_wave())
    get = lambda n: raw.get_trace(n).get_wave()
    return t, get, log


def window(t, y, w):
    m = (t >= w[0]) & (t <= w[1])
    return y[m]


def analyse(test: Test, t, get):
    vout, il, ish = get("V(vload)"), get("I(L1)"), get("I(Rsh)")
    ith, icl = get("V(ith)"), get("I(Rclamp)")
    res = {}
    for name, w in test.windows.items():
        v, i, io, th, c = (window(t, x, w) for x in (vout, il, ish, ith, icl))
        res[name] = dict(vmin=v.min(), vmax=v.max(), ilmax=i.max(), ilmin=i.min(), iomax=io.max(),
                         iomean=io.mean(), ithmax=th.max(), ithmin=th.min(), iclmax=c.max())
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
    return summary


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    main([a for a in args if a != "--no-sim"], simulate="--no-sim" not in args)
