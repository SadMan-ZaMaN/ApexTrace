# ApexTrace

**Signal Processing & Driver Signature Analysis for Formula 1**

An experimental motorsport analytics project exploring F1 telemetry through digital signal processing, corner-level performance analysis, and interpretable driver identification.

## Run the web app

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pip install -e .
.venv\Scripts\python.exe -m app          # then open http://127.0.0.1:5000
# or, the same thing:  .venv\Scripts\python.exe run.py
```

The overview page works from the committed results. The lap-compare page also needs the raw lap
samples, which are not in the repository (`experiments/09_build_dataset.py` rebuilds them from OpenF1).

*ApexTrace is an unofficial student project and is not associated in any way with the Formula 1
companies. F1, FORMULA ONE, FORMULA 1 and related marks are trade marks of Formula One Licensing B.V.*
