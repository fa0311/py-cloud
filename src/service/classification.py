import os
from typing import Any

import httpx
import numpy as np
import torch
from httpx import URL
from PIL import Image
from transformers import (
    AutoImageProcessor,
    AutoModelForImageClassification,
)

from submodule.TorchDeepDanbooru import deep_danbooru_model


class ClassificationModel:
    device = torch.device("cuda")
    cache_dir = "./.cache"

    def __init__(self, labels: list[str], model: Any, processor: Any = None):
        self.labels = labels
        self.model = model
        self.processor = processor

    @classmethod
    def load(cls, source: str) -> "ClassificationModel":
        raise NotImplementedError

    def classify(self, filename: str) -> list[int]:
        raise NotImplementedError


def __del__(self):
    del self.model
    del self.processor
    torch.cuda.empty_cache()


class DeepDanbooruClassificationModel(ClassificationModel):
    @classmethod
    def load(cls, source: str):
        url = URL(source)
        output_dir = os.path.join(cls.cache_dir, *url.path.split("/")[1:])
        os.makedirs(os.path.dirname(output_dir), exist_ok=True)
        if not os.path.exists(output_dir):
            with httpx.stream("GET", url, follow_redirects=True) as response:
                with open(output_dir, "wb") as f:
                    for chunk in response.iter_bytes():
                        f.write(chunk)

        model = deep_danbooru_model.DeepDanbooruModel()
        model.load_state_dict(torch.load(output_dir, weights_only=True))
        model.eval()
        model.half()
        model.to(cls.device, non_blocking=True)

        return cls(model.tags, model)

    def classify(self, filename: str) -> list[int]:
        pic = Image.open(filename).convert("RGB").resize((512, 512))
        a = np.expand_dims(np.array(pic, dtype=np.float32), 0) / 255

        with torch.no_grad(), torch.autocast(self.device.type):
            x = torch.from_numpy(a).to(self.device, non_blocking=True)
            y = self.model(x)[0].detach().cpu().numpy()
            for _ in range(10):
                self.model(x)

            tag = np.where(y[:-3] >= 0.5)
            rating = np.where(y[-3:] >= 0.5)
            safe_key = rating[0] if rating[0] else 0
            return tag[0].tolist() + [(y.size - 3 + safe_key)]


class ImageClassificationModel(ClassificationModel):
    @classmethod
    def load(cls, source: str):
        model = AutoModelForImageClassification.from_pretrained(
            source,
            cache_dir=cls.cache_dir,
        )
        model.to(cls.device)
        processor = AutoImageProcessor.from_pretrained(
            source,
            cache_dir=cls.cache_dir,
        )
        return cls(model.config.id2label, model, processor)

    def classify(self, filename: str) -> list[int]:
        inputs = self.processor(images=Image.open(filename), return_tensors="pt")
        with torch.no_grad():
            outputs = self.model(pixel_values=inputs.pixel_values.to(self.device))
        logits = outputs.logits

        return [logits.argmax(-1).item()]
