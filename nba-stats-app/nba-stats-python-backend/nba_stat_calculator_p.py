#!/usr/bin/env python
# coding: utf-8

# In[ ]:


# nba_stat_calculator_p.py

# Function: Return official NBA stats or calculated NBA stats to the frontend.

# Inputs:

# Frontend data that was passed as follows:

# Frontend -> Backend (api.py) -> This file

# Which consists of:

# Player Full Name, Season, Season Type, Opposing Team Abbreviation, Recent Games, and a connection pool (cur)

# Output:

# Calculated NBA stats or Official NBA stats.

# Time complexity:

# player_ids_to_player: O(n), where n is the number of NBA players.

# round_to_one_decimal_place: O(1)

# neg_num_to_zero: O(1)

# get_player_id: O(n*k), where n is the number of players that were in the NBA at any point, and k is the number of characters in the player's full name.

# create_player_games_stat_avg_series: O(n*k), where n is the number of rows in the input dataframe, and k is the number of columns that are operated on in the filtered dataframe.

# get_player_deltas: O(n*k), where n is the number of rows in the resulting series and k is the number of columns in the resulting series.

# player_games_stat_avg_hm: O(n*k), where n and k are the rows and columns of the player's data

# calculate_player_games_df: O(max(n*k, m*j)), where n and k are the rows and columns of the player's team stats, and m and j are the rows and columns of the opposing team stats.

# Space complexity:

# player_ids_to_player: O(n), where n is the number of NBA players.

# round_to_one_decimal_place: O(1)

# neg_num_to_zero: O(1)

# get_player_id: O(n*k), where n is the number of players that were in the NBA at any point, and k is the number of characters in the player's full name.

# create_player_games_stat_avg_series: O(n*k), where n is the number of rows in the input dataframe, and k is the number of columns that are operated on in the filtered dataframe.

# get_player_deltas: O(n*k), where n is the number of rows in the resulting series and k is the number of columns in the resulting series.

# player_games_stat_avg_hm: O(n*k), where n and k are the rows and columns of the player's data

# calculate_player_games_df: O(max(n*k, m*j)), where n and k are the rows and columns of the player's team stats, and m and j are the rows and columns of the opposing team stats.

#################################################################################
# Date modified              Modifier             What was modified             #
# 11/02/2025                 Eram Kabir           Initial Development           #
#################################################################################

# Libraries

from nba_api.stats.static import players
from typing import Union, Tuple
from pandera.typing import DataFrame, Series
import pandas as pd
import numpy as np
import numpy.typing as npt
import pandera.pandas as pa
import asyncpg

# Suppress warning about assigning values to subset dataframes
pd.options.mode.chained_assignment = None

# query string for getting player stats
def player_stats_table_query_string() -> str:

    return "SELECT season_id, \
                     player_id, \
                     game_id, \
                     game_date, \
                     matchup, \
                     wl, \
                     minutes, \
                     field_goals_made, \
                     field_goals_attempted, \
                     field_goals_percentage, \
                     field_goal_threes_made, \
                     field_goal_threes_attempted, \
                     field_goal_threes_percentage, \
                     free_throws_made, \
                     free_throws_attempted, \
                     free_throws_percentage, \
                     offensive_rebounds, \
                     defensive_rebounds, \
                     rebounds, \
                     assists, \
                     steals, \
                     blocks, \
                     turnovers, \
                     personal_fouls, \
                     points, \
                     plus_minus, \
                     video_available "

# Validation Schema for return value dataframes and input value
# dataframes

class PlayerSchema(pa.DataFrameModel):
    
    SEASON_ID: str
    Player_ID: int
    Game_ID: str
    GAME_DATE: str
    MATCHUP: str
    WL: str
    MIN: int
    FGM: int
    FGA: int
    FG_PCT: float
    FG3M: int
    FG3A: int
    FG3_PCT: float
    FTM: int
    FTA: int
    FT_PCT: float
    OREB: int
    DREB: int
    REB: int
    AST: int
    STL: int
    BLK: int
    TOV: int
    PF: int
    PTS: int
    PLUS_MINUS: int
    VIDEO_AVAILABLE: int

# Dataframe columns list for making player stats dataframe
def player_stats_df_columns_list() -> list:

    return ["SEASON_ID",
            "Player_ID",
            "Game_ID",
            "GAME_DATE",
            "MATCHUP",
            "WL",
            "MIN",
            "FGM",
            "FGA",
            "FG_PCT",
            "FG3M",
            "FG3A",
            "FG3_PCT",
            "FTM",
            "FTA",
            "FT_PCT",
            "OREB",
            "DREB",
            "REB",
            "AST",
            "STL",
            "BLK",
            "TOV",
            "PF",
            "PTS",
            "PLUS_MINUS",
            "VIDEO_AVAILABLE"]

# This function maps player ids to player names.
def player_ids_to_player() -> dict[int, str]:

    players_dict_arr = players.get_players()

    player_ids_to_player_names_hm = {p["id"]: p["full_name"] for p in players_dict_arr}

    return player_ids_to_player_names_hm

# This function rounds a float number
# to one decimal place by using the
# formula int(num*10+0.5) to determine
# if the number should be rounded up
# or down. If the formula result is
# greater than num*10, then the
# formula result should be rounded up.
# Otherwise, it should be rounded down.
# If the number needs to be rounded up,
# the function rounds up the number by 
# dividing the formula result by 10, 
# and then returns it. If it needs to be
# rounded down, the function rounds down
# the number by using the formula
# int(num*10)/10 on the number, and
# then returns it.

def round_to_one_decimal_place(num: float) -> float:
    
    scaled_num = num*10
    
    rounded_num = int(scaled_num+0.5)
    
    if rounded_num > scaled_num:
        
        res = rounded_num / 10
        
        return res
    
    res = int(scaled_num) / 10
    
    return res

# This function is the same
# as the previous one, except
# it rounds to two decimal
# places instead of one.

def round_to_two_decimal_places(num: Union[float, int]) -> Union[float, int]:

    num_scaling_factor = 100

    scaled_num = num*num_scaling_factor

    rounded_num = int(scaled_num+0.5)

    if rounded_num > scaled_num:

        res = rounded_num / num_scaling_factor

        return res

    res = int(scaled_num) / num_scaling_factor

    return res

# This function... is self explanatory.

def neg_num_to_zero(num: float) -> Union[int, float]:
    
    if num<0:
        
        return 0
    
    return num

# This function gets the player_id
# of an NBA player using their full
# name. It gets a dictionary of the
# player's identification information
# and indexes into it to get the id.

def get_player_id(player_full_name: str) -> int:
    
    player_info_list = players.find_players_by_full_name(player_full_name)
    
    player_id = player_info_list[0]["id"]
    
    return player_id

# This function takes the dataframe
# input and produces the weighted 
# average of all numerical columns.
# It filters the dataframe,
# calculates weights for each column,
# and creates the weighted averages
# through the formula 
# sum(weight*column) / sum(weights).
# It returns these averages as a
# pandas series.

def create_player_stat_avg_series(df: DataFrame[PlayerSchema]) -> Series[float]:
    
    needed_cols_arr = [i for i in range(0, len(df.columns)-1) if (i>5)]
    
    filtered_df = df.iloc[:, needed_cols_arr]
    
    avg_minutes = df["MIN"].sum() / len(df["MIN"])
    
    weights = []

    for i in filtered_df["MIN"]:

        if not i:

            weights.append(1)

        elif i<=avg_minutes:

            weights.append(round_to_one_decimal_place((i/avg_minutes)*1.5))
            
        else:

            weights.append(round_to_one_decimal_place(neg_num_to_zero(2-(i/avg_minutes))*1.5))

    filtered_df[["FG_PCT", "FG3_PCT", "FT_PCT"]] = (filtered_df[["FG_PCT", "FG3_PCT", "FT_PCT"]]).astype(float)
    
    weighted_values_df = filtered_df.mul(weights, axis=0)
    
    weighted_avgs_series = weighted_values_df.sum() / sum(weights)
    
    rounded_weighted_avgs_series = weighted_avgs_series.apply(round_to_one_decimal_place)
        
    return rounded_weighted_avgs_series

# This function calculates the
# player's additional stats
# with regards to a certain
# matchup. It does this by
# getting the player's stats,
# upon which it calculates the
# difference between the stats
# in a particular matchup and the
# overall stats. This difference
# is the player's additional stats
# in a certain matchup, which
# signifies their improved or
# debilitated performance against
# a certain team. The stats are
# then returned as a pandas series.

async def get_player_deltas(opposing_team_abbreviation: str, player_full_name: str, season_type: str, recent_games: int, cur: asyncpg.Connection) -> Series[float]:
    
    player_id = get_player_id(player_full_name)
    
    season_type_dict = {"Pre Season": "preseason", 
                        "Regular Season": "regseason", 
                        "Playoffs": "poffsseason"}

    player_stats_table_name = "nbaplayerstats" + season_type_dict[season_type]

    query = player_stats_table_query_string() + f"FROM {player_stats_table_name} WHERE player_id = $1"

    player_stats_list_of_tuples = await cur.fetch(query, player_id)

    if not player_stats_list_of_tuples:

        return 3
    
    player_stats_list_of_tuples = [tuple((dict(row)).values()) 
                                   for row in player_stats_list_of_tuples]

    player_stats_df_columns = player_stats_df_columns_list()
    
    player_stats_df = pd.DataFrame(player_stats_list_of_tuples, columns = player_stats_df_columns).head(recent_games)
    
    player_stats_df[["FG_PCT", "FG3_PCT", "FT_PCT"]] = (player_stats_df[["FG_PCT", "FG3_PCT", "FT_PCT"]]).astype(float)

    relevant_row_indices = [i for i in range(len(player_stats_df)) 
                            if player_stats_df.iloc[i, 4][-3:] == opposing_team_abbreviation]
    
    if not relevant_row_indices:
        
        series = pd.Series(dtype=float)
        
        return series
    
    player_stats_opposing_teams_df = player_stats_df.iloc[relevant_row_indices]
    
    player_stats_opposing_teams_df = player_stats_opposing_teams_df.iloc[:, 6:-1]
    
    player_stats_df = player_stats_df.iloc[:, 6:-1]
    
    matchup_avg = player_stats_opposing_teams_df.sum() / len(player_stats_opposing_teams_df)
    
    all_seasons_avg = player_stats_df.sum() / len(player_stats_df)
    
    delta = matchup_avg - all_seasons_avg
    
    rounded_delta = delta.apply(round_to_one_decimal_place)
    
    return rounded_delta

# This function calculates a player's
# weighted stat averages (and adds it 
# to their additional stats against a 
# team, if applicable). It does this
# by creating a dataframe from the
# player's stats that were gotten
# from the database, upon which the
# create_player_games_stat_avg_series
# function is called to make the
# weighted stat averages (the
# get_player_deltas function is also
# called if a matchup is specified, 
# and its results are combined with 
# the weighted stat averages). The
# weighted averages are then returned.

async def player_stat_avg_hm(player_full_name: str, 
                             season: str, 
                             season_type: str, 
                             opposing_team_abbreviation: str, 
                             recent_games: int, 
                             cur: asyncpg.Connection) -> Union[int, dict[str, float]]:
    
    player_id = get_player_id(player_full_name)

    year_season_id_dict = {"Pre Season": [2025, 12024], 
                           "Regular Season": [2025, 22024],
                           "Playoffs": [2025, 42024]}
    
    season_type_dict = {"Pre Season": "preseason", 
                        "Regular Season": "regseason",
                        "Playoffs": "poffsseason"}
    
    year_season_id_array = year_season_id_dict[season_type]
    
    try:

        year_diff = year_season_id_array[0] - int(season[0:2] + season[-2:])

        if season[-2:] == "00":

            year_diff = year_season_id_array[0] - (int(season[0:4]) + 1)

        season_id = str(year_season_id_array[1] - year_diff)

    except:

        return 3

    player_stats_table_name = "nbaplayerstats" + season_type_dict[season_type]

    player_stats_table_columns_str = player_stats_table_query_string()

    query = player_stats_table_columns_str + f"FROM {player_stats_table_name} WHERE player_id = $1 AND season_id = $2"

    player_stats_list_of_tuples = await cur.fetch(query, player_id, season_id)

    if not player_stats_list_of_tuples:

        query = player_stats_table_columns_str + f"FROM {player_stats_table_name} WHERE player_id = $1"

        any_player_stats = await cur.fetch(query, player_id)

        if not any_player_stats:

            return 2

        return 3
    
    player_stats_list_of_tuples = [tuple((dict(row)).values()) for row in player_stats_list_of_tuples]

    player_stats_df_columns = player_stats_df_columns_list()
    
    player_stats_df = pd.DataFrame(player_stats_list_of_tuples, columns = player_stats_df_columns).head(recent_games)
    
    player_team_name = player_stats_df["MATCHUP"].iloc[0][0:3]
    
    player_stats_avg_series = create_player_stat_avg_series(player_stats_df)
    
    if len(opposing_team_abbreviation) == 1:
        
        player_stats_avg_hm = player_stats_avg_series.to_dict()
        
        return player_stats_avg_hm
        
    if opposing_team_abbreviation == player_team_name:

        return 4
        
    player_deltas = await get_player_deltas(opposing_team_abbreviation, player_full_name, season_type, recent_games, cur)
        
    if len(player_deltas.index) == 0:
            
        player_stats_avg_hm = player_stats_avg_series.to_dict()
        
        return player_stats_avg_hm
        
    player_stats_avg_with_deltas = player_stats_avg_series + player_deltas
        
    rounded_player_stats_avg_with_deltas = player_stats_avg_with_deltas.apply(round_to_one_decimal_place)
        
    player_stats_avg_with_deltas_hm = rounded_player_stats_avg_with_deltas.to_dict()
        
    return player_stats_avg_with_deltas_hm

# This function gets stats
# for games the team has played from
# a database, and then splits
# it up into the numerical stats,
# the player_ids, and the player
# matchups. It does the same
# for the opposing team, if it
# was specified. It also gets every
# player's id and every player's
# name (in the league). 
# It then returns the team
# abbreviation, the player's split
# stats, the opposing team's split 
# stats, and the ids and names of
# all players in the NBA.

async def calculate_player_stats_arrays(team: str, 
                                        season: str, 
                                        season_type: str, 
                                        opposing_team_abbreviation: str, 
                                        cur: asyncpg.Connection) \
                                        -> Union[Tuple[int, 
                                                       int, 
                                                       int, 
                                                       int, 
                                                       int, 
                                                       int, 
                                                       int, 
                                                       int, 
                                                       int], 
                                                 Tuple[str, 
                                                       npt.NDArray[np.float64], 
                                                       npt.NDArray[np.int64], 
                                                       npt.NDArray[np.uint8], 
                                                       npt.NDArray[np.float64], 
                                                       npt.NDArray[np.int64], 
                                                       npt.NDArray[np.uint8], 
                                                       npt.NDArray[np.int64], 
                                                       npt.NDArray[np.uint8]]]:
    
    wrong_season_error_code = 3

    no_player_stats_error_code = 4

    year_season_id_dict = {"Pre Season": [2025, 12024, "preseason"],
                           "Regular Season": [2025, 22024, "regseason"],
                           "Playoffs": [2025, 42024, "poffsseason"]}

    year_season_id_array = year_season_id_dict[season_type]
    
    try:
    
        year_diff = year_season_id_array[0] - int(season[0:2] + season[-2:])

        if season[-2:] == "00":

            year_diff = year_season_id_array[0] - (int(season[0:4]) + 1)

        season_id = str(year_season_id_array[1] - year_diff)

    except:

        return wrong_season_error_code, wrong_season_error_code, wrong_season_error_code, wrong_season_error_code, wrong_season_error_code, wrong_season_error_code, wrong_season_error_code, wrong_season_error_code

    player_stats_table_name = "nbaplayerstats" + year_season_id_dict[season_type][2]

    team_regex = team + '%'

    player_stats_table_columns_str = player_stats_table_query_string()

    query = player_stats_table_columns_str + f"FROM {player_stats_table_name} WHERE matchup LIKE $1 AND season_id = $2 ORDER BY player_id"

    all_player_stats_info = await cur.fetch(query, team_regex, season_id)

    if not all_player_stats_info:

        query = f"SELECT season_id FROM {player_stats_table_name} WHERE season_id = $1"
        
        season_valid = await cur.fetch(query, season_id)

        if not season_valid:

            return wrong_season_error_code, wrong_season_error_code, wrong_season_error_code, wrong_season_error_code, wrong_season_error_code, wrong_season_error_code, wrong_season_error_code, wrong_season_error_code
        
        return no_player_stats_error_code, no_player_stats_error_code, no_player_stats_error_code, no_player_stats_error_code, no_player_stats_error_code, no_player_stats_error_code, no_player_stats_error_code, no_player_stats_error_code
    
    all_player_stats_info = [list((dict(row)).values()) for row in all_player_stats_info]

    filtered_all_player_stats_info = [[float(num) for num in row[6:-1]] for row in all_player_stats_info]

    players_stats_np_arr = np.array(filtered_all_player_stats_info)
    
    player_ids = np.array([row[1] for row in all_player_stats_info])

    player_matchups_encoded = [(row[4]).encode("utf8") for row in all_player_stats_info]

    max_len_matchup = max(len(s) for s in player_matchups_encoded)

    player_matchups_bytes = np.array(player_matchups_encoded, dtype=f"|S{max_len_matchup*4}")

    player_matchups = player_matchups_bytes.view(np.uint8).reshape(len(player_matchups_encoded), max_len_matchup*4)

    players_info_dict_arr = players.get_players()

    all_player_ids_arr = np.array([p["id"] for p in players_info_dict_arr])

    all_player_names_encoded = [(p["full_name"]).encode("utf-8") for p in players_info_dict_arr]

    max_len_player_name = max(len(s) for s in all_player_names_encoded)

    all_player_names_arr_bytes = np.array(all_player_names_encoded, dtype=f"|S{max_len_player_name*4}")

    all_player_names_arr = all_player_names_arr_bytes.view(np.uint8).reshape(len(all_player_names_encoded), max_len_player_name*4)

    if len(opposing_team_abbreviation) == 1:
        
        empty_np_arr_2D_float = np.empty((0, 0), dtype=np.float64)

        empty_np_arr_2D_int = np.empty((0,), dtype=np.int64)

        empty_np_arr_2D_unsigned_int = np.empty((0, 0), dtype=np.uint8)

        result = (players_stats_np_arr, player_ids, player_matchups, empty_np_arr_2D_float, empty_np_arr_2D_int, empty_np_arr_2D_unsigned_int, all_player_ids_arr, all_player_names_arr)

        return result

    opp_team_regex = opposing_team_abbreviation + '%'

    query = player_stats_table_columns_str + f"FROM {player_stats_table_name} WHERE matchup LIKE $1 AND season_id = $2 ORDER BY player_id"

    all_opp_player_stats_info = await cur.fetch(query, opp_team_regex, season_id)
    
    if not all_opp_player_stats_info:
        
        return no_player_stats_error_code, no_player_stats_error_code, no_player_stats_error_code, no_player_stats_error_code, no_player_stats_error_code, no_player_stats_error_code, no_player_stats_error_code, no_player_stats_error_code
        
    all_opp_player_stats_info = [list((dict(row)).values()) for row in all_opp_player_stats_info]

    filtered_all_opp_player_stats_info = [[float(num) for num in row[6:-1]] for row in all_opp_player_stats_info]

    opp_players_stats_np_arr = np.array(filtered_all_opp_player_stats_info)

    opp_player_ids = np.array([row[1] for row in all_opp_player_stats_info])

    opp_player_matchups_encoded = [(row[4]).encode("utf-8") for row in all_opp_player_stats_info]

    max_len_opp_matchup = max(len(s) for s in opp_player_matchups_encoded)

    opp_player_matchups_bytes = np.array(opp_player_matchups_encoded, dtype=f"|S{max_len_opp_matchup*4}")

    opp_player_matchups = opp_player_matchups_bytes.view(np.uint8).reshape(len(opp_player_matchups_encoded), max_len_opp_matchup*4)

    result = (players_stats_np_arr, player_ids, player_matchups, opp_players_stats_np_arr, opp_player_ids, opp_player_matchups, all_player_ids_arr, all_player_names_arr)

    return result