import pandas as pd, numpy as np
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
DATA.mkdir(exist_ok=True)

dates = pd.date_range(end=pd.Timestamp.today(), periods=30)

# historic.csv
rows = []
for sku in ["GS-019","BL-101"]:
    base = np.random.randint(50,200)
    for d in dates:
        rows.append({"date": d.strftime("%Y-%m-%d"), "sku": sku, "units": int(base + np.random.randint(-20,20))})
pd.DataFrame(rows).to_csv(DATA/"historic.csv", index=False)

# social.csv
hashtags = ["#sale","#new","#trend"]
rows = []
for d in dates:
    for h in hashtags:
        rows.append({"date": d.strftime("%Y-%m-%d"), "hashtag": h, "mentions": int(np.random.randint(0,50)), "source":"TikTok", "sku":"GS-019"})
pd.DataFrame(rows).to_csv(DATA/"social.csv", index=False)

print("Dummy data written to", DATA)
