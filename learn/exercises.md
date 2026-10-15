# Exercises: change, predict, run, check

The best way to own this code: change one thing, **predict** what will happen
(write the prediction down), run, and compare. Undo your change afterwards
(`git checkout -- <file>` or GitHub Desktop → Discard).

## Chapter 2 (setup, lap selection)

1. In `tests/test_data_loading.py`, change lap 3's time from 100.2 to 87.0 s.
   Predict which test fails and why. Run `python -m pytest`.
2. In `data_loading.py`, set `SLOW_LAP_FACTOR = 1.02`. Predict how many
   Abu Dhabi FP2 long-run laps survive. Run `experiments/01_data_pilot.py`.
3. Delete the 2025 guard in `load_session` and run the tests. Which test
   catches it? Why doesn't it download anything?

## Chapter 3 (data)

4. In `01_data_pilot.py` set `GAP_THRESHOLD_S = 0.45`. Predict: more or fewer
   "gaps"? Why is 0.6 a better choice? (Hint: look at `sample_intervals.png`.)
5. Compute by hand: an interval of 0.40 s at 250 km/h. How many metres between
   samples? What is the uniform error std if you report the middle?
6. Run `quality.event_timing_error_s([0.16, 0.48])` in Python. Explain why the
   answer is bigger than `mean([0.16, 0.48]) / sqrt(12)`.

## Chapter 4 (measurement science)

7. In `02_group_delay_demo.py`, change the moving average from 5 to 9 samples.
   Predict the new delay in seconds and the mid-braking shift in metres. Run it.
8. In `synthetic.py`, change the brake ramp range in `random_corner_params`
   to `rng.uniform(0.0, 0.01)` (an instant ramp). Predict what happens to the
   bias of "speed breakpoint". Run `03_synthetic_errors.py` (reduce
   `LAPS_PER_TYPE` to 200 for speed).
9. In `03_synthetic_errors.py`, the "regular" scenario uses the mean interval.
   Change it to 0.16 s (a ~6 Hz feed). Predict how the midpoint error changes.
10. Plot one synthetic corner: `truth = make_true_corner(random_corner_params("heavy_braking", rng))`,
    then plot `truth["time_s"]` vs `truth["speed_kmh"]`, and on top the
    samples from `degrade_like_feed`. Mark the true brake onset.
11. Derive by hand: for a moving average of N samples, show H(e^{jω}) has
    |H| = |sin(Nω/2) / (N sin(ω/2))| and linear phase −ω(N−1)/2. What are the
    zeros?
