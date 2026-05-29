"""Safe Withdrawal Backtester — the reference service.

Computes the *upper bound on the 4% rule*: for each historical retirement start
year, the maximum constant inflation-adjusted withdrawal rate that, with perfect
hindsight, would have brought the portfolio to exactly $0 at the end of a fixed
horizon — for various allocations. The historical *minimum* of those upper bounds
is the empirically "safe" rate to compare against the 4% rule of thumb.
"""
