# test_backtest_mc_sim.py

# Function: Validate historical feature construction, tuning, calibration,
# simulation reproducibility, and database loading for the backtest model.

# Inputs: Synthetic NBA games, deterministic arrays, and mocked collaborators.

# Output: unittest assertions describing any backtest-model regression.

# Libraries

import unittest
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import numpy as np

import mc_sim
import backtest_mc_sim
from backtest_mc_sim import (
    DEFAULT_WEIGHTS,
    Game,
    HistoryRecord,
    TeamRow,
    build_examples,
    build_matchup_team_inputs,
    calculate_model_weights,
    defensive_four_factors,
    fit_score_calibration,
    normalize_season_type,
    tune_model_weights,
)


# Build one complete team-stat vector with configurable scoring and margin.
def stats(points=100.0, plus_minus=0.0):
    # Preserve the production model's fixed 20-column statistic order.
    return np.array(
        [
            240.0,
            40.0,
            85.0,
            40.0 / 85.0,
            12.0,
            34.0,
            12.0 / 34.0,
            8.0,
            10.0,
            0.8,
            10.0,
            32.0,
            42.0,
            24.0,
            8.0,
            5.0,
            12.0,
            20.0,
            points,
            plus_minus,
        ],
        # Match the compiled simulator's double-precision memory views.
        dtype=np.float64,
    )


# Build a paired home/away game with internally consistent points and margins.
def game(game_id, game_date, home_team, away_team, home_points, away_points):
    # Create the home row and encode the opponent in the matchup string.
    home = TeamRow(
        game_id,
        game_date,
        home_team,
        f"{home_team} vs. {away_team}",
        stats(home_points, home_points - away_points),
        98.0,
    )
    # Create the away row with the inverse score margin.
    away = TeamRow(
        game_id,
        game_date,
        away_team,
        f"{away_team} @ {home_team}",
        stats(away_points, away_points - home_points),
        98.0,
    )
    # Return the completed two-team game consumed by backtest builders.
    return Game(game_id, game_date, home, away)


# Test pure backtest construction, tuning, and simulation behavior.
class BacktestTests(unittest.TestCase):
    # Verify all games on one date share league totals from earlier dates only.
    def test_running_league_totals_preserve_same_day_exclusion(self):
        # Arrange two games per date so same-day leakage would be observable.
        games = [
            game(str(index), date(2026, 1, 1) + timedelta(days=index // 2),
                 "A", "B", 100 + index, 90 + index)
            for index in range(20)
        ]
        # Compare each optimized running-total value with a rebuilt history.
        for example in build_examples(games, 3, 2, 1.0, 5.0):
            # Reconstruct exactly the records completed before this example's date.
            history = [
                HistoryRecord(other.team, row.stats, other.stats, row.pace)
                for previous in games if previous.game_date < example.game_date
                for row, other in ((previous.home, previous.away),
                                   (previous.away, previous.home))
            ]
            # The incremental implementation must match the straightforward reference.
            np.testing.assert_allclose(
                example.league_averages,
                backtest_mc_sim.league_averages(history), rtol=1e-14,
            )

    # Verify frontend spellings map to database-facing canonical season keys.
    def test_frontend_season_types_are_normalized(self):
        # Normalize the preseason label used by the UI.
        self.assertEqual(normalize_season_type("Pre Season"), "preseason")
        # Normalize the regular-season label used by the UI.
        self.assertEqual(normalize_season_type("Regular Season"), "regular")
        # Normalize the postseason label used by the UI.
        self.assertEqual(normalize_season_type("Playoffs"), "playoffs")

    # Verify candidate selection uses later dates before refitting all examples.
    def test_tuner_selects_on_later_dates_and_refits_all_examples(self):
        # Define a recognizable nondefault adjustment candidate.
        candidate = (0.1, 0.2, 0.03, 0.4, 0.05, 0.6, 0.7, 0.08)
        # Create enough dated examples to enable chronological validation.
        examples = [SimpleNamespace(
            game_id=str(index), game_date=date(2026, 1, 1) + timedelta(days=index),
        ) for index in range(48)]
        # Represent raw predictions by identity so slices can be asserted exactly.
        raw = [object() for _ in examples]
        # Combine the candidate with known calibration and context coefficients.
        calibrated_candidate = candidate + (1.1, 2.0) + DEFAULT_WEIGHTS[10:]
        # Return fitted parameters while recording which prediction slice was used.
        def fit_parameters(predictions, adjustments):
            # Preserve candidate adjustments and append deterministic fitted values.
            return np.array(tuple(adjustments) + (1.1, 2.0) + DEFAULT_WEIGHTS[10:])
        # Isolate selection logic from expensive simulation and numeric fitting.
        with (
            patch(
                "backtest_mc_sim.candidate_weights",
                return_value=(DEFAULT_WEIGHTS[:8], candidate),
            ),
            patch(
                "backtest_mc_sim.predict_examples",
                return_value=raw,
            ),
            patch(
                "backtest_mc_sim.fit_prediction_parameters",
                side_effect=fit_parameters,
            ) as fit,
            patch(
                "backtest_mc_sim.apply_prediction_parameters",
                side_effect=lambda predictions, weights: predictions,
            ) as apply,
            patch(
                "backtest_mc_sim.calculate_metrics",
                side_effect=(
                    SimpleNamespace(score_mae=5.0),
                    SimpleNamespace(score_mae=2.0),
                ),
            ),
        ):
            # Tune one random candidate plus the default baseline.
            weights = tune_model_weights(examples, trials=1, iterations=10, seed=7)

        # The lower validation-MAE candidate should be returned after full refit.
        np.testing.assert_array_equal(weights, calibrated_candidate)
        # Recompute the expected date-safe split boundary.
        split = backtest_mc_sim.chronological_split_index(examples, .7)
        # Initial fitting must use only the earlier training slice.
        self.assertEqual(fit.call_args_list[0].args[0], raw[:split])
        # Candidate scoring must apply parameters only to the later slice.
        self.assertEqual(apply.call_args_list[0].args[0], raw[split:])
        # The selected candidate must finally be refit against all examples.
        self.assertTrue(any(call.args[0] == raw for call in fit.call_args_list))

    # Verify calibration can recover a simple shared ten-point score offset.
    def test_calibration_recovers_simple_offset(self):
        # Arrange one game whose two predictions are each ten points low.
        example_one = backtest_mc_sim.BacktestExample(
            "1", date(2026, 1, 1), "A", "B", stats(), stats(), 100.0,
            np.ones(5), np.ones(4), np.ones(4), 100.0, 90.0,
        )
        # Arrange a second game with the same systematic offset.
        example_two = backtest_mc_sim.BacktestExample(
            "2", date(2026, 1, 2), "C", "D", stats(), stats(), 100.0,
            np.ones(5), np.ones(4), np.ones(4), 120.0, 110.0,
        )
        # Pair each actual example with its deliberately low prediction.
        predictions = [
            backtest_mc_sim.Prediction(example_one, 90.0, 80.0),
            backtest_mc_sim.Prediction(example_two, 110.0, 100.0),
        ]
        # Fit the shared linear score calibration.
        scale, intercept = fit_score_calibration(predictions)

        # Equal spread means no multiplicative correction is required.
        self.assertAlmostEqual(scale, 1.0, places=2)
        # The additive correction should recover the missing ten points.
        self.assertAlmostEqual(intercept, 10.0, places=2)

    # Verify a game cannot leak its final statistics into its own prediction.
    def test_current_game_never_changes_its_own_inputs(self):
        # Arrange the only game that may contribute prior history.
        first = game("1", date(2026, 1, 1), "A", "B", 100, 90)
        # Arrange the target game with its original final score.
        second = game("2", date(2026, 1, 2), "B", "A", 105, 95)
        # Create the same target game with dramatically different final stats.
        altered_second = game("2", date(2026, 1, 2), "B", "A", 205, 45)

        # Build examples from original target results.
        original = build_examples([first, second], 20, 1, 1.0, 5.0)
        # Build examples after modifying only the target game's own result.
        altered = build_examples([first, altered_second], 20, 1, 1.0, 5.0)

        # Only the second game has enough prior history to become an example.
        self.assertEqual(len(original), 1)
        # Home features must remain based solely on the first completed game.
        np.testing.assert_array_equal(original[0].home_stats, altered[0].home_stats)
        # Away features must likewise ignore the target game's final stats.
        np.testing.assert_array_equal(original[0].away_stats, altered[0].away_stats)
        # League averages must not include the game currently being predicted.
        np.testing.assert_array_equal(
            original[0].league_averages, altered[0].league_averages
        )

    # Verify a future matchup incorporates the most recently completed game.
    def test_next_matchup_uses_the_latest_completed_game(self):
        # Arrange an initial game with moderate team-A scoring.
        first = game("1", date(2026, 1, 1), "A", "B", 100, 90)
        # Arrange a later game where team A scores substantially more.
        second = game("2", date(2026, 1, 2), "B", "A", 50, 150)

        # Calculate matchup inputs before the later result is available.
        before = build_matchup_team_inputs([first], "A", "B", 20, 1)
        # Recalculate after the later game becomes completed history.
        after = build_matchup_team_inputs([first, second], "A", "B", 20, 1)

        # Team A's averaged points should increase after its 150-point game.
        self.assertGreater(after.team_stats[18], before.team_stats[18])

    # Verify defensive factors are calculated from opponents' offensive results.
    def test_defensive_four_factors_use_opponent_offense(self):
        # Arrange separate own and opponent stat vectors.
        own = stats()
        opponent = stats()
        # Store both perspectives in one historical record.
        record = HistoryRecord("B", own, opponent, 100.0)
        # Calculate the four defensive factors from recent history.
        factors = defensive_four_factors([record], 20)

        # Effective field-goal rate must use opponent makes and attempts.
        self.assertAlmostEqual(factors[0], (40.0 + 0.5 * 12.0) / 85.0)
        # Forced-turnover rate must use opponent actions.
        self.assertAlmostEqual(factors[1], 12.0 / (85.0 + 0.44 * 10.0 + 12.0))
        # Allowed free-throw rate must use opponent attempts.
        self.assertAlmostEqual(factors[2], 10.0 / 85.0)
        # Defensive-rebound share must compare own DREB with opponent OREB.
        self.assertAlmostEqual(factors[3], 32.0 / (32.0 + 10.0))

    # Verify an explicit random seed reproduces the exact simulation result.
    def test_seeded_simulation_is_reproducible(self):
        # Arrange valid team, league, and defense inputs.
        team = stats()
        league = [0.471, 0.360, 0.783, 0.127, 0.305]
        defense = [0.545, 0.127, 0.250, 0.695]
        # Run the compiled simulation once with a fixed seed.
        first = mc_sim.run_monte_carlo_simulation(
            team, team, 98.0, league, defense, 500, DEFAULT_WEIGHTS, 42
        )
        # Repeat the identical simulation with the same fixed seed.
        second = mc_sim.run_monte_carlo_simulation(
            team, team, 98.0, league, defense, 500, DEFAULT_WEIGHTS, 42
        )
        # Per-thread deterministic RNG states should produce equal results.
        self.assertEqual(first, second)

    # Verify omitting weights is equivalent to passing documented defaults.
    def test_default_weights_preserve_unconfigured_result(self):
        # Arrange one valid matchup input set.
        team = stats()
        league = [0.471, 0.360, 0.783, 0.127, 0.305]
        defense = [0.545, 0.127, 0.250, 0.695]
        # Run through the default-argument path.
        unconfigured = mc_sim.run_monte_carlo_simulation(
            team,
            team,
            98.0,
            league,
            defense,
            iterations=500,
            random_seed=73,
        )
        # Run through the explicit-weight path with the same seed.
        configured = mc_sim.run_monte_carlo_simulation(
            team, team, 98.0, league, defense, 500, DEFAULT_WEIGHTS, 73
        )
        # Both configuration paths must preserve the same production behavior.
        self.assertEqual(unconfigured, configured)


# Test asynchronous request wrappers and database row loading.
class RequestWeightTests(unittest.IsolatedAsyncioTestCase):
    # Verify model-weight requests retain the requested season and settings.
    async def test_request_weights_use_requested_season_and_type(self):
        # Arrange recognizable connection, game, example, and weight objects.
        connection = object()
        games = [object()]
        examples = [object() for _ in range(10)]
        expected = np.array(DEFAULT_WEIGHTS, dtype=np.float64)

        # Replace database, feature-building, and worker collaborators.
        with (
            patch("backtest_mc_sim.load_games", new=AsyncMock(return_value=games)) as load,
            patch("backtest_mc_sim.build_examples", return_value=examples) as build,
            patch(
                "backtest_mc_sim.asyncio.to_thread",
                new=AsyncMock(return_value=expected),
            ) as to_thread,
        ):
            # Call the public request helper with nondefault tuning settings.
            weights = await calculate_model_weights(
                connection,
                "2025-26",
                "Regular Season",
                recent_games=12,
                min_prior_games=2,
                tune_trials=4,
                tuning_iterations=50,
                seed=99,
            )

        # Season inputs must be normalized before the database call.
        load.assert_awaited_once_with(connection, "regular", "22025")
        # Example construction must preserve history and matchup settings.
        build.assert_called_once_with(
            games,
            12,
            2,
            matchup_adjustment=1.0,
            matchup_prior_games=5.0,
        )
        # CPU tuning must run off-loop with every requested parameter intact.
        to_thread.assert_awaited_once_with(
            backtest_mc_sim.tune_model_weights,
            examples,
            4,
            50,
            99,
        )
        # The wrapper should return the exact worker result.
        self.assertIs(weights, expected)

    # Verify the loader obtains basic stats and pace through one joined query.
    async def test_game_loader_fetches_stats_and_pace_in_one_query(self):
        # Arrange the home database record for one completed game.
        first = {
            "game_id": "0022500001",
            "game_date": date(2025, 10, 1),
            "team_abbreviation": "A",
            "matchup": "A vs. B",
            "pace": 99.0,
        }
        # Arrange the corresponding away record with the same game id.
        second = {
            "game_id": "0022500001",
            "game_date": date(2025, 10, 1),
            "team_abbreviation": "B",
            "matchup": "B @ A",
            "pace": 98.0,
        }
        # List the 20 database columns converted into each model stat vector.
        stat_columns = (
            "minutes", "field_goals_made", "field_goals_attempted",
            "field_goals_percentage", "field_goal_threes_made",
            "field_goal_threes_attempted", "field_goal_threes_percentage",
            "free_throws_made", "free_throws_attempted",
            "free_throws_percentage", "offensive_rebounds",
            "defensive_rebounds", "rebounds", "assists", "steals",
            "blocks", "turnovers", "personal_fouls", "points", "plus_minus",
        )
        # Populate every required stat field on both mocked records.
        for row in (first, second):
            # A uniform nonzero value keeps conversion simple and valid.
            row.update(dict.fromkeys(stat_columns, 1.0))
        # Expose asyncpg-like fetch behavior without opening a database.
        connection = SimpleNamespace(fetch=AsyncMock(return_value=[first, second]))

        # Load and pair the two records through the real query-processing code.
        games = await backtest_mc_sim.load_games(
            connection, "regular", "22025"
        )

        # Loading one season should execute only one SQL query.
        connection.fetch.assert_awaited_once()
        # Retrieve the exact query text passed to the mocked connection.
        query = connection.fetch.await_args.args[0]
        # The query must join advanced stats so pace arrives in the same fetch.
        self.assertIn("LEFT JOIN nbateamadvancedstatsregseason", query)
        # Two team rows with one game id should produce exactly one Game.
        self.assertEqual(len(games), 1)
        # Preserve the home team's pace from its joined advanced-stat record.
        self.assertEqual(games[0].home.pace, 99.0)
        # Preserve the away team's independently joined pace.
        self.assertEqual(games[0].away.pace, 98.0)


# Support direct execution in addition to external test discovery.
if __name__ == "__main__":
    # Discover and run every test method declared above.
    unittest.main()
