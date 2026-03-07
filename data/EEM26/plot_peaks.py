import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.lines import Line2D

np.random.seed(99)

n_days = 7
n_hours = 24

base = np.random.uniform(0.2, 0.9, (n_days, n_hours))
for h in range(7, 10):
    base[:, h] += np.random.uniform(0.2, 0.5, n_days)

base[1, 8]  = 3.70
base[1, 9]  = 3.45
base[4, 19] = 3.20
base[3, 9]  = 2.65
base[6, 14] = 2.10
for d in [0, 2, 5, 6]:
    base[d, :] = np.clip(base[d, :], 0.2, 1.8)
data = np.clip(base, 0.05, None)

daily_max_hours = np.argmax(data, axis=1)
daily_max_vals  = data[np.arange(n_days), daily_max_hours]

flat_idx = np.argsort(data.flatten())[::-1][:3]
monthly_peak_days  = flat_idx // n_hours
monthly_peak_hours = flat_idx % n_hours
monthly_peak_vals  = data[monthly_peak_days, monthly_peak_hours]

top3_daily_idx = np.argsort(daily_max_vals)[::-1][:3]

IEEE_COL = 3.5
FS = 7

fig = plt.figure(figsize=(IEEE_COL, 3.2))
# 3D axes takes left ~72% of width, leaving right side for legend
ax = fig.add_axes([0.02, 0.38, 0.78, 0.5], projection='3d')

days  = np.arange(1, n_days + 1)
hours = np.arange(n_hours)
dx, dy = 0.7, 0.7

for d_idx, day in enumerate(days):
    for h in hours:
        ax.bar3d(day - dx/2, h - dy/2, 0, dx, dy, data[d_idx, h],
                 color='steelblue', alpha=0.95, shade=True,
                 edgecolor='steelblue', linewidth=0.05)

for d_idx in range(n_days):
    h = daily_max_hours[d_idx]
    v = daily_max_vals[d_idx]
    ax.scatter(days[d_idx], h, v + 0.05, color='orange', s=12,
               marker='o', zorder=10, depthshade=False)

for i in range(len(monthly_peak_days)):
    d = monthly_peak_days[i] + 1
    h = monthly_peak_hours[i]
    v = monthly_peak_vals[i]
    ax.scatter(d, h, v + 0.05, color='red', s=14,
               marker='s', zorder=10, depthshade=False)

for idx in top3_daily_idx:
    d = days[idx]
    h = daily_max_hours[idx]
    v = daily_max_vals[idx]
    ax.scatter(d, h, v + 0.15, color='green', s=12,
               marker='^', zorder=11, depthshade=False)

ax.set_xlabel('Day in billing month\n(example window)', labelpad=2, fontsize=FS)
ax.set_ylabel('Hour of day', labelpad=2, fontsize=FS)
ax.set_xticks(days)
ax.set_yticks([0, 5, 10, 15, 20])
ax.tick_params(axis='both', labelsize=FS - 1, pad=1)
ax.set_zlim(0, 4.0)
ax.set_zticks([0.0, 1.0, 2.0, 3.0])
ax.view_init(elev=22, azim=-55)
ax.grid(True, linestyle='--', linewidth=0.3, alpha=0.6)

# Annotation at top
fig.text(0.01, 0.85,
         "3 design dimensions: "
         r"LEVEL: $\mu^{pk}$ (SEK/kW-month) \n" 
         "WINDOW: daily-reset vs monthly-pool\n"
         "AVERAGING: |K|=3 peaks",
         va='top', ha='left', fontsize=FS, family='monospace')

# Legend placed on the right side to fill blank space
legend_elements = [
    Line2D([0], [0], marker='o', color='w', markerfacecolor='orange',
           markersize=6, label='Daily maxima\n(daily-reset)'),
    Line2D([0], [0], marker='^', color='w', markerfacecolor='green',
           markersize=6, label='Daily-reset\nbilled peaks\n(Top-3)'),
    Line2D([0], [0], marker='s', color='w', markerfacecolor='red',
           markersize=6, label='Monthly-pool\nbilled peaks\n(Top-3)'),
]
fig.legend(handles=legend_elements,
           loc='center left',
           bbox_to_anchor=(0.9, 0.44),
           ncol=1, frameon=True, fontsize=FS,
           handletextpad=0.3, labelspacing=0.6,
           borderpad=0.4)

plt.savefig('tariff_peaks_3d.png', dpi=300, bbox_inches='tight')
plt.savefig('tariff_peaks_3d.pdf', bbox_inches='tight')
print("Saved.")