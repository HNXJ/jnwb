# beta — restored from git history (commit 90c743d^, deleted 2026-05-05)
import numpy as np
from sklearn.decomposition import PCA
from src.analysis.io.loader import DataLoader
from src.analysis.io.logger import log

def estimate_recurrence(pop_traj: np.ndarray, n_comp: int = 5):
    """
    Fits X_{t+1} = A X_t and returns spectral radius of A.
    pop_traj: (time, units)
    """
    # 1. Reduce dim
    pca = PCA(n_components=n_comp)
    X = pca.fit_transform(pop_traj) # (T, n_comp)

    # 2. Shift for X_t and X_{t+1}
    Xt = X[:-1, :]
    Xnext = X[1:, :]

    # 3. Least squares: Xnext = Xt * A_transposed
    A_T, _, _, _ = np.linalg.lstsq(Xt, Xnext, rcond=None)
    A = A_T.T

    # 4. Spectral Radius
    eigvals = np.linalg.eigvals(A)
    radius = np.max(np.abs(eigvals))

    return radius

def analyze_recurrence_dynamics(loader: DataLoader, sessions: list, areas: list, condition="AXAB"):
    """
    Computes spectral radius of recurrence for each area during omission.
    """
    results = {area: [] for area in areas}

    for ses in sessions:
        log.info(f"Computing Recurrence for {ses}")
        for area in areas:
            spk = loader.get_signal(mode="spk", condition=condition, area=area, session=ses)
            if not spk: continue

            # Pop average trajectory
            pop = np.mean(spk[0], axis=0).T # (time, units)
            # Use DataLoader for omission onset
            onset = int(loader.get_omission_onset(condition))
            # Omission window: onset to onset+1500
            traj = pop[onset:onset+1500, :]

            if traj.shape[1] >= 5: # need enough units
                radius = estimate_recurrence(traj, n_comp=5)
                results[area].append(radius)

    # Aggregate
    final_results = {}
    for area in areas:
        if results[area]:
            final_results[area] = {
                'radius_mean': np.mean(results[area]),
                'radius_std': np.std(results[area])
            }

    return final_results
