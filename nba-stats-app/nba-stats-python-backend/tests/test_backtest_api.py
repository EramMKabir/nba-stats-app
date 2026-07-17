import asyncio
import sys
import unittest
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import numpy as np

import backtest_api
import backtest_mc_sim


def _stats(offset=0.0):
    return np.array(
        [
            240.0, 40.0 + offset, 85.0, (40.0 + offset) / 85.0,
            12.0, 34.0, 12.0 / 34.0, 18.0, 22.0, 18.0 / 22.0,
            10.0, 32.0, 42.0, 24.0, 8.0, 5.0, 12.0, 20.0,
            100.0 + offset, offset,
        ],
        dtype=np.float64,
    )


def _games(count=8):
    result = []
    for index in range(count):
        home_team, away_team = ("A", "B") if index % 2 == 0 else ("B", "A")
        game_date = date(2026, 1, 1) + timedelta(days=index)
        home = backtest_mc_sim.TeamRow(
            str(index), game_date, home_team, f"{home_team} vs. {away_team}",
            _stats(index), 98.0 + index,
        )
        away = backtest_mc_sim.TeamRow(
            str(index), game_date, away_team, f"{away_team} @ {home_team}",
            _stats(-index), 97.0 + index,
        )
        result.append(backtest_mc_sim.Game(str(index), game_date, home, away))
    return result


class CythonMatchupTests(unittest.TestCase):
    def test_native_aggregation_matches_python_reference(self):
        games = _games()
        expected = backtest_mc_sim.build_matchup_team_inputs(
            games, "A", "B", 5, min_prior_games=2
        )
        actual = backtest_api.build_matchup_team_inputs(
            games, "A", "B", 5, min_prior_games=2
        )

        self.assertAlmostEqual(actual.pace, expected.pace)
        for field in (
            "team_stats",
            "opponent_stats",
            "league_averages",
            "team_defense",
            "opponent_defense",
        ):
            np.testing.assert_allclose(
                getattr(actual, field), getattr(expected, field), rtol=1e-14
            )

    def test_sys_maxsize_recent_window_is_supported(self):
        result = backtest_api.build_matchup_team_inputs(
            _games(), "A", "B", sys.maxsize, min_prior_games=2
        )

        self.assertEqual(result.team_stats.shape, (20,))


class CythonRequestTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        backtest_api.clear_model_weights_cache()

    async def test_matchup_request_uses_normalized_season(self):
        games = _games()
        with patch(
            "backtest_mc_sim.load_games", new=AsyncMock(return_value=games)
        ) as load:
            result = await backtest_api.calculate_matchup_team_inputs(
                object(), "2025-26", "Regular Season", "A", "B", 5
            )

        load.assert_awaited_once_with(unittest.mock.ANY, "regular", "22025")
        self.assertEqual(result.team_stats.shape, (20,))

    async def test_weight_request_preserves_training_split(self):
        games = _games()
        expected = np.arange(10, dtype=np.float64)
        with (
            patch(
                "backtest_mc_sim.load_games", new=AsyncMock(return_value=games)
            ) as load,
            patch(
                "backtest_api.asyncio.to_thread",
                new=AsyncMock(return_value=expected),
            ) as to_thread,
        ):
            actual = await backtest_api.calculate_model_weights(
                object(), "2025-26", "Playoffs", 12, 2, 4, 50, 99
            )

        to_thread.assert_awaited_once_with(
            backtest_api._build_and_tune_model_weights,
            games,
            12,
            2,
            4,
            50,
            99,
        )
        self.assertIs(actual, expected)

    async def test_combined_request_loads_games_once(self):
        games = _games()
        expected_weights = np.arange(10, dtype=np.float64)
        connection = object()
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
                    connection,
                    "2025-26",
                    "Regular Season",
                    "A",
                    "B",
                    sys.maxsize,
                    min_prior_games=2,
                )
            )

        load.assert_awaited_once_with(connection, "regular", "22025")
        self.assertEqual(matchup.team_stats.shape, (20,))
        self.assertIs(weights, expected_weights)

    async def test_combined_request_reuses_snapshot_weights(self):
        games = _games()
        expected_weights = np.arange(10, dtype=np.float64)
        connection = object()
        with (
            patch(
                "backtest_mc_sim.load_games", new=AsyncMock(return_value=games)
            ) as load,
            patch(
                "backtest_api.asyncio.to_thread",
                new=AsyncMock(return_value=expected_weights),
            ) as to_thread,
        ):
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

        self.assertEqual(to_thread.await_count, 1)

    async def test_concurrent_requests_share_one_tuning_task(self):
        games = _games()
        expected_weights = np.arange(10, dtype=np.float64)

        async def delayed_weights(*args):
            await asyncio.sleep(0.01)
            return expected_weights

        with (
            patch(
                "backtest_mc_sim.load_games", new=AsyncMock(return_value=games)
            ),
            patch(
                "backtest_api.asyncio.to_thread",
                new=AsyncMock(side_effect=delayed_weights),
            ) as to_thread,
        ):
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

        self.assertEqual(to_thread.await_count, 1)

    async def test_startup_warms_all_three_request_cache_keys(self):
        games = _games()
        expected_weights = np.arange(10, dtype=np.float64)
        connection = object()
        season_types = ("Pre Season", "Regular Season", "Playoffs")

        with (
            patch(
                "backtest_mc_sim.load_games", new=AsyncMock(return_value=games)
            ) as load,
            patch(
                "backtest_api.asyncio.to_thread",
                new=AsyncMock(return_value=expected_weights),
            ) as to_thread,
        ):
            for season_type in season_types:
                await backtest_api.calculate_model_weights(
                    connection,
                    "2025-26",
                    season_type,
                    recent_games=sys.maxsize,
                    min_prior_games=1,
                )

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

        self.assertEqual(to_thread.await_count, 3)
        self.assertEqual(load.await_count, 3)

    async def test_refresh_atomically_replaces_cached_weights(self):
        games = _games()
        initial_weights = np.arange(10, dtype=np.float64)
        refreshed_weights = initial_weights + 10.0
        connection = object()

        with (
            patch(
                "backtest_mc_sim.load_games", new=AsyncMock(return_value=games)
            ) as load,
            patch(
                "backtest_api.asyncio.to_thread",
                new=AsyncMock(
                    side_effect=(initial_weights, refreshed_weights)
                ),
            ) as to_thread,
        ):
            first = await backtest_api.calculate_model_weights(
                connection,
                "2025-26",
                "Regular Season",
                recent_games=sys.maxsize,
                min_prior_games=1,
            )
            refreshed = await backtest_api.refresh_model_weights(
                connection,
                "2025-26",
                "Regular Season",
                recent_games=sys.maxsize,
                min_prior_games=1,
            )
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

        self.assertIs(first, initial_weights)
        self.assertIs(refreshed, refreshed_weights)
        self.assertIs(reused, refreshed_weights)
        self.assertEqual(to_thread.await_count, 2)
        self.assertEqual(load.await_count, 2)


if __name__ == "__main__":
    unittest.main()
