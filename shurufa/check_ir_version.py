import onnx
from pathlib import Path


def check(path: str) -> None:
    p = Path(path)
    if not p.exists():
        print(f"missing: {path}")
        return
    m = onnx.load(str(p))
    print(f"{p.name}\tIR_VERSION={m.ir_version}")


ASSETS_DIR = Path("e:/project/31fangyan/shurufa/app/src/main/assets")
check(str(ASSETS_DIR / "model.onnx"))
check(str(ASSETS_DIR / "model_quantized.onnx"))

