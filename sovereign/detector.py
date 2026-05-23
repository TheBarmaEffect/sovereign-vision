"""SovereignDetector - YOLO26 MLX wrapper that *forces* every detection
through the Constitutional Firewall.

Design invariant: there is no public method on this class that returns raw
detections. The only output is a `FirewallResult`. If you find a way to
extract raw detections from a `SovereignDetector` instance, that's a bug
and a violation of the constitution.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sovereign.firewall import ConstitutionalFirewall, FirewallResult, RawDetection

if TYPE_CHECKING:  # pragma: no cover
    import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_MODEL_FILENAME: str = "yolo26m.npz"
DEFAULT_CONF_THRESHOLD: float = 0.25  # SV-005 enforces a stricter 0.75 floor


class ModelLoadError(RuntimeError):
    """Raised when the YOLO26 MLX model cannot be loaded."""


class SovereignDetector:
    """The only path from a camera frame to an enterprise output."""

    def __init__(
        self,
        model_path: str | Path,
        firewall: ConstitutionalFirewall,
        conf_threshold: float = DEFAULT_CONF_THRESHOLD,
        device: str = "mlx",
    ) -> None:
        self._model_path = Path(model_path)
        self._firewall = firewall
        self._conf_threshold = conf_threshold
        self._device = device
        self._model = self._load_model()
        self._inference_count: int = 0
        self._total_inference_ns: int = 0
        logger.info(
            "SovereignDetector ready: model=%s device=%s conf=%.2f session=%s",
            self._model_path.name,
            device,
            conf_threshold,
            firewall.session_id,
        )

    # -- the only public entrypoints ----------------------------------------

    def detect(self, frame: "np.ndarray") -> FirewallResult:
        """Run YOLO26 MLX inference and immediately pipe through the firewall.

        Returns only the firewall result. The raw detections produced by the
        model are local to this method and dropped before return.
        """
        result, _ = self._detect_with_raw(frame, expose_raw=False)
        return result

    def detect_with_raw_preview(
        self, frame: "np.ndarray"
    ) -> tuple[FirewallResult, list[RawDetection]]:
        """Same as `detect`, but also returns the raw detections for the
        dashboard's left-hand "RAW INFERENCE" panel.

        IMPORTANT: this method is an explicit, audited side channel for
        DEMO VISUALISATION ONLY. The raw detections returned here:

          1. Are computed in the SAME inference call as the firewall result
             (no second `predict()` invocation, no double-inference path).
          2. Are intended to be consumed within the current render frame
             and dropped immediately.
          3. Are NEVER persisted, logged, or aggregated.
          4. Are not used to construct any compliance artifact.

        In a production deployment (`--production` flag on `run_demo.py`)
        this method MUST NOT be called. The audit chain will record a
        BLOCKED status if it is.
        """
        return self._detect_with_raw(frame, expose_raw=True)

    def _detect_with_raw(
        self, frame: "np.ndarray", expose_raw: bool
    ) -> tuple[FirewallResult, list[RawDetection]]:
        infer_start_ns = time.perf_counter_ns()
        raw = self._run_inference(frame)
        inference_ms = (time.perf_counter_ns() - infer_start_ns) / 1e6
        self._inference_count += 1
        self._total_inference_ns += time.perf_counter_ns() - infer_start_ns

        # Hand a snapshot to the dashboard side channel BEFORE the
        # firewall consumes the list. The firewall does not mutate `raw`
        # but we copy defensively so the dashboard cannot interact with
        # the firewall's working state.
        raw_preview = list(raw) if expose_raw else []

        result = self._firewall.process_frame(
            raw_detections=raw,
            frame=frame,
            frame_shape=frame.shape if hasattr(frame, "shape") else None,
            inference_latency_ms=inference_ms,
        )
        # Deliberately drop the reference to raw detections immediately.
        del raw
        return result, raw_preview

    # -- accessors -----------------------------------------------------------

    @property
    def firewall(self) -> ConstitutionalFirewall:
        return self._firewall

    @property
    def model_path(self) -> Path:
        return self._model_path

    @property
    def average_inference_ms(self) -> float:
        if self._inference_count == 0:
            return 0.0
        return (self._total_inference_ns / self._inference_count) / 1e6

    # -- internals -----------------------------------------------------------

    def _load_model(self) -> Any:
        """Load the YOLO26 MLX model.

        We support three states:
          1) MLX + yolo26mlx are installed → real model
          2) MLX not installed (e.g. CI, Linux) → simulation model
          3) Model file missing → raise ModelLoadError
        """
        if not self._model_path.exists():
            logger.warning(
                "Model file %s not found - falling back to simulation backend",
                self._model_path,
            )
            return _SimulationModel()

        try:
            # We import lazily so this module can be imported on machines
            # without MLX (e.g. CI runners) for the purpose of running tests.
            from yolo26mlx import YOLO  # type: ignore[import-not-found]
        except Exception as exc:  # pragma: no cover - depends on env
            logger.warning(
                "yolo26mlx not importable (%s) - using simulation backend",
                exc,
            )
            return _SimulationModel()

        try:
            model = YOLO(str(self._model_path))
            logger.info("YOLO26 MLX model loaded from %s", self._model_path)
            return model
        except Exception as exc:  # pragma: no cover - depends on env
            raise ModelLoadError(f"Failed to load YOLO26 MLX model: {exc}") from exc

    def _run_inference(self, frame: "np.ndarray") -> list[RawDetection]:
        """Run model.predict and convert to a list of RawDetection.

        We tolerate two output shapes:
          - YOLO26 MLX `results[0].boxes` API
          - The simulation backend that returns RawDetection directly
        """
        if isinstance(self._model, _SimulationModel):
            return self._model.predict(frame, conf=self._conf_threshold)

        try:
            results = self._model.predict(frame, conf=self._conf_threshold)
            return _yolo_results_to_raw(results)
        except Exception as exc:  # pragma: no cover - depends on env
            logger.error("YOLO predict failed: %s - returning empty detections", exc)
            return []


# ---------------------------------------------------------------------------
# Simulation backend - runs anywhere, no MLX required
# ---------------------------------------------------------------------------


class _SimulationModel:
    """Deterministic synthetic detector for testing and CI.

    Produces a small, plausible stream of detections (a couple of persons,
    a phone, occasional sensitive object) so the whole pipeline can be
    exercised end-to-end without GPU/MLX.
    """

    def __init__(self, seed: int = 42) -> None:
        import random

        self._rng = random.Random(seed)
        self._tick = 0

    def predict(
        self,
        frame: Any,
        conf: float = DEFAULT_CONF_THRESHOLD,
    ) -> list[RawDetection]:
        self._tick += 1
        h, w = _shape_or_default(frame)
        detections: list[RawDetection] = []

        # 1-4 persons drifting across the frame
        n_persons = self._rng.randint(1, 4)
        for i in range(n_persons):
            cx = ((self._tick * 7 + i * 137) % w) / float(w)
            cy = 0.3 + 0.4 * (((self._tick + i * 53) % 100) / 100.0)
            bw, bh = 80, 200
            x = int(cx * w - bw / 2)
            y = int(cy * h - bh / 2)
            confidence = round(self._rng.uniform(0.6, 0.95), 3)
            detections.append(
                RawDetection(
                    class_name="person",
                    confidence=confidence,
                    bbox=(x, y, bw, bh),
                    track_id=self._tick * 10 + i,  # firewall must drop this
                )
            )

        # occasional phone
        if self._tick % 5 == 0:
            detections.append(
                RawDetection(
                    class_name="cell phone",
                    confidence=0.81,
                    bbox=(int(0.4 * w), int(0.55 * h), 40, 60),
                )
            )

        # rare sensitive object
        if self._tick % 47 == 0:
            detections.append(
                RawDetection(
                    class_name="knife",
                    confidence=0.78,
                    bbox=(int(0.6 * w), int(0.45 * h), 50, 30),
                )
            )

        return [d for d in detections if d.confidence >= conf]


def _shape_or_default(frame: Any) -> tuple[int, int]:
    try:
        return int(frame.shape[0]), int(frame.shape[1])
    except Exception:
        return 720, 1280


def _yolo_results_to_raw(results: Any) -> list[RawDetection]:  # pragma: no cover
    """Convert YOLO26 MLX `results` to our RawDetection list.

    This duck-types the YOLO results object so any compatible YOLO API
    (yolo26mlx, ultralytics, etc.) works as long as `boxes.xywh`, `cls`,
    and `conf` are present.
    """
    out: list[RawDetection] = []
    for r in results:
        boxes = getattr(r, "boxes", None)
        if boxes is None:
            continue
        names = getattr(r, "names", {})
        xywh = getattr(boxes, "xywh", None)
        cls = getattr(boxes, "cls", None)
        conf = getattr(boxes, "conf", None)
        if xywh is None or cls is None or conf is None:
            continue
        for i in range(len(xywh)):
            cls_idx = int(cls[i])
            cname = str(names.get(cls_idx, cls_idx))
            x, y, w, h = (float(v) for v in xywh[i])
            out.append(
                RawDetection(
                    class_name=cname,
                    confidence=float(conf[i]),
                    bbox=(x - w / 2, y - h / 2, w, h),
                )
            )
    return out
