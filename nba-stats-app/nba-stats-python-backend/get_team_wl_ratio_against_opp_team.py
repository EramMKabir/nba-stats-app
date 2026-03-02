#!/usr/bin/env python
# coding: utf-8

# In[20]:


# get_team_wl_ratio_against_opp_team.py

# Function: Return wl ratio data for a matchup to the frontend.

# Inputs:

# Frontend data that was passed as follows:

# Frontend -> Backend (api.py) -> This file

# Which consists of:

# Player Full Name, Season Type, Opposing Team Abbreviation, and a connection pool (cur)

# Output:

# Dictionary consisting of a key string saying who leads, and an array value with the wins and losses of the matchup.

# Time complexity: O(n), where n is the number of rows returned from the DB query.

# Space complexity: O(n)

#################################################################################
# Date modified              Modifier             What was modified             #
# 11/02/2025                 Eram Kabir           Initial Development           #
#################################################################################

# Libraries

from typing import List
import asyncpg

# The following code gets the wl ratio
# of an NBA matchup.

# It gets the number of matches between the team
# and opposing team, calculates the 
# wl ratio based on the match results,
# and returns the wl ratio along with
# who leads in matches through a
# dictionary.

async def get_team_wl_ratio_against_opp_team(team: str, season_type: str, opposing_team_abbreviation: str, cur: asyncpg.Connection) -> dict[str, List[int]]:
    
    if len(opposing_team_abbreviation) == 1:

        return {'': ''}

    season_type_dict = {"Pre Season": "preseason", 
                        "Regular Season": "regseason", 
                        "All Star": "astarsseason", 
                        "Playoffs": "poffsseason"}

    team_stats_table_name = "nbateamstats" + season_type_dict[season_type]

    regex_team_abbreviation = team + '%'

    query = f"SELECT matchup, wl FROM {team_stats_table_name} WHERE matchup LIKE $1"

    team_matches = await cur.fetch(query, regex_team_abbreviation)

    if not team_matches:
        
        return 4
    
    team_matches = [tuple((dict(row)).values()) for row in team_matches]

    matches_against_opp_team = [match for match in team_matches if match[0][-3:] == opposing_team_abbreviation]
    
    team_binary_win_loss_array = [1 if match[1] == 'W' else 0 for match in matches_against_opp_team]
    
    w = sum(team_binary_win_loss_array)
    
    l = len(team_binary_win_loss_array) - w

    team_has_more_wins, team_has_less_wins = w > l, w < l

    historical_wins_string = "All Time W/L Record: "

    leads_in_wins_string = " leads"

    if team_has_more_wins:

        team_wins_losses = {historical_wins_string + team + leads_in_wins_string: [w, l]}
    
    elif team_has_less_wins:

        team_wins_losses = {historical_wins_string + opposing_team_abbreviation + leads_in_wins_string: [l, w]}

    else:

        team_wins_losses = {historical_wins_string + "No one" + leads_in_wins_string: [w, l]}
    
    return team_wins_losses