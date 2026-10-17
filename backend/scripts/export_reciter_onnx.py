"""Export the existing model without changing the embedding database.

Run with the export dependency group. PyTorch is only needed for this command.
"""

from __future__ import annotations

import hashlib
import json

import numpy as np
import onnx
import torch

from app.core.config import get_settings
from scripts.torch_reference import get_classifier


class Encoder(torch.nn.Module):
    def __init__(self, classifier):
        super().__init__()
        self.fbanks = classifier.mods.compute_features.compute_fbanks
        self.encoder = classifier.mods.embedding_model

    def forward(self, power):
        features = self.fbanks(power)
        features = features - features.mean(dim=1, keepdim=True)
        return self.encoder(features, torch.ones(1, device=power.device))


def main():
    torch.set_num_threads(2)
    classifier = get_classifier()
    norm = classifier.mods.mean_var_norm
    stft = classifier.mods.compute_features.compute_STFT
    assert norm.norm_type == "sentence" and norm.mean_norm and not norm.std_norm
    assert (stft.n_fft, stft.win_length, stft.hop_length) == (400, 400, 160)
    assert stft.center and stft.pad_mode == "constant" and not stft.normalized_stft
    model = Encoder(classifier).eval()
    path = get_settings().reciter_onnx_path
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        model,
        torch.ones(1, 301, 201),
        str(path),
        opset_version=17,
        dynamo=False,
        input_names=["power"],
        output_names=["embedding"],
        dynamic_axes={"power": {1: "frames"}},
    )
    graph = onnx.load(str(path))
    onnx.checker.check_model(graph)
    metadata = {
        "source": get_settings().embedding_model_source,
        "source_revision": get_settings().embedding_model_revision,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "database_sha256": hashlib.sha256(get_settings().embeddings_path.read_bytes()).hexdigest(),
        "sample_rate": 16000,
        "n_fft": 400,
        "hop_length": 160,
        "precision": "float32",
        "bytes": path.stat().st_size,
        "numpy_version": np.__version__,
        "torch_version": torch.__version__,
    }
    path.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata))


if __name__ == "__main__":
    main()
