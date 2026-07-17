import unittest
from datetime import date
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


def stats(points=100.0, plus_minus=0.0):
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
        dtype=np.float64,
    )


def game(game_id, game_date, home_team, away_team, home_points, away_points):
    home = TeamRow(
        game_id,
        game_date,
        home_team,
        f"{home_team} vs. {away_team}",
        stats(home_points, home_points - away_points),
        98.0,
    )
    away = TeamRow(
        game_id,
        game_date,
        away_team,
        f"{away_team} @ {home_team}",
        stats(away_points, away_points - home_points),
        98.0,
    )
    return Game(game_id, game_date, home, away)


class BacktestTests(unittest.TestCase):
    def test_frontend_season_types_are_normalized(self):
        self.assertEqual(normalize_season_type("Pre Season"), "preseason")
        self.assertEqual(normalize_season_type("Regular Season"), "regular")
        self.assertEqual(normalize_season_type("Playoffs"), "playoffs")

    def test_tuner_selects_lowest_mae_candidate(self):
        candidate = (0.1, 0.2, 0.03, 0.4, 0.05, 0.6, 0.7, 0.08)
        examples = [object()]
        calibrated_candidate = candidate + (1.1, 2.0)
        with (
            patch(
                "backtest_mc_sim.candidate_weights",
                return_value=(DEFAULT_WEIGHTS[:8], candidate),
            ),
            patch(
                "backtest_mc_sim.predict_examples",
                side_effect=([object()], [object()]),
            ),
            patch(
                "backtest_mc_sim.fit_score_calibration",
                side_effect=((1.0, 0.0), (1.1, 2.0)),
            ),
            patch(
                "backtest_mc_sim.apply_score_calibration",
                side_effect=([object()], [object()]),
            ),
            patch(
                "backtest_mc_sim.calculate_metrics",
                side_effect=(
                    SimpleNamespace(score_mae=5.0),
                    SimpleNamespace(score_mae=2.0),
                ),
            ),
        ):
            weights = tune_model_weights(examples, trials=1, iterations=10, seed=7)

        np.testing.assert_array_equal(weights, calibrated_candidate)

    def test_calibration_recovers_simple_offset(self):
        example_one = backtest_mc_sim.BacktestExample(
            "1", date(2026, 1, 1), "A", "B", stats(), stats(), 100.0,
            np.ones(5), np.ones(4), np.ones(4), 100.0, 90.0,
        )
        example_two = backtest_mc_sim.BacktestExample(
            "2", date(2026, 1, 2), "C", "D", stats(), stats(), 100.0,
            np.ones(5), np.ones(4), np.ones(4), 120.0, 110.0,
        )
        predictions = [
            backtest_mc_sim.Prediction(example_one, 90.0, 80.0),
            backtest_mc_sim.Prediction(example_two, 110.0, 100.0),
        ]
        scale, intercept = fit_score_calibration(predictions)

        self.assertAlmostEqual(scale, 1.0, places=2)
        self.assertAlmostEqual(intercept, 10.0, places=2)

    def test_current_game_never_changes_its_own_inputs(self):
        first = game("1", date(2026, 1, 1), "A", "B", 100, 90)
        second = game("2", date(2026, 1, 2), "B", "A", 105, 95)
        altered_second = game("2", date(2026, 1, 2), "B", "A", 205, 45)

        original = build_examples([first, second], 20, 1, 1.0, 5.0)
        altered = build_examples([first, altered_second], 20, 1, 1.0, 5.0)

        self.assertEqual(len(original), 1)
        np.testing.assert_array_equal(original[0].home_stats, altered[0].home_stats)
        np.testing.assert_array_equal(original[0].away_stats, altered[0].away_stats)
        np.testing.assert_array_equal(
            original[0].league_averages, altered[0].league_averages
        )

    def test_next_matchup_uses_the_latest_completed_game(self):
        first = game("1", date(2026, 1, 1), "A", "B", 100, 90)
        second = game("2", date(2026, 1, 2), "B", "A", 50, 150)

        before = build_matchup_team_inputs([first], "A", "B", 20, 1)
        after = build_matchup_team_inputs([first, second], "A", "B", 20, 1)

        self.assertGreater(after.team_stats[18], before.team_stats[18])

    def test_defensive_four_factors_use_opponent_offense(self):
        own = stats()
        opponent = stats()
        record = HistoryRecord("B", own, opponent, 100.0)
        factors = defensive_four_factors([record], 20)

        self.assertAlmostEqual(factors[0], (40.0 + 0.5 * 12.0) / 85.0)
        self.assertAlmostEqual(factors[1], 12.0 / (85.0 + 0.44 * 10.0 + 12.0))
        self.assertAlmostEqual(factors[2], 10.0 / 85.0)
        self.assertAlmostEqual(factors[3], 32.0 / (32.0 + 10.0))

    def test_seeded_simulation_is_reproducible(self):
        team = stats()
        league = [0.471, 0.360, 0.783, 0.127, 0.305]
        defense = [0.545, 0.127, 0.250, 0.695]
        first = mc_sim.run_monte_carlo_simulation(
            team, team, 98.0, league, defense, 500, DEFAULT_WEIGHTS, 42
        )
        second = mc_sim.run_monte_carlo_simulation(
            team, team, 98.0, league, defense, 500, DEFAULT_WEIGHTS, 42
        )
        self.assertEqual(first, second)

    def test_default_weights_preserve_unconfigured_result(self):
        team = stats()
        league = [0.471, 0.360, 0.783, 0.127, 0.305]
        defense = [0.545, 0.127, 0.250, 0.695]
        unconfigured = mc_sim.run_monte_carlo_simulation(
            team,
            team,
            98.0,
            league,
            defense,
            iterations=500,
            random_seed=73,
        )
        configured = mc_sim.run_monte_carlo_simulation(
            team, team, 98.0, league, defense, 500, DEFAULT_WEIGHTS, 73
        )
        self.assertEqual(unconfigured, configured)


class RequestWeightTests(unittest.IsolatedAsyncioTestCase):
    async def test_request_weights_use_requested_season_and_type(self):
        connection = object()
        games = [object()]
        examples = [object() for _ in range(10)]
        training = examples[:7]
        expected = np.array(DEFAULT_WEIGHTS, dtype=np.float64)

        with (
            patch("backtest_mc_sim.load_games", new=AsyncMock(return_value=games)) as load,
            patch("backtest_mc_sim.build_examples", return_value=examples) as build,
            patch(
                "backtest_mc_sim.asyncio.to_thread",
                new=AsyncMock(return_value=expected),
            ) as to_thread,
        ):
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

        load.assert_awaited_once_with(connection, "regular", "22025")
        build.assert_called_once_with(
            games,
            12,
            2,
            matchup_adjustment=1.0,
            matchup_prior_games=5.0,
        )
        to_thread.assert_awaited_once_with(
            backtest_mc_sim.tune_model_weights,
            training,
            4,
            50,
            99,
        )
        self.assertIs(weights, expected)

    async def test_game_loader_fetches_stats_and_pace_in_one_query(self):
        first = {
            "game_id": "0022500001",
            "game_date": date(2025, 10, 1),
            "team_abbreviation": "A",
            "matchup": "A vs. B",
            "pace": 99.0,
        }
        second = {
            "game_id": "0022500001",
            "game_date": date(2025, 10, 1),
            "team_abbreviation": "B",
            "matchup": "B @ A",
            "pace": 98.0,
        }
        stat_columns = (
            "minutes", "field_goals_made", "field_goals_attempted",
            "field_goals_percentage", "field_goal_threes_made",
            "field_goal_threes_attempted", "field_goal_threes_percentage",
            "free_throws_made", "free_throws_attempted",
            "free_throws_percentage", "offensive_rebounds",
            "defensive_rebounds", "rebounds", "assists", "steals",
            "blocks", "turnovers", "personal_fouls", "points", "plus_minus",
        )
        for row in (first, second):
            row.update(dict.fromkeys(stat_columns, 1.0))
        connection = SimpleNamespace(fetch=AsyncMock(return_value=[first, second]))

        games = await backtest_mc_sim.load_games(
            connection, "regular", "22025"
        )

        connection.fetch.assert_awaited_once()
        query = connection.fetch.await_args.args[0]
        self.assertIn("LEFT JOIN nbateamadvancedstatsregseason", query)
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0].home.pace, 99.0)
        self.assertEqual(games[0].away.pace, 98.0)


if __name__ == "__main__":
    unittest.main()
