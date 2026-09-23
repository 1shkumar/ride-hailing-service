# Ride Hailing Backend

An in-memory ride-hailing backend (Uber-style): register users and drivers,
book a ride against nearby available drivers, price it with tiered per-km
rates, apply coupons, and get ride history — plus surge pricing, configurable
driver matching, cancellation fees, and concurrency-safe booking.

Built as a FastAPI web app. In-memory storage, no database, no auth — see
"Points to note" in the brief; both are explicitly optional.

## Prerequisites & Setup

Make sure Python 3.10+ is installed before running the project.

## Create and activate a virtual environment

### Windows (PowerShell):
```bash

python -m venv .venv
.\.venv\Scripts\Activate.ps1

```
### macOS / Linux:

```bash
python3 -m venv .venv 
source .venv/bin/activate

```
## Running it

```bash
pip install -r requirements.txt

# run the API
uvicorn app.main:app --reload
# -> http://127.0.0.1:8000/docs for interactive Swagger UI

# run the tests
pytest -v
```

53 tests, all passing. No external services or network access required —
everything is in-memory and self-contained.

### Switching bonus strategies at runtime

```bash
MATCHING_STRATEGY=HIGHEST_RATED uvicorn app.main:app --reload   # default: NEAREST
SURGE_STRATEGY=DEMAND_SUPPLY uvicorn app.main:app --reload      # default: NONE (1x)
```

These are read once at startup in `app/main.py` and handed to `RideService`
through its public `set_matching_strategy` / `set_surge_strategy` setters —
`RideService` itself never branches on config, which is the point of bonus
requirement #2 ("switchable without touching booking logic").

## API surface

| Method | Path                        | Purpose                                   |
|--------|-----------------------------|--------------------------------------------|
| POST   | `/users`                    | Register a user                            |
| POST   | `/drivers`                  | Register a driver (creates their cab too)  |
| PUT    | `/drivers/{id}/location`    | Update that driver's cab location          |
| POST   | `/rides/book`                | Book a ride                                |
| POST   | `/rides/{id}/end`            | End a ride, get the final cost             |
| POST   | `/rides/{id}/cancel`         | Cancel an ongoing ride (bonus)             |
| GET    | `/users/{id}/rides`          | Ride history for a user                    |
| GET    | `/drivers/{id}/rides`        | Ride history for a driver                  |
| POST   | `/coupons`                   | Add a coupon                               |
| DELETE | `/coupons/{code}`            | Delete a coupon                            |

Full request/response shapes are in `app/schemas.py` and visible live at
`/docs`.

## Project layout

```
app/
  models.py             domain entities (User, Driver, Cab, Ride, Coupon, Location) — plain dataclasses
  enums.py              CarType, CabStatus, RideStatus, DiscountType
  exceptions.py         domain exceptions, mapped to HTTP codes at the API edge only
  repositories.py       in-memory storage
  pricing/
    strategy.py         PricingStrategy interface + TieredPricingStrategy
    registry.py         CarType -> PricingStrategy  (the "add a car type" seam)
    surge.py            SurgeStrategy interface + NoSurge / DemandSupply implementations
  matching/
    strategy.py         MatchingStrategy interface + Nearest / HighestRated implementations
  coupons/
    service.py          coupon CRUD + discount computation
  services/
    user_service.py
    driver_service.py
    ride_service.py     booking / ending / cancelling — the orchestrator, with per-cab locking
  container.py           manual dependency wiring (one factory function, used by both main.py and tests)
  schemas.py             pydantic request/response models — the ONLY place pydantic is used
  main.py                FastAPI routes; HTTP <-> service translation only, no business logic
tests/
  test_pricing.py        tiers, minimum fare, per-car-type rates, registry
  test_coupons.py        add/delete/apply, flat vs percentage, caps, invalid codes
  test_booking.py        radius search, free upgrade, ending, history
  test_matching.py       nearest vs highest-rated
  test_surge.py           demand/supply multiplier, effect on final fare
  test_cancellation.py    grace period, flat fee, cab release
  test_concurrency.py     the double-booking race condition
  test_api.py             a few tests through the real HTTP layer (FastAPI TestClient)
```

## Assumptions (spec was silent or ambiguous here)

- **One driver = one cab.** The spec talks about "the location of a cab" as
  if a cab might be distinct from a driver (e.g. a driver swapping vehicles),
  but nothing in the mandatory scope needs that distinction. Registering a
  driver creates their one cab in the same call; "update a cab's location" is
  exposed as `PUT /drivers/{id}/location`.
- **Booking = starting the ride.** The spec only mentions "book" and "end" as
  ride-lifecycle actions — there's no separate "ride has started" step (e.g.
  after the driver physically arrives). So `book_ride` puts the ride straight
  into `ONGOING`, and the ride's clock (used for the cancellation grace
  period) starts at booking time.
- **Coupons are validated at booking, discount computed at ending.** "Apply a
  valid coupon when starting a ride" is interpreted as: fail fast if the
  coupon doesn't exist at booking time (so the user gets that feedback
  immediately, not after the whole trip), but the actual discount amount is
  computed against the real final fare in `end_ride`, since distance —
  and therefore fare — isn't known yet at booking time.
- **Hatchback rates are our own numbers; only the Sedan example was given.**
  We made Hatchback cheaper than Sedan at every tier (typical of real
  ride-hailing pricing): min fare ₹40, ₹8/₹6/₹4 per km across the same 0-2 /
  2-5 / 5+ km bands as the Sedan example. See `app/pricing/registry.py`.
- **The free Hatchback→Sedan upgrade is priced at Hatchback rates.** `Ride`
  stores both `car_type_requested` and `car_type_assigned`; `end_ride` always
  prices off `car_type_requested`, so the rider pays what they originally
  asked for regardless of which car actually showed up.
- **Distance is straight-line (haversine), not road distance.** No routing
  engine is in scope; this is called out explicitly as a simplification.
- **Cancellation-fee policy** (bonus, undefined by spec): free within a grace
  period (default 60s) of booking, a flat fee after that. Chosen because it's
  simple to reason about and to test; a real system would probably fold in
  how far the driver has already travelled toward pickup.
- **Surge pricing** (bonus) uses a coarse lat/lon grid cell as its "area" and
  a simple demand/supply ratio → multiplier formula. It's wired up but
  disabled by default (`SURGE_STRATEGY=NONE`) so the default demo path stays
  deterministic and easy to reason about; it's meant to demonstrate the seam
  more than to be a production-grade surge model.
- **Ratings are static.** Drivers get a `rating` at registration; nothing in
  the mandatory or bonus scope asks for post-ride rating updates, so none
  exist. `HighestRatedDriverStrategy` reads whatever rating was set at
  registration.
- **No auth, no persistence, no pagination.** Explicitly out of scope per the
  brief ("in-memory storage is fine... using a database is optional").

## Key design decisions & trade-offs

- **Strategy pattern for the three swappable behaviours the brief calls out
  by name: pricing (per car type), matching, and surge.** Each is an ABC with
  one narrow method (`calculate_fare`, `order_candidates`,
  `get_multiplier`), registered/injected rather than branched on inside
  `RideService`. Adding a new car type's pricing, or a whole new matching
  strategy, is a new class + one line of registration — it doesn't touch
  booking logic. This directly answers "where the seams are" from the
  evaluation criteria.
- **Domain layer has zero framework dependencies.** `app/models.py` and the
  `services/` layer only import from each other and the standard library —
  no FastAPI, no pydantic. `app/schemas.py` is the only pydantic in the
  codebase, and `app/main.py` is the only FastAPI. This means the whole
  domain + service layer is testable (and was tested) without ever starting
  a web server, and could be dropped behind a CLI instead with no changes
  below the API layer.
- **Per-cab locking, not a single global lock, for concurrency safety.** Two
  bookings for two *different* cabs should never block each other; only two
  bookings racing for the *same* cab should serialize. A dict of
  `threading.Lock`s keyed by cab id (created lazily under a small guard lock)
  gives that fine-grained safety cheaply. The claim sequence is: filter
  candidates by radius/type (unlocked, cheap), then for each candidate in
  matching-strategy order, take its lock, re-check `AVAILABLE`, flip to
  `BUSY`, release. `tests/test_concurrency.py` proves this under real
  `threading.Thread` contention (a 2-thread race for 1 cab, and a 20-thread
  race for 5 cabs), not just by inspection.
- **In-process locks are explicitly a single-process solution.** This is
  fine for the in-memory, single-process scope of this exercise, but would
  NOT be correct if this process were horizontally scaled — see "what I'd do
  differently."
- **Manual dependency wiring (`app/container.py`), not a DI framework.** One
  factory function building repos → services → `RideService`, called once by
  `main.py` for the live app and fresh by every test needing an isolated
  world. A DI framework would add ceremony this size of app doesn't need.
- **Tiered pricing modeled as an ordered list of `(upto_km, rate_per_km)`
  brackets**, computed like income-tax slabs (only the portion of distance
  inside each bracket is charged at that bracket's rate), with a `minimum_fare`
  floor applied once at the end. This was the most literal reading of the
  spec's example and generalizes cleanly to more tiers or different car
  types without special-casing.
- **Pydantic-only-at-the-edge.** Domain entities are plain `@dataclass`es;
  request/response validation is pydantic `BaseModel`s in `schemas.py` with
  `from_model` classmethods to convert. Keeps validation concerns (HTTP)
  separate from business rules (domain).

## What I'd do differently with more time

- **Real persistence** (Postgres via SQLAlchemy or similar) behind the same
  repository interfaces — the service layer wouldn't need to change at all,
  only the repository implementations.
- **Move booking concurrency safety from in-process locks to the database**
  (row-level locking / `SELECT ... FOR UPDATE`, or optimistic concurrency
  with a version column) so correctness holds across multiple server
  processes, not just multiple threads in one process.
- **Real routing distance/ETA** instead of haversine straight-line distance.
- **A proper geo-index** (geohash / S2 / quad-tree) for "drivers within
  radius" instead of the current O(n) scan over all cabs — fine at this
  scale, not at real scale.
- **Driver rating updates post-ride**, coupon expiry dates and per-user usage
  caps, idempotency keys on booking (so a client retry after a timeout can't
  double-book), and structured logging/metrics (booking latency, surge
  multiplier distribution, cancellation rate).
- **A `problem+json`-style error schema** instead of the current
  `{"detail": "..."}`, and request validation errors surfaced more
  consistently alongside domain errors.

## A note on AI use

In accordance with the prompt's guidelines encouraging AI tool usage, this project was developed using a **multi-model, iterative engineering approach**. Rather than relying on a single tool or blindly accepting generated output, I utilized **Claude, Gemini, and ChatGPT** concurrently to cross-examine architectural proposals, stress-test strategy implementations, and critique edge-case handling.

Every design pattern, algorithm, and test case was evaluated through an iterative feedback loop: prompting one model for an implementation, using another to counter-question its trade-offs, and refactoring the final code to ensure complete ownership and domain clarity.

### Prompting Strategy & Iterative Refinements

1. **Architecture & Design Patterns**:
   - *Initial Output*: A single-file application with coarse global locking and mixed business logic inside FastAPI route handlers.
   - *Critique & Refactor*: Prompted alternative models to challenge the separation of concerns. This led to decoupling into pure domain entities (`dataclass`), isolated Strategy Patterns (for Pricing, Matching, and Surge), and moving application orchestration entirely into dedicated service layers.

2. **Concurrency & Locking Mechanism**:
   - *Initial Output*: Claude initially suggested a global `threading.Lock` around `book_ride`.
   - *Counter-Questioning*: Gemini was tasked with stress-testing this approach under high contention, highlighting that global locking serializes unrelated bookings for different cabs unnecessarily.
   - *Resolution*: Refactored the locking mechanism to use **per-cab fine-grained locking** (a dictionary of `threading.Lock`s managed under a guard lock). Strengthened `tests/test_concurrency.py` to simulate a 20-thread race across 5 cabs to verify lock isolation under actual multi-threaded contention.

3. **Pricing Engine & Free Upgrade Edge Cases**:
   - *Initial Output*: Early iterations calculated upgraded ride fares using the assigned car rate (`car_type_assigned`).
   - *Critique & Refactor*: Cross-checked against the exact spec requirement ("at no extra cost"). Rewrote `end_ride` to explicitly bill trips off `car_type_requested` whenever `is_upgraded=True` is flagged. Added a dedicated regression test (`test_upgrade_is_charged_at_the_originally_requested_hatchback_rate`) to guarantee compliance.

4. **Coupon Calculation & Minimum Fare Boundaries**:
   - *Initial Output*: Flat-discount coupons allowed final fares to drift into negative numbers on short, minimum-fare trips.
   - *Resolution*: Enforced a strict calculation boundary: minimum fare is evaluated first, and discount computation is capped at the trip fare itself (`max(0.0, base_fare - discount)`).

5. **Code Hygiene & Modern Standards**:
   - *Deprecation Fixes*: Detected deprecated `datetime.utcnow()` calls flagged during `pytest` runs and standardized the codebase on timezone-aware `datetime.now(timezone.utc)`.
   - *Precision*: Fixed floating-point rounding mismatches in intermediate surge calculations by rounding final fares at the domain strategy edge.
