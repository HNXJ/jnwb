#!/usr/bin/env python3
r"""Neural Additive Model (NAM) for (N x T) neural decoding with per-unit attribution.

    logit_c(X) = b_c + sum_{i=1..N} h_i(x_i)_c

Each unit/channel i gets its OWN sub-network h_i seeing ONLY that unit's temporal vector x_i,
so its scalar contribution to the decision is unambiguous -- which a standard network, mixing all
inputs in its first layer, cannot give.

IMPLEMENTATION NOTE (identical math, not an approximation)
    The reference implementation loops `for i in range(N): subnets[i](x[:, i])`, which is N
    separate small GPU kernels per forward pass and is dominated by launch overhead. This
    implements the same N independent sub-networks as GROUPED operations:
        - a grouped Conv1d (groups=N) = N independent temporal convolutions
        - two einsum layers against per-unit weight tensors = N independent MLPs
    No weights are shared across units. Verified equivalent to the looped form in
    tests/receipts (see scripts/decode_fig04_v9_nam.py's self-check).

ATTRIBUTION
    S_i = std over trials of unit i's contribution. High S_i = that unit's output swings with
    the class, i.e. it is driving the decision. S_i ~ 0 = contributes nothing. For the 3-way
    (A/B/R) case S_i is the mean over classes of the per-class trial-wise std.
"""
from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


class LaminarNAM(nn.Module):
    def __init__(self, num_units: int, time_samples: int, n_classes: int = 3,
                 n_filters: int = 8, hidden_dim: int = 32, kernel_size: int = 5,
                 dropout: float = 0.25):
        super().__init__()
        self.N, self.T, self.C = num_units, time_samples, n_classes
        self.F_ = n_filters
        self.conv = nn.Conv1d(num_units, num_units * n_filters, kernel_size=kernel_size,
                              padding=kernel_size // 2, groups=num_units)
        f_in = n_filters * time_samples
        self.w1 = nn.Parameter(torch.empty(num_units, hidden_dim, f_in))
        self.b1 = nn.Parameter(torch.zeros(num_units, hidden_dim))
        self.w2 = nn.Parameter(torch.empty(num_units, n_classes, hidden_dim))
        self.b2 = nn.Parameter(torch.zeros(num_units, n_classes))
        self.bias = nn.Parameter(torch.zeros(n_classes))
        self.dropout = nn.Dropout(dropout)
        for w, fan in ((self.w1, f_in), (self.w2, hidden_dim)):
            nn.init.uniform_(w, -1.0 / np.sqrt(fan), 1.0 / np.sqrt(fan))

    def forward(self, x, unit_mask=None):
        """x: (B, N, T). unit_mask: optional (N,) 0/1 tensor zeroing pruned units'
        contributions. Returns (logits (B,C), contributions (B,N,C))."""
        B = x.size(0)
        h = F.relu(self.conv(x)).view(B, self.N, -1)          # (B, N, F*T)
        h = F.relu(torch.einsum("bnf,nhf->bnh", h, self.w1) + self.b1)
        h = self.dropout(h)
        contrib = torch.einsum("bnh,nch->bnc", h, self.w2) + self.b2   # (B, N, C)
        if unit_mask is not None:
            contrib = contrib * unit_mask.view(1, -1, 1)
        return contrib.sum(dim=1) + self.bias, contrib


@torch.no_grad()
def unit_importance(model, X, device="cpu", unit_mask=None):
    """S_i = mean over classes of the trial-wise std of unit i's contribution."""
    model.eval()
    _, contrib = model(torch.as_tensor(X, dtype=torch.float32, device=device), unit_mask)
    return contrib.std(dim=0).mean(dim=1).cpu().numpy()   # (N,)


@torch.no_grad()
def predict(model, X, device="cpu", unit_mask=None):
    model.eval()
    logits, _ = model(torch.as_tensor(X, dtype=torch.float32, device=device), unit_mask)
    proba = torch.softmax(logits, dim=1).cpu().numpy()
    return proba.argmax(axis=1), proba


def train_nam(model, X_tr, y_tr, X_val, y_val, device="cpu", max_epochs=300, patience=25,
              lr=1e-3, weight_decay=1e-3, batch_size=64, class_weight=None, seed=0):
    """Train on the TRAIN split only. The VAL split never contributes a gradient -- it is used
    solely to early-stop and to restore the best-val weights, which is what keeps it available
    as an honest model-selection set while TEST stays untouched."""
    torch.manual_seed(seed)
    model.to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    Xtr = torch.as_tensor(X_tr, dtype=torch.float32, device=device)
    ytr = torch.as_tensor(y_tr, dtype=torch.long, device=device)
    Xva = torch.as_tensor(X_val, dtype=torch.float32, device=device)
    yva = torch.as_tensor(y_val, dtype=torch.long, device=device)
    cw = None if class_weight is None else torch.as_tensor(class_weight, dtype=torch.float32,
                                                           device=device)
    best, best_state, bad, best_epoch = np.inf, None, 0, 0
    n = len(Xtr)
    g = torch.Generator(device="cpu").manual_seed(seed)
    for epoch in range(max_epochs):
        model.train()
        perm = torch.randperm(n, generator=g).to(device)
        for i in range(0, n, batch_size):
            idx = perm[i:i + batch_size]
            opt.zero_grad()
            logits, _ = model(Xtr[idx])
            F.cross_entropy(logits, ytr[idx], weight=cw).backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            val_loss = float(F.cross_entropy(model(Xva)[0], yva, weight=cw))
        if val_loss < best - 1e-5:
            best, bad, best_epoch = val_loss, 0, epoch
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
        else:
            bad += 1
            if bad >= patience:
                break
    if best_state is not None:
        model.load_state_dict(best_state)
    return {"best_val_loss": best, "best_epoch": best_epoch, "epochs_run": epoch + 1}
