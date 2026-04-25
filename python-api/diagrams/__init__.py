# Engineering diagram generators — Phase 10
# Each module returns an SVG string from calc inputs + results.
# matplotlib Agg backend — no display required (server-safe).
import matplotlib
matplotlib.use("Agg")
