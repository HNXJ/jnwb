# GAMMA Protocol: Layer-Specific Effective Impedance Estimation

**Objective**: Extract the relative effective complex impedance gradient $Z_{eff}(z, \omega)$ across cortical layers using spontaneous in vivo recordings, bypassing the uniform-conductivity assumption of standard Current Source Density (CSD) analysis.

## 1. ingredient-information
- **Hardware**: DBC128-1 laminar probe (128 channels, $C = 128$) with $\Delta z = 40\mu\text{m}$ spatial spacing. Intan recording system.
- **Data Volume**: Minimum 1000 seconds of continuous recording.
- **Data Matrices**:
    - $X \in \mathbb{R}^{C \times T_{30k}}$: Raw wideband recording (30 kHz).
    - $L \in \mathbb{R}^{C \times T_{1k}}$: Low-pass filtered Local Field Potential (1 kHz).
    - $SPK \in \mathbb{R}^{C \times T_{1k}}$: Convolved spiking activity / MUAe (1 kHz), acting as our proxy for the biological ground-truth current source $I_m$.
- **Spatial Operator**: $D_z^2 \in \mathbb{R}^{C \times C}$: Spatial finite-difference 1D Laplacian matrix (main diagonal $-2/\Delta z^2$, adjacent diagonals $1/\Delta z^2$).

## 2. problem-solution-chain
- **Problem**: Standard CSD assumes uniform tissue conductivity ($\sigma$). We must invert this to find the actual layered impedance by treating the tissue as a Linear Time-Invariant (LTI) filter that distorts the LFP.
- **Solution**: Treat locally detected spiking ($SPK$) as the "ground truth" biological current, and calculate the transfer function (impedance) that maps this source to the observed field gradient.
    - **Step A: The Naive Spatial Gradient**
      Calculate what the volumetric current source would be if the tissue were perfectly uniform ($\sigma = 1$):
      $$C_{naive} = -D_z^2 L$$
    - **Step B: Frequency Domain Transformation**
      Compute the Fourier transforms over overlapping time windows to capture capacitive filtering:
      $$\tilde{C}(\omega) = \mathcal{F}_t \{ C_{naive} \} \quad \text{and} \quad \tilde{S}(\omega) = \mathcal{F}_t \{ SPK \}$$
    - **Step C: The Complex Impedance Tensor (Wiener-Hopf Estimation)**
      From the Poisson equation, the effective impedance $Z_{eff} = 1/\sigma$ is the transfer function mapping $\tilde{S}$ to $\tilde{C}$. Using Welch's method across the 1000s windows, calculate the Cross-Spectral ($P_{SC}$) and Auto-Spectral ($P_{SS}$) densities:
      $$Z_{eff}(z, \omega) = \frac{P_{SC}(z, \omega)}{P_{SS}(z, \omega)} = \frac{\langle \tilde{S}(z, \omega) \odot \tilde{C}^*(z, \omega) \rangle}{\langle \tilde{S}(z, \omega) \odot \tilde{S}^*(z, \omega) \rangle}$$
      (where $\odot$ is the Hadamard product and $\langle \cdot \rangle$ is the time-window average).

### Output Interpretation:
- Yields a $128 \times \text{Freq}$ complex tensor.
- **Magnitude $|Z_{eff}|$**: Maps the relative impedance layer-by-layer.
- **Phase $\angle Z_{eff}$**: Reveals the local reactive/capacitive load.

## 3. code-repo-tasks
- [ ] Initialize a Python/JAX script to handle the large-scale matrix operations (avoiding memory bottlenecks for 1000s of 30kHz data).
- [ ] Implement the finite-difference matrix $D_z^2$ with appropriate edge-padding for the top and bottom channels.
- [ ] Write a vectorized Welch's overlapping window function utilizing `scipy.signal.csd` and `scipy.signal.welch` (or JAX equivalents) to compute $P_{SC}$ and $P_{SS}$ across the $L$ and $SPK$ matrices.
- [ ] (Optional High-Freq Pass): Re-run the chain utilizing the 30kHz raw matrix $X$ and discrete 30kHz spike times to calculate the purely resistive high-frequency asymptote $Z_{eff}(z, \infty)$.
- [ ] Commit the modular pipeline to the repository with visualization functions plotting heatmaps for $|Z_{eff}|$ and $\angle Z_{eff}$ vs depth.

## 4. skills-to-make
- **Biophysical Inverse Problems**: The agent will learn to treat standard spatial derivatives (like CSD) not as ground truth, but as observable variables subjected to tissue filtering.
- **Cross-Spectral Signal Processing**: Mastery of transferring time-domain correlations into robust, window-averaged complex frequency transfer functions.
- **Tensor Scale-Up**: Handling multi-billion sample arrays by mapping operations across discrete time-windows rather than attempting full-array memory loading.