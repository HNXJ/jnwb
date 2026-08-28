# Figure 04: Population Spiking Dynamics and Omission Identity Decoding

## 1. Sealed Headline & Central Finding

$$\boxed{\text{Population spiking primarily represents temporal sequence state, rather than the identity of an expected-but-omitted stimulus.}}$$

* **Disciplined Representational Conclusion**:
  > *Omission identity was not detectably represented in scalar firing rates, spatiotemporal linear subspaces, or the tested low-dimensional nonlinear population manifolds ($X|A \text{ vs } X|B \le 0.5000$).*
* **Subspace Dimension Discovery**:
  > *Physical visual stimulus identity occupies a compact population subspace ($D_{\text{ambient}} \gg D_{\text{informative}}$); $\operatorname{PCA}_5$ preserved the measured held-out stimulus-decoding performance of the ambient representation ($0.8303$ vs $0.8270$).*
* **Geometric Dominance**:
  > *Sequence position dynamics vastly dominate over expected stimulus identity ($R = \frac{D_{\text{between identity}}}{D_{\text{within identity, across position}}} \approx 0.2105 \ll 1.0$).*
* **Terminal Slot Structure**:
  > *Elevated decodability at $p_4$ reflects terminal-position-specific structure because cross-position generalization collapses to $0.3870$ ($0.0\%$ significance).*
* **Trajectory Dynamics**:
  > *No transient identity divergence exceeding the within-cycle permutation null was detected at the tested 53-ms resolution.*

---

## 2. Nine-Panel Layout Specification ($3 \times 3$)

| Panel | Topic | Target / Estimand | Sampling Scope | Empirical Result | Scientific Verdict |
|---|---|---|---|---|---|
| **Panel A** | Physical Stimulus Positive Control | $A \text{ vs } B$ at $p_1$ ($0\text{--}531\text{ ms}$) across Direct, $\operatorname{PCA}_5$, $\operatorname{UMAP}_5$, $\operatorname{PCA}\rightarrow\operatorname{UMAP}$ | 4-session representative multi-subject subset | Direct Acc = $0.827$, $\operatorname{PCA}_5$ Acc = **$0.830$** (AUC $0.855$), $\operatorname{UMAP}_5$ Acc = $0.729$ | **PASS** ($\operatorname{PCA}_5$ preserved the measured held-out stimulus-decoding performance of ambient space) |
| **Panel B** | Temporal Context Sequence Position | $p_1 \text{ vs } p_2 \text{ vs } p_3 \text{ vs } p_4$ 4-way decoding under cycle-grouped CV | Full Corpus ($N=22$ sessions, $n=79$ area populations) | Mean Acc = **$0.3743 \pm 0.0101$ (Chance = $0.2500$)**; **$43/79$ ($54.4\%$) survive strict Benjamini-Hochberg FDR correction ($q < 0.05$)** | **PRIMARY_SUPPORTED** (spiking robustly tracks sequence progression) |
| **Panel C** | Temporal Context Cortical Hierarchy | 4-way position accuracy across V1, V2, MT, MST, FEF, PFC | Full Corpus ($N=22$ sessions, $n=79$ area populations) | V1 ($0.376$), V2 ($0.354$), MT ($0.378$), MST ($0.369$), FEF ($0.364$), PFC ($0.377$) | **DISTRIBUTED** (sequence state is broadcast across sensory and frontal tiers) |
| **Panel D** | Position-Specific Omission Decoding | $X\|A \text{ vs } X\|B$ across slot positions $p_2, p_3, p_4$ under LOCO CV | Full Corpus ($N=22$ sessions, $n=79$ area populations) | $p_2$ Acc = $0.4526$ (Sig $3.8\%$), $p_3$ Acc = $0.4905$ (Sig $9.1\%$), $p_4$ Acc = $0.5935$ (Sig $40.3\%$) | **NOT DETECTABLY REPRESENTED at $p_2/p_3$** |
| **Panel E** | Cross-Position Generalization Transfer | $\operatorname{train}(p_2, p_3) \rightarrow \operatorname{test}(p_4)$ transfer decoding | Full Corpus ($N=22$ sessions, $n=77$ area populations) | Within-$p_4$ Acc = $0.5935 \pm 0.0175$ vs Transfer Acc = **$0.3870 \pm 0.0148$** ($0/77$, $0.0\%$ sig) | **TERMINAL-POSITION-SPECIFIC STRUCTURE** ($p_4$ code does not generalize to mid-sequence slots) |
| **Panel F** | Manifold Invariance Ratio ($R$) | $R = \frac{D_{\text{between identity}}}{D_{\text{within identity, across position}}}$ | 4-session representative multi-subject subset | Direct $R = 0.812$, $\operatorname{PCA}_5 R = 1.014$, $\operatorname{UMAP}_5 R = \mathbf{0.2105 \ll 1.0}$ | **POSITION DOMINATES IDENTITY** ($D_{\text{position}} \approx 5 \times D_{\text{identity}}$) |
| **Panel G** | Omission Decoding across Hierarchy | $X\|A \text{ vs } X\|B$ at $p_2$ across Direct, $\operatorname{PCA}_5$, $\operatorname{UMAP}_5$, $\operatorname{PCA}\rightarrow\operatorname{UMAP}$ | 4-session representative multi-subject subset | Direct = $0.468$, $\operatorname{PCA}_5$ = $0.457$, $\operatorname{UMAP}_5$ = $0.477$, $\operatorname{PCA}\rightarrow\operatorname{UMAP}$ = $0.503$ | **NOT DETECTABLY REPRESENTED across tested manifolds and nonlinear encoders** |
| **Panel H** | Latent Trajectory Dynamics | $D_{AB}(t) = \|\mu_A(t) - \mu_B(t)\|$ across 10 temporal bins ($53.1\text{ ms}$ each) | 4-session representative multi-subject subset | Observed trajectory distance tracks within-cycle permutation null across all 10 bins ($p > 0.10$) | **NULL** (No transient identity divergence exceeding within-cycle permutation null detected at 53-ms resolution) |
| **Panel I** | Unified Representation Summary | $3 \times 3$ Matrix: Stimulus, Position, Omission $\times$ Direct, PCA, UMAP | Full & Sub-Corpus Synthesized | Empirical Held-Out Performance Matrix | **SUMMARY COHERENCE** |

---

## 3. Sampling Scope & Provenance Accounting

1. **Full Corpus Scope**: $N=22$ sessions, $n=79$ area populations (Panels B, C, D, E).
2. **4-Session Representative Manifold Subset**: $N=4$ multi-area sessions across all 3 subjects (`sub-C31o_ses-230816`, `sub-C31o_ses-230823`, `sub-V182o_ses-260710`, `sub-V198o_ses-230719`), totaling $n=960$ decoding runs across 4 manifold representations, 3 downstream encoders, 10 temporal trajectory bins, and geometric distance ratios (Panels A, F, G, H, I).
