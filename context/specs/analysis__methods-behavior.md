# Methodology Part 4: Oculomotor Precision & Behavioral Audit

## 1. Raw Source Extraction
- **File Format**: MonkeyLogic `.bhv2.mat` files.
- **Signal**: `bhvUni.AnalogData.Eye` (X and Y trajectories).
- **Precision**: Direct extraction of Degrees of Visual Angle (DVA) without intermediate compression or downsampling.

## 2. Temporal Alignment
- **Event Reference**: Trials aligned to **Code 101** (P1 Onset).
- **Omission Window**: Extraction of eye trajectories during the 1531ms window surrounding the expected stimulus presentation ($d_{k-1} \to p_k \to d_k$).

## 3. Precision Metrics
- **XY Variance**: Calculation of temporal variance in eye position as a proxy for fixation stability.
- **Microsaccade Density**: Identification of ballistic eye movements using a velocity threshold (>30°/s).
- **Jitter**: Quantification of high-frequency oscillatory noise in eye position.

## 4. Active Inference Audit
- **Goal**: Test the hypothesis of "Precision Scaling."
- **Prediction**: Neural surprise (omission) should trigger a compensatory tightening of oculomotor control, reflected as reduced XY variance (quenching) in the post-omission delay period.

---
*Status: Verified and Accepted.*
