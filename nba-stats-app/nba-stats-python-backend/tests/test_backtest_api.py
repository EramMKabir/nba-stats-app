# test_backtest_api.py

# Function: Verify that the compiled backtest API matches the Python reference
# implementation and safely caches, refreshes, and restores tuned weights.

# Inputs: Deterministic synthetic games plus mocked database and worker calls.

# Output: unittest assertions describing any aggregation or cache regression.

# Libraries

import asyncio
import copy
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import numpy as np

import backtest_api
import backtest_mc_sim


# Build one complete 20-value team-stat row for a synthetic game.
def _stats(offset=0.0):
    # Store values in the same index order consumed by the production model.
    return np.array(
        [
            # Vary scoring-related values through offset while keeping valid rates.
            240.0, 40.0 + offset, 85.0, (40.0 + offset) / 85.0,
            12.0, 34.0, 12.0 / 34.0, 18.0, 22.0, 18.0 / 22.0,
            10.0, 32.0, 42.0, 24.0, 8.0, 5.0, 12.0, 20.0,
            100.0 + offset, offset,
        ],
        # Match the Cython API's contiguous double-precision input type.
        dtype=np.float64,
    )


# Create an alternating home/away series with predictable dates and statistics.
def _games(count=8):
    # Accumulate paired team rows as completed Game objects.
    result = []
    # Give every synthetic game a unique identifier and daily date.
    for index in range(count):
        # Alternate venues so both teams receive home and away history.
        home_team, away_team = ("A", "B") if index % 2 == 0 else ("B", "A")
        # Advance one day per game to preserve chronological ordering.
        game_date = date(2026, 1, 1) + timedelta(days=index)
        # Build the home row with a home-format matchup and rising pace.
        home = backtest_mc_sim.TeamRow(
            str(index), game_date, home_team, f"{home_team} vs. {away_team}",
            _stats(index), 98.0 + index,
        )
        # Build the matching away row with the inverse stat offset.
        away = backtest_mc_sim.TeamRow(
            str(index), game_date, away_team, f"{away_team} @ {home_team}",
            _stats(-index), 97.0 + index,
        )
        # Pair both rows into the completed game expected by aggregation code.
        result.append(backtest_mc_sim.Game(str(index), game_date, home, away))
    # Return the reusable chronological fixture.
    return result


# Compare native aggregation behavior with the authoritative Python version.
class CythonMatchupTests(unittest.TestCase):
    # Confirm every native matchup output equals its Python reference value.
    def test_native_aggregation_matches_python_reference(self):
        # Arrange a shared history for both implementations.
        games = _games()
        # Calculate the expected values with the readable Python implementation.
        expected = backtest_mc_sim.build_matchup_team_inputs(
            games, "A", "B", 5, min_prior_games=2
        )
        # Calculate the actual values with the compiled Cython implementation.
        actual = backtest_api.build_matchup_team_inputs(
            games, "A", "B", 5, min_prior_games=2
        )

        # Pace is scalar, so compare it with floating-point tolerance.
        self.assertAlmostEqual(actual.pace, expected.pace)
        # Check every vector-valued feature produced by the native aggregator.
        for field in (
            "team_stats",
            "opponent_stats",
            "league_averages",
            "team_defense",
            "opponent_defense",
        ):
            # Resolve the same named field from both result objects.
            np.testing.assert_allclose(
                getattr(actual, field), getattr(expected, field), rtol=1e-14
            )

    # Confirm an effectively unlimited recent-game window fits Cython indexes.
    def test_sys_maxsize_recent_window_is_supported(self):
        # Pass sys.maxsize through the public native aggregation entry point.
        result = backtest_api.build_matchup_team_inputs(
            _games(), "A", "B", sys.maxsize, min_prior_games=2
        )

        # The returned team vector must still contain all 20 model statistics.
        self.assertEqual(result.team_stats.shape, (20,))


# Verify the database lookup that aligns matchup and player-stat seasons.
class LatestMatchupSeasonTests(unittest.IsolatedAsyncioTestCase):
    # Confirm the resolver queries the correct phase table and team patterns.
    async def test_latest_common_season_query(self):
        connection = AsyncMock()
        connection.fetchval.return_value = "22024"

        result = await backtest_api._latest_matchup_season_id(
            connection, backtest_mc_sim, "regular", "NYK", "BOS"
        )

        query, team_pattern, opponent_pattern = connection.fetchval.await_args.args
        self.assertIn("FROM nbaplayerstatsregseason", query)
        self.assertIn("HAVING COUNT(*) FILTER", query)
        self.assertEqual((team_pattern, opponent_pattern), ("NYK%", "BOS%"))
        self.assertEqual(result, "22024")

    # Preserve the existing no-data sentinel when no common season exists.
    async def test_no_common_season_returns_none(self):
        connection = AsyncMock()
        connection.fetchval.return_value = None

        result = await backtest_api._latest_matchup_season_id(
            connection, backtest_mc_sim, "playoffs", "NYK", "BOS"
        )

        self.assertIsNone(result)


# Exercise asynchronous loading, tuning, persistence, and cache coordination.
class CythonRequestTests(unittest.IsolatedAsyncioTestCase):
    # Give each test empty in-memory caches and an isolated persistence file.
    def setUp(self):
        # Remove state retained by earlier API tests.
        backtest_api.clear_model_weights_cache()
        # Create a directory that unittest will delete after this test.
        directory = tempfile.TemporaryDirectory()
        # Register cleanup even when an assertion interrupts the test.
        self.addCleanup(directory.cleanup)
        # Redirect weight persistence away from the project checkout.
        self.weights_path = Path(directory.name) / "model_weights.json"
        # Patch both the disk path and its parsed in-memory representation.
        for name, value in (("MODEL_WEIGHTS_PATH", self.weights_path),
                            ("_saved_model_weights", {})):
            # Build a reversible patch for the selected module attribute.
            setting = patch.object(backtest_api, name, value)
            # Apply the isolated value before the test begins.
            setting.start()
            # Guarantee restoration of the original module attribute.
            self.addCleanup(setting.stop)
        # Keep existing request tests independent of the new database lookup.
        latest_season = patch.object(
            backtest_api,
            "_latest_matchup_season_id",
            new=AsyncMock(
                side_effect=lambda connection, backtest, canonical, team, opponent:
                f"{backtest.SEASON_TYPES[canonical][1]}2025"
            ),
        )
        # Retain the mock so fallback-specific tests can select another season.
        self.latest_season = latest_season.start()
        # Restore the real resolver after every request test.
        self.addCleanup(latest_season.stop)

    # Verify a refresh is atomic from the perspective of concurrent requests.
    async def test_requests_use_previous_snapshot_until_refresh_finishes(self):
        # Arrange an original season snapshot and a corrected replacement.
        games = _games()
        changed = copy.deepcopy(games)
        # Change one source statistic so the two snapshots have distinct hashes.
        changed[0].home.stats[1] += 5.0
        # Use recognizable arrays for the original and replacement weights.
        initial = np.array(backtest_mc_sim.DEFAULT_WEIGHTS, dtype=np.float64)
        replacement = initial + 10.0
        # Coordinate the refresh worker so a request can run mid-refresh.
        started, finish = asyncio.Event(), asyncio.Event()

        # Return initial weights immediately but pause replacement tuning.
        async def tune(*args):
            # Identify the first tuning call by its original games object.
            if args[1] is games:
                return initial
            # Signal that refresh tuning has begun.
            started.set()
            # Keep the new snapshot unpublished until the test permits it.
            await finish.wait()
            # Finish with the unmistakable replacement vector.
            return replacement

        # Wrap the combined public call to keep each request identical.
        async def request():
            # Ask for the full available synthetic history.
            return await backtest_api.calculate_matchup_inputs_and_model_weights(
                object(), "2025-26", "Regular Season", "A", "B", sys.maxsize
            )

        # Replace database loading and worker execution with controlled mocks.
        with (
            patch("backtest_mc_sim.load_games",
                  new=AsyncMock(side_effect=[games, changed])) as load,
            patch("backtest_api.asyncio.to_thread",
                  new=AsyncMock(side_effect=tune)) as worker,
        ):
            # Prime both caches with the initial snapshot and its weights.
            previous_inputs, _ = await request()
            # Begin refreshing the corrected snapshot in the background.
            refresh = asyncio.create_task(backtest_api.refresh_model_weights(
                object(), "2025-26", "Regular Season", sys.maxsize
            ))
            # Always release the paused refresh, even if the assertions fail.
            try:
                # Wait until the replacement is actively being tuned.
                await started.wait()
                # Issue a normal request while only the old snapshot is publishable.
                inputs, weights = await asyncio.wait_for(request(), timeout=1)
                # The in-flight request must reuse the last completed weights.
                self.assertIs(weights, initial)
                # Its feature data must also come from the matching old snapshot.
                np.testing.assert_array_equal(inputs.team_stats, previous_inputs.team_stats)
            finally:
                # Allow refresh tuning to finish.
                finish.set()
                # Observe refresh completion so no task leaks beyond the test.
                await refresh
            # A subsequent request must see the atomically published replacement.
            updated_inputs, weights = await request()
            # Verify the cache now exposes the newly tuned object.
            self.assertIs(weights, replacement)
            # Verify the corrected game changed the published matchup features.
            self.assertNotEqual(updated_inputs.team_stats[1], previous_inputs.team_stats[1])
        # Only the initial load and explicit refresh should touch the loader.
        self.assertEqual(load.await_count, 2)
        # Each distinct snapshot should be tuned exactly once.
        self.assertEqual(worker.await_count, 2)

    # Verify frontend season labels are normalized before database loading.
    async def test_matchup_request_uses_normalized_season(self):
        # Arrange enough games for both teams to satisfy the history threshold.
        games = _games()
        # Return the fixture without using a real database connection.
        with patch(
            "backtest_mc_sim.load_games", new=AsyncMock(return_value=games)
        ) as load:
            # Request matchup inputs through the asynchronous API wrapper.
            result = await backtest_api.calculate_matchup_team_inputs(
                object(), "2025-26", "Regular Season", "A", "B", 5
            )

        # The loader must receive the canonical type and derived season id.
        load.assert_awaited_once_with(unittest.mock.ANY, "regular", "22025")
        # Successful aggregation returns the complete stat vector.
        self.assertEqual(result.team_stats.shape, (20,))

    # Verify matchup requests load the latest season shared by both teams.
    async def test_combined_request_uses_latest_common_season(self):
        # Make the resolver select an older season than the frontend requested.
        self.latest_season.side_effect = None
        self.latest_season.return_value = "22024"
        games = _games()
        expected_weights = np.array(backtest_mc_sim.DEFAULT_WEIGHTS, dtype=np.float64)
        connection = object()
        # Isolate season selection from database loading and model tuning.
        with (
            patch(
                "backtest_mc_sim.load_games", new=AsyncMock(return_value=games)
            ) as load,
            patch(
                "backtest_api.asyncio.to_thread",
                new=AsyncMock(return_value=expected_weights),
            ),
        ):
            matchup, weights = (
                await backtest_api.calculate_matchup_inputs_and_model_weights(
                    connection, "2025-26", "Regular Season", "A", "B", 5
                )
            )

        # The history loader must receive the season chosen for both teams.
        load.assert_awaited_once_with(connection, "regular", "22024")
        self.assertEqual(matchup.team_stats.shape, (20,))
        self.assertIs(weights, expected_weights)

    # Verify every tuning parameter crosses the async worker boundary unchanged.
    async def test_weight_request_preserves_training_split(self):
        # Arrange a season history and recognizable worker result.
        games = _games()
        expected = np.array(backtest_mc_sim.DEFAULT_WEIGHTS, dtype=np.float64)
        # Isolate both database I/O and CPU-bound tuning.
        with (
            patch(
                "backtest_mc_sim.load_games", new=AsyncMock(return_value=games)
            ) as load,
            patch(
                "backtest_api.asyncio.to_thread",
                new=AsyncMock(return_value=expected),
            ) as to_thread,
        ):
            # Pass nondefault values so argument loss or reordering is visible.
            actual = await backtest_api.calculate_model_weights(
                object(), "2025-26", "Playoffs", 12, 2, 4, 50, 99
            )

        # The worker must receive the loaded games and all requested settings.
        to_thread.assert_awaited_once_with(
            backtest_api._build_and_tune_model_weights,
            games,
            12,
            2,
            4,
            50,
            99,
        )
        # The API should return the worker's array without replacing it.
        self.assertIs(actual, expected)

    # Verify the combined endpoint does not load identical history twice.
    async def test_combined_request_loads_games_once(self):
        # Arrange shared history, weights, and a stable connection identity.
        games = _games()
        expected_weights = np.array(backtest_mc_sim.DEFAULT_WEIGHTS, dtype=np.float64)
        connection = object()
        # Mock the one database load and the one CPU tuning call.
        with (
            patch(
                "backtest_mc_sim.load_games", new=AsyncMock(return_value=games)
            ) as load,
            patch(
                "backtest_api.asyncio.to_thread",
                new=AsyncMock(return_value=expected_weights),
            ),
        ):
            # Request features and model weights in one operation.
            matchup, weights = (
                await backtest_api.calculate_matchup_inputs_and_model_weights(
                    connection,
                    "2025-26",
                    "Regular Season",
                    "A",
                    "B",
                    sys.maxsize,
                    min_prior_games=2,
                )
            )

        # Combined calculation must fetch this season snapshot only once.
        load.assert_awaited_once_with(connection, "regular", "22025")
        # The feature result must have the expected model width.
        self.assertEqual(matchup.team_stats.shape, (20,))
        # The returned weights should be the exact tuned array.
        self.assertIs(weights, expected_weights)

    # Verify repeated combined requests reuse the completed tuning result.
    async def test_combined_request_reuses_snapshot_weights(self):
        # Arrange one immutable season snapshot and its expected weights.
        games = _games()
        expected_weights = np.array(backtest_mc_sim.DEFAULT_WEIGHTS, dtype=np.float64)
        connection = object()
        # Keep loading and tuning observable without external dependencies.
        with (
            patch(
                "backtest_mc_sim.load_games", new=AsyncMock(return_value=games)
            ) as load,
            patch(
                "backtest_api.asyncio.to_thread",
                new=AsyncMock(return_value=expected_weights),
            ) as to_thread,
        ):
            # Make the same request twice against the same cache key.
            for _ in range(2):
                await backtest_api.calculate_matchup_inputs_and_model_weights(
                    connection,
                    "2025-26",
                    "Regular Season",
                    "A",
                    "B",
                    sys.maxsize,
                    min_prior_games=2,
                )

        # A completed result should prevent a second CPU-bound tuning call.
        self.assertEqual(to_thread.await_count, 1)

    # Verify simultaneous cache misses share one in-flight tuning task.
    async def test_concurrent_requests_share_one_tuning_task(self):
        # Arrange a common snapshot and result for all concurrent callers.
        games = _games()
        expected_weights = np.array(backtest_mc_sim.DEFAULT_WEIGHTS, dtype=np.float64)

        # Keep tuning pending briefly so all requests encounter the same task.
        async def delayed_weights(*args):
            # Yield control and let the other requests reach the cache lookup.
            await asyncio.sleep(0.01)
            # Resolve every waiter with the shared weight object.
            return expected_weights

        # Replace I/O and thread dispatch with deterministic async mocks.
        with (
            patch(
                "backtest_mc_sim.load_games", new=AsyncMock(return_value=games)
            ),
            patch(
                "backtest_api.asyncio.to_thread",
                new=AsyncMock(side_effect=delayed_weights),
            ) as to_thread,
        ):
            # Start four identical requests together.
            await asyncio.gather(
                *(
                    backtest_api.calculate_matchup_inputs_and_model_weights(
                        object(),
                        "2025-26",
                        "Playoffs",
                        "A",
                        "B",
                        sys.maxsize,
                        min_prior_games=2,
                    )
                    for _ in range(4)
                )
            )

        # The first request creates the task and the other three must reuse it.
        self.assertEqual(to_thread.await_count, 1)

    # Verify startup warmup fills a distinct cache entry for each season type.
    async def test_startup_warms_all_three_request_cache_keys(self):
        # Arrange reusable history and weights for the three supported phases.
        games = _games()
        expected_weights = np.array(backtest_mc_sim.DEFAULT_WEIGHTS, dtype=np.float64)
        connection = object()
        season_types = ("Pre Season", "Regular Season", "Playoffs")

        # Count database and tuning calls while avoiding real external work.
        with (
            patch(
                "backtest_mc_sim.load_games", new=AsyncMock(return_value=games)
            ) as load,
            patch(
                "backtest_api.asyncio.to_thread",
                new=AsyncMock(return_value=expected_weights),
            ) as to_thread,
        ):
            # Warm one model-weight cache entry for every frontend season label.
            for season_type in season_types:
                await backtest_api.calculate_model_weights(
                    connection,
                    "2025-26",
                    season_type,
                    recent_games=sys.maxsize,
                    min_prior_games=1,
                )

            # Confirm combined requests reuse all three warmed entries.
            for season_type in season_types:
                await backtest_api.calculate_matchup_inputs_and_model_weights(
                    connection,
                    "2025-26",
                    season_type,
                    "A",
                    "B",
                    recent_games=sys.maxsize,
                    min_prior_games=1,
                )

        # Each season type should tune once during warmup and never afterward.
        self.assertEqual(to_thread.await_count, 3)
        # Each season type should likewise load one historical snapshot.
        self.assertEqual(load.await_count, 3)

    # Verify explicit refresh replaces both snapshot and weights together.
    async def test_refresh_atomically_replaces_cached_weights(self):
        # Arrange original and corrected histories with distinct fingerprints.
        games = _games()
        changed_games = copy.deepcopy(games)
        # Change one made-shot value in the replacement snapshot.
        changed_games[0].home.stats[1] += 1.0
        # Make the two tuning results distinguishable by identity and value.
        initial_weights = np.array(backtest_mc_sim.DEFAULT_WEIGHTS, dtype=np.float64)
        refreshed_weights = initial_weights + 10.0
        connection = object()

        # Return snapshots and weights in the same order as initial/refresh calls.
        with (
            patch(
                "backtest_mc_sim.load_games",
                new=AsyncMock(side_effect=(games, changed_games)),
            ) as load,
            patch(
                "backtest_api.asyncio.to_thread",
                new=AsyncMock(
                    side_effect=(initial_weights, refreshed_weights)
                ),
            ) as to_thread,
        ):
            # Populate the cache from the original history.
            first = await backtest_api.calculate_model_weights(
                connection,
                "2025-26",
                "Regular Season",
                recent_games=sys.maxsize,
                min_prior_games=1,
            )
            # Reload and publish the corrected history and replacement weights.
            refreshed = await backtest_api.refresh_model_weights(
                connection,
                "2025-26",
                "Regular Season",
                recent_games=sys.maxsize,
                min_prior_games=1,
            )
            # Read through the normal combined endpoint after publication.
            _, reused = (
                await backtest_api.calculate_matchup_inputs_and_model_weights(
                    connection,
                    "2025-26",
                    "Regular Season",
                    "A",
                    "B",
                    recent_games=sys.maxsize,
                    min_prior_games=1,
                )
            )

        # Preserve exact worker objects throughout the cache lifecycle.
        self.assertIs(first, initial_weights)
        self.assertIs(refreshed, refreshed_weights)
        self.assertIs(reused, refreshed_weights)
        # One tuning call is required for each distinct snapshot.
        self.assertEqual(to_thread.await_count, 2)
        # Initial calculation and refresh should each load once.
        self.assertEqual(load.await_count, 2)

    # Verify an unchanged refresh reuses memory or persisted weights without tuning.
    async def test_refresh_reuses_unchanged_memory_and_saved_weights(self):
        # Arrange a stable result for every load of an equivalent game snapshot.
        expected = np.array(backtest_mc_sim.DEFAULT_WEIGHTS, dtype=np.float64)
        # Return a fresh but value-equivalent games list on every loader call.
        with (
            patch("backtest_mc_sim.load_games",
                  new=AsyncMock(side_effect=lambda *args: _games())) as load,
            patch("backtest_api.asyncio.to_thread",
                  new=AsyncMock(return_value=expected)) as tune,
        ):
            # Tune and cache the initial snapshot.
            first = await backtest_api.calculate_model_weights(
                object(), "2025-26", "Regular Season"
            )
            # Observe persistence calls while refreshing the unchanged snapshot.
            with patch("backtest_api._save_model_weights") as save:
                # An in-memory fingerprint match should return the original object.
                refreshed = await backtest_api.refresh_model_weights(
                    object(), "2025-26", "Regular Season"
                )
                # Confirm refresh reused the already cached array.
                self.assertIs(refreshed, first)
                # Simulate a process restart by discarding only runtime caches.
                backtest_api.clear_model_weights_cache()
                # Refresh again so the saved-weight representation is consulted.
                restored = await backtest_api.refresh_model_weights(
                    object(), "2025-26", "Regular Season"
                )
                # Restored numeric weights must equal the original tuning result.
                np.testing.assert_array_equal(restored, first)
                # Neither unchanged path should rewrite the persistence file.
                save.assert_not_called()
        # Only the initial request should have invoked the tuner.
        self.assertEqual(tune.await_count, 1)
        # Initial, in-memory refresh, and restart refresh each reload history.
        self.assertEqual(load.await_count, 3)


    # Verify saved weights survive restart but invalidate on data or setting changes.
    async def test_restart_reuses_weights_and_corrected_data_retunes(self):
        # Arrange original and corrected snapshots.
        games = _games()
        corrected = copy.deepcopy(games)
        # Change a turnover so the corrected snapshot receives a new fingerprint.
        corrected[0].away.stats[16] += 1.0
        # Use deterministic weights and a fixed set of cache-key parameters.
        expected = np.array(backtest_mc_sim.DEFAULT_WEIGHTS, dtype=np.float64)
        parameters = (sys.maxsize, 1, 25, 750, 20260709)
        # Mock season loading and CPU tuning while exercising real persistence.
        with (
            patch("backtest_mc_sim.load_games", new=AsyncMock(return_value=games)) as load,
            patch("backtest_api.asyncio.to_thread", new=AsyncMock(return_value=expected)) as tune,
        ):
            # Tune and save the original season snapshot.
            first = await backtest_api.calculate_model_weights(
                object(), "2021-22", "Regular Season", *parameters
            )
            # Clear volatile caches to model a restarted process.
            backtest_api.clear_model_weights_cache()
            # Reload the just-written persistence file into module state.
            backtest_api._saved_model_weights = backtest_api._read_saved_model_weights()
            # Request the exact same snapshot and tuning configuration.
            restored = await backtest_api.calculate_model_weights(
                object(), "2021-22", "Regular Season", *parameters
            )
            # Persistence should avoid a second tuning job.
            self.assertEqual(tune.await_count, 1)
            # The reconstructed array must preserve every saved weight.
            np.testing.assert_array_equal(restored, first)
            # Clear runtime state before presenting corrected historical data.
            backtest_api.clear_model_weights_cache()
            # Make future loads return the fingerprint-changing correction.
            load.return_value = corrected
            # Corrected source data must invalidate the saved weight entry.
            await backtest_api.calculate_model_weights(
                object(), "2021-22", "Regular Season", *parameters
            )
            # The changed snapshot should trigger exactly one new tuning call.
            self.assertEqual(tune.await_count, 2)
            # Change tune_trials to prove settings also participate in the key.
            await backtest_api.calculate_model_weights(
                object(), "2021-22", "Regular Season", sys.maxsize, 1, 26, 750, 20260709
            )
            # Distinct tuning settings require another independent model fit.
            self.assertEqual(tune.await_count, 3)

    # Verify malformed persisted JSON is ignored and replaced by valid weights.
    async def test_invalid_weights_file_is_rebuilt(self):
        # Write deliberately incomplete JSON to the isolated persistence path.
        self.weights_path.write_text('{"incomplete":')
        # Re-run the production parser, which should safely return an empty mapping.
        backtest_api._saved_model_weights = backtest_api._read_saved_model_weights()
        # Supply valid history and a deterministic rebuilt weight vector.
        with (
            patch("backtest_mc_sim.load_games", new=AsyncMock(return_value=_games())),
            patch("backtest_api.asyncio.to_thread",
                  new=AsyncMock(return_value=np.array(backtest_mc_sim.DEFAULT_WEIGHTS, dtype=np.float64))) as tune,
        ):
            # A normal request should recover by tuning instead of propagating JSON errors.
            weights = await backtest_api.calculate_model_weights(
                object(), "2021-22", "Regular Season"
            )
        # Recovery requires exactly one tuning invocation.
        self.assertEqual(tune.await_count, 1)
        # The newly written persistence entry must contain the rebuilt weights.
        np.testing.assert_array_equal(
            next(iter(backtest_api._read_saved_model_weights().values()))["weights"], weights
        )



# Run this module directly through unittest as well as through test discovery.
if __name__ == "__main__":
    # Discover and execute every TestCase method in this file.
    unittest.main()
