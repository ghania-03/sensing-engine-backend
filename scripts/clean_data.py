#!/usr/bin/env python3
"""Clean historic.csv and social.csv into normalized parquet/json files.

Usage:
    python clean_data.py --data-dir ../data --out-dir ../data/cleaned

Produces: historic.parquet, historic.json, social.parquet, social.json
"""
from pathlib import Path
import argparse
import pandas as pd
import os


def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def clean_historic(data_dir: Path, out_dir: Path):
    src = data_dir / "historic.csv"
    if not src.exists():
        print(f"historic.csv not found at {src}")
        return None

    df = pd.read_csv(src, parse_dates=["date"], infer_datetime_format=True)

    # map common column names to expected
    col_map = {}
    for c in df.columns:
        lc = c.lower()
        if lc in ("date", "ds", "day"):
            col_map[c] = "date"
        if lc in ("sku", "product", "sku_id"):
            col_map[c] = "sku"
        if lc in ("units", "sales", "quantity", "qty"):
            col_map[c] = "units"

    df = df.rename(columns=col_map)

    if "date" not in df.columns:
        raise ValueError("historic.csv must have a date column")

    # keep only required columns
    df["sku"] = df.get("sku", "UNK").fillna("UNK").astype(str)
    df["units"] = pd.to_numeric(df.get("units", 0), errors="coerce").fillna(0).astype(int)

    df = df[["date", "sku", "units"]].sort_values(["sku", "date"]) 
    df = df.drop_duplicates(subset=["sku", "date"], keep="last")

    ensure_dir(out_dir)
    out_par = out_dir / "historic.parquet"
    out_json = out_dir / "historic.json"
    df.to_parquet(out_par, index=False)
    df.to_json(out_json, orient="records", date_format="iso")
    print(f"Wrote cleaned historic to {out_par} and {out_json}")
    return out_par


def _normalize_hashtag(tag: str):
    if not isinstance(tag, str):
        return ""
    tag = tag.strip()
    if tag == "":
        return ""
    if not tag.startswith("#"):
        tag = "#" + tag
    return tag.lower()


def clean_social(data_dir: Path, out_dir: Path):
    src = data_dir / "social.csv"
    if not src.exists():
        print(f"social.csv not found at {src}")
        return None

    df = pd.read_csv(src, parse_dates=["date"], infer_datetime_format=True)

    # normalize column names
    col_map = {}
    for c in df.columns:
        lc = c.lower()
        if lc in ("date", "ts", "timestamp"):
            col_map[c] = "date"
        if lc in ("hashtag", "tag", "topic"):
            col_map[c] = "hashtag"
        if lc in ("mentions", "count", "mentions_count"):
            col_map[c] = "mentions"
        if lc in ("source", "platform"):
            col_map[c] = "source"
        if lc in ("sku", "product"):
            col_map[c] = "sku"

    df = df.rename(columns=col_map)

    # ensure columns exist
    if "date" not in df.columns:
        raise ValueError("social.csv must have a date/timestamp column")

    df["hashtag"] = df.get("hashtag", "").fillna("").apply(_normalize_hashtag)
    df["mentions"] = pd.to_numeric(df.get("mentions", 0), errors="coerce").fillna(0).astype(int)
    df["source"] = df.get("source", "unknown").fillna("unknown").astype(str)
    df["sku"] = df.get("sku", "").fillna("").astype(str)

    df = df[["date", "sku", "source", "hashtag", "mentions"]].sort_values(["date"]) 
    df = df.drop_duplicates()

    # top hashtags
    top = df["hashtag"].value_counts().reset_index()
    top.columns = ["hashtag", "count"]

    ensure_dir(out_dir)
    out_par = out_dir / "social.parquet"
    out_json = out_dir / "social.json"
    df.to_parquet(out_par, index=False)
    df.to_json(out_json, orient="records", date_format="iso")
    # also write top hashtags
    top_path = out_dir / "social_top_hashtags.json"
    top.to_json(top_path, orient="records")
    print(f"Wrote cleaned social to {out_par}, {out_json}, and {top_path}")
    return out_par


def main():
    parser = argparse.ArgumentParser(description="Clean historic and social CSVs")
    parser.add_argument("--data-dir", type=str, default=str(Path(__file__).resolve().parents[1] / "data"))
    parser.add_argument("--out-dir", type=str, default=str(Path(__file__).resolve().parents[1] / "data" / "cleaned"))
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)

    print(f"Reading from {data_dir}, writing cleaned files to {out_dir}")
    clean_historic(data_dir, out_dir)
    clean_social(data_dir, out_dir)


if __name__ == "__main__":
    main()
