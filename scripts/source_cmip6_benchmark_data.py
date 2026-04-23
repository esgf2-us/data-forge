from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen


@dataclass(frozen=True)
class SampleFile:
    label: str
    source_url: str


SINGLE_SAMPLE = SampleFile(
    label="single",
    source_url=(
        "s3://esgf-world/CMIP6/AerChemMIP/NCC/NorESM2-LM/histSST-piNTCF/"
        "r1i1p1f1/LImon/snd/gn/v20190920/"
        "snd_LImon_NorESM2-LM_histSST-piNTCF_r1i1p1f1_gn_185001-185912.nc"
    ),
)

MULTI_SAMPLES = [
    SampleFile(
        label="multi-1",
        source_url=SINGLE_SAMPLE.source_url,
    ),
    SampleFile(
        label="multi-2",
        source_url=(
            "s3://esgf-world/CMIP6/AerChemMIP/NCC/NorESM2-LM/histSST-piNTCF/"
            "r1i1p1f1/LImon/snd/gn/v20190920/"
            "snd_LImon_NorESM2-LM_histSST-piNTCF_r1i1p1f1_gn_186001-186912.nc"
        ),
    ),
    SampleFile(
        label="multi-3",
        source_url=(
            "s3://esgf-world/CMIP6/AerChemMIP/NCC/NorESM2-LM/histSST-piNTCF/"
            "r1i1p1f1/LImon/snd/gn/v20190920/"
            "snd_LImon_NorESM2-LM_histSST-piNTCF_r1i1p1f1_gn_187001-187912.nc"
        ),
    ),
]


def _https_url(source_url: str) -> str:
    parsed = urlparse(source_url)
    if parsed.scheme != "s3":
        return source_url
    return f"https://{parsed.netloc}.s3.amazonaws.com{parsed.path}"


def _download(source_url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return
    with urlopen(_https_url(source_url)) as src, destination.open("wb") as dst:
        shutil.copyfileobj(src, dst)


def _copy_samples(output_dir: Path) -> dict[str, list[dict[str, str]]]:
    manifest: dict[str, list[dict[str, str]]] = {"single": [], "multi": []}

    single_path = output_dir / "single" / Path(SINGLE_SAMPLE.source_url).name
    _download(SINGLE_SAMPLE.source_url, single_path)
    manifest["single"].append(
        {"source_url": SINGLE_SAMPLE.source_url, "local_path": str(single_path)}
    )

    for sample in MULTI_SAMPLES:
        local_path = output_dir / "multi" / Path(sample.source_url).name
        _download(sample.source_url, local_path)
        manifest["multi"].append(
            {"source_url": sample.source_url, "local_path": str(local_path)}
        )

    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download CMIP6 sample data for benchmarks"
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path("./data/benchmark-samples").resolve()),
        help="Directory to store benchmark samples",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    manifest = _copy_samples(output_dir)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
