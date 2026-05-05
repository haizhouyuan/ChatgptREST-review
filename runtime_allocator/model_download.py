"""Model download manager for Paperclip LLM Research pipeline.

Handles downloading and managing local LLM models from HuggingFace.
Supports: MOSS-TTS-Nano, MiMo-7B, airLLM quantized models, Nemotron NVFP4/FP8.

Usage:
    from runtime_allocator.model_download import ModelDownloader
    downloader = ModelDownloader()
    downloader.download("mimo-7b")
    downloader.list_models()
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Default model storage directory
DEFAULT_MODEL_DIR = Path(os.path.expanduser("~/.paperclip/models"))

# Model registry: model_id -> HuggingFace repo + metadata
MODEL_REGISTRY: dict[str, dict] = {
    "mimo-7b": {
        "repo": "XiaomiMiMo/MiMo-7B-RL",
        "description": "Xiaomi MiMo 7B reasoning model",
        "size_gb": 14,
        "quantization": None,
        "license": "apache-2.0",
        "gpu_required": True,
        "min_gpu_memory_gb": 16,
    },
    "mimo-7b-gguf": {
        "repo": "XiaomiMiMo/MiMo-7B-RL-GGUF",
        "description": "Xiaomi MiMo 7B GGUF quantized",
        "size_gb": 4.5,
        "quantization": "Q4_K_M",
        "license": "apache-2.0",
        "gpu_required": False,
        "min_gpu_memory_gb": 0,
    },
    "moss-tts-nano": {
        "repo": "MOSS-TTS/MOSS-TTS-Nano",
        "description": "MOSS TTS Nano text-to-speech model",
        "size_gb": 0.5,
        "quantization": None,
        "license": "apache-2.0",
        "gpu_required": False,
        "min_gpu_memory_gb": 0,
    },
    "nemotron-mini-4b": {
        "repo": "nvidia/Nemotron-Mini-4B-Instruct",
        "description": "NVIDIA Nemotron Mini 4B instruct model",
        "size_gb": 8,
        "quantization": None,
        "license": "nvidia-open-model-license",
        "gpu_required": True,
        "min_gpu_memory_gb": 10,
    },
    "qwen2.5-7b-gguf": {
        "repo": "Qwen/Qwen2.5-7B-Instruct-GGUF",
        "description": "Qwen 2.5 7B Instruct GGUF quantized",
        "size_gb": 4.7,
        "quantization": "Q4_K_M",
        "license": "apache-2.0",
        "gpu_required": False,
        "min_gpu_memory_gb": 0,
    },
    "phi-4-mini": {
        "repo": "microsoft/Phi-4-mini-instruct",
        "description": "Microsoft Phi-4 Mini 3.8B instruct",
        "size_gb": 7.5,
        "quantization": None,
        "license": "mit",
        "gpu_required": True,
        "min_gpu_memory_gb": 10,
    },
}


@dataclass
class DownloadResult:
    model_id: str
    success: bool
    path: Optional[str] = None
    size_bytes: int = 0
    error: Optional[str] = None


class ModelDownloader:
    """Manages model downloads from HuggingFace."""

    def __init__(self, model_dir: Optional[Path] = None):
        self.model_dir = Path(model_dir) if model_dir else DEFAULT_MODEL_DIR
        self.model_dir.mkdir(parents=True, exist_ok=True)

    def list_available(self) -> list[dict]:
        """List all models in the registry."""
        models = []
        for model_id, info in MODEL_REGISTRY.items():
            models.append({
                "model_id": model_id,
                "repo": info["repo"],
                "description": info["description"],
                "size_gb": info["size_gb"],
                "quantization": info["quantization"],
                "downloaded": self.is_downloaded(model_id),
            })
        return models

    def list_downloaded(self) -> list[dict]:
        """List models that have been downloaded."""
        return [m for m in self.list_available() if m["downloaded"]]

    def is_downloaded(self, model_id: str) -> bool:
        """Check if a model has been downloaded."""
        model_path = self.model_dir / model_id
        return model_path.exists() and any(model_path.iterdir())

    def get_model_path(self, model_id: str) -> Optional[Path]:
        """Get the local path for a downloaded model."""
        model_path = self.model_dir / model_id
        if model_path.exists():
            return model_path
        return None

    def check_disk_space(self, model_id: str) -> tuple[bool, str]:
        """Check if there's enough disk space for a model."""
        info = MODEL_REGISTRY.get(model_id)
        if not info:
            return False, f"Unknown model: {model_id}"

        required_gb = info["size_gb"]
        stat = shutil.disk_usage(str(self.model_dir))
        free_gb = stat.free / (1024 ** 3)

        if free_gb < required_gb * 1.1:  # 10% buffer
            return False, f"Need {required_gb:.1f}GB but only {free_gb:.1f}GB free"
        return True, f"{free_gb:.1f}GB available, {required_gb:.1f}GB needed"

    def check_gpu(self, model_id: str) -> tuple[bool, str]:
        """Check if GPU requirements are met."""
        info = MODEL_REGISTRY.get(model_id)
        if not info:
            return False, f"Unknown model: {model_id}"

        if not info["gpu_required"]:
            return True, "No GPU required"

        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                memory_mb = int(result.stdout.strip().split("\n")[0])
                memory_gb = memory_mb / 1024
                required = info["min_gpu_memory_gb"]
                if memory_gb >= required:
                    return True, f"GPU has {memory_gb:.1f}GB, need {required}GB"
                return False, f"GPU has {memory_gb:.1f}GB but need {required}GB"
        except Exception:
            pass

        return False, "GPU check failed or no GPU available"

    def download(
        self,
        model_id: str,
        force: bool = False,
        token: Optional[str] = None,
    ) -> DownloadResult:
        """Download a model from HuggingFace.

        Args:
            model_id: Model ID from MODEL_REGISTRY
            force: Re-download even if already exists
            token: HuggingFace API token (for gated models).
                If None, reads from HF_TOKEN env var (preferred).

        Returns:
            DownloadResult with success status and path.
        """
        info = MODEL_REGISTRY.get(model_id)
        if not info:
            return DownloadResult(
                model_id=model_id,
                success=False,
                error=f"Unknown model: {model_id}. Available: {list(MODEL_REGISTRY.keys())}",
            )

        model_path = self.model_dir / model_id

        if self.is_downloaded(model_id) and not force:
            return DownloadResult(
                model_id=model_id,
                success=True,
                path=str(model_path),
            )

        # Check disk space
        ok, msg = self.check_disk_space(model_id)
        if not ok:
            return DownloadResult(model_id=model_id, success=False, error=msg)

        # Check GPU if required
        ok, msg = self.check_gpu(model_id)
        if not ok and info["gpu_required"]:
            print(f"Warning: {msg}. Model may not run on this machine.", file=sys.stderr)

        # Download using huggingface-cli to a temp dir, then atomic rename
        print(f"Downloading {model_id} from {info['repo']}...")
        print(f"  Size: ~{info['size_gb']}GB")
        print(f"  Destination: {model_path}")

        # Token: prefer env over parameter (parameter is legacy)
        resolved_token = token or os.getenv("HF_TOKEN", "")

        import tempfile
        temp_dir = Path(tempfile.mkdtemp(prefix=f"hf_download_{model_id}_", dir=str(self.model_dir)))
        try:
            cmd = [
                "huggingface-cli", "download",
                info["repo"],
                "--local-dir", str(temp_dir),
            ]
            if resolved_token:
                cmd.extend(["--token", resolved_token])

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
            if result.returncode != 0:
                shutil.rmtree(temp_dir, ignore_errors=True)
                return DownloadResult(
                    model_id=model_id,
                    success=False,
                    error=f"Download failed: {result.stderr[:500]}",
                )

            # Atomic move: temp_dir -> final_dir
            if model_path.exists():
                if force:
                    shutil.rmtree(model_path)
                else:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    return DownloadResult(
                        model_id=model_id,
                        success=True,
                        path=str(model_path),
                    )
            temp_dir.rename(model_path)
            return DownloadResult(
                model_id=model_id,
                success=True,
                path=str(model_path),
            )
        except subprocess.TimeoutExpired:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return DownloadResult(
                model_id=model_id,
                success=False,
                error="Download timed out (1 hour limit)",
            )
        except FileNotFoundError:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return DownloadResult(
                model_id=model_id,
                success=False,
                error="huggingface-cli not found. Install with: pip install huggingface_hub",
            )
        except Exception as e:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return DownloadResult(
                model_id=model_id,
                success=False,
                error=str(e)[:500],
            )

    def delete(self, model_id: str) -> bool:
        """Delete a downloaded model.

        Security: model_id must be in registry. Path is resolved and
        checked to be under model_dir to prevent path traversal.
        """
        if model_id not in MODEL_REGISTRY:
            return False
        model_path = (self.model_dir / model_id).resolve()
        # Path containment check
        try:
            model_path.relative_to(self.model_dir.resolve())
        except ValueError:
            return False
        if model_path.exists():
            shutil.rmtree(model_path)
            return True
        return False

    def summary(self) -> dict:
        """Get a summary of model storage."""
        total_size = 0
        downloaded = []
        for model_id in MODEL_REGISTRY:
            model_path = self.model_dir / model_id
            if model_path.exists():
                size = sum(f.stat().st_size for f in model_path.rglob("*") if f.is_file())
                total_size += size
                downloaded.append({
                    "model_id": model_id,
                    "size_mb": size / (1024 * 1024),
                })

        return {
            "model_dir": str(self.model_dir),
            "downloaded_count": len(downloaded),
            "total_size_mb": total_size / (1024 * 1024),
            "models": downloaded,
        }


# ── CLI entry point ──────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Paperclip Model Download Manager")
    sub = parser.add_subparsers(dest="command", required=True)

    # list command
    sub.add_parser("list", help="List all available models")

    # downloaded command
    sub.add_parser("downloaded", help="List downloaded models")

    # download command
    dl_parser = sub.add_parser("download", help="Download a model")
    dl_parser.add_argument("model_id", help="Model ID to download")
    dl_parser.add_argument("--force", action="store_true", help="Re-download if exists")
    dl_parser.add_argument("--token", help="HuggingFace API token")

    # delete command
    rm_parser = sub.add_parser("delete", help="Delete a downloaded model")
    rm_parser.add_argument("model_id", help="Model ID to delete")

    # summary command
    sub.add_parser("summary", help="Show storage summary")

    args = parser.parse_args()
    downloader = ModelDownloader()

    if args.command == "list":
        models = downloader.list_available()
        for m in models:
            status = "✓" if m["downloaded"] else " "
            q = f" ({m['quantization']})" if m["quantization"] else ""
            print(f"  [{status}] {m['model_id']:20s} {m['size_gb']:5.1f}GB{q} — {m['description']}")

    elif args.command == "downloaded":
        models = downloader.list_downloaded()
        if not models:
            print("No models downloaded yet.")
        for m in models:
            print(f"  {m['model_id']:20s} {m['size_gb']:5.1f}GB — {m['description']}")

    elif args.command == "download":
        result = downloader.download(args.model_id, force=args.force, token=args.token)
        if result.success:
            print(f"OK: {result.model_id} -> {result.path}")
        else:
            print(f"FAIL: {result.error}")
            sys.exit(1)

    elif args.command == "delete":
        if downloader.delete(args.model_id):
            print(f"Deleted: {args.model_id}")
        else:
            print(f"Not found: {args.model_id}")

    elif args.command == "summary":
        s = downloader.summary()
        print(f"Model directory: {s['model_dir']}")
        print(f"Downloaded: {s['downloaded_count']} models, {s['total_size_mb']:.0f}MB total")


if __name__ == "__main__":
    main()
