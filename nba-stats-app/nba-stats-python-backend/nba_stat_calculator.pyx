# nba_stat_calculator.pyx

# Function: Return calculated NBA stats to the frontend.

# Inputs:

# Frontend data that was passed as follows:

# Frontend -> Backend (api.py) -> This file

# Which consists of:

# Player Full Name, Season, Season Type, Opposing Team Abbreviation, Recent Games, Team Abbreviation, Player NP Arrays, Player IDs, Player Matchups, Opp Player NP Arrays, Opp Player IDs, Opp Player Matchups, Player ID Keys, Player Name Values

# Output:

# Calculated NBA stats.

# Time complexity: 

# round_to_one_decimal_place: O(1)

# neg_num_to_zero: O(1)

# fast_nanmean_2D: O(n*m), where n is the number of rows with NBA data and m is # the number of columns of the arr variable.

# split_by_indices: O(i*j*k), where i is the depth number of the result array, 
# and j and k are the rows and columns of the result array.

# split_by_indices_bytes: O(i*j*k), where i is the depth number of 
# the result array, and j and k are the rows and columns of the result array.

# fast_2D_multiply: O(n*m), where n and m are the number of rows and columns in
# out.

# get_weight_value: O(1)

# fast_nanmean_1D: O(n), where n is the number of elements in arr.

# extract_column: O(n), where n is the number of rows with NBA data.

# create_player_stats_avg_mv: O(n*m), where n and m are the number of
# rows and columns in weighted_values_np_arr.

# calculate_winning_matchup: O(i*max(j, n)*k + z*max(y, x)*k), where i and z
# are the number of players and opposing players in a matchup, j is the number
# of characters of the longest name out of all players in an NBA team, y is the
# number of characters of the longest name out of all players in the opposing
# NBA team, n is the number of games played by the highest-attendance player in
# an NBA team, x is the number of games played by the highest-attendance player
# in the opposing NBA team, and k is the number of stats calculated by this
# function.

# Space complexity:

# round_to_one_decimal_place: O(1)

# neg_num_to_zero: O(1)

# fast_nanmean_2D: O(n*m), where n is the number of rows and m is
# the number of columns of the arr variable.

# split_by_indices: O(i*j*k), where i is the depth number of the result array, 
# and j and k are the rows and columns of the result array.

# split_by_indices_bytes: O(i*j*k), where i is the depth number of the result 
# array, and j and k are the rows and columns of the result array.

# fast_2D_multiply: O(n*m), where n and m are the number of rows and columns in 
# out.

# get_weight_value: O(1)

# fast_nanmean_1D: O(1)

# extract_column: O(n), where n is the number of rows with NBA data.

# create_player_stats_avg_mv: O(n*m), where n and m are the number of
# rows and columns in weighted_values_np_arr.

# calculate_winning_matchup: O(max(i*j*k, x*y*z)), where i is the depth number 
# of the player_matchups_l array, j and k are the rows and columns of the
# player_matchups_l array, x is the depth number of the opp_player_matchups_mv
# array, and y and z are the rows and columns of the opp_player_matchups_mv
# array.

#################################################################################
# Date modified              Modifier             What was modified             #
# 11/03/2025                 Eram Kabir           Initial Development           #
#################################################################################

# Libraries

cimport numpy as cnp
import numpy as np
cimport cython
from cython.parallel cimport prange
from libc.math cimport isnan, NAN

# Boundscheck and wraparound need
# to be set to False before every
# function to maximize performance.

@cython.boundscheck(False)
@cython.wraparound(False)

# This function rounds a 
# float number to one decimal
# place, using 
# double(int(num*10+0.5) / 10)
# to round up, and
# double(int(num*10)) / 10
# to round down.

cdef double round_to_one_decimal_place(double num) nogil:
    
    cdef double scaled_num = num * 10
    
    cdef int rounded_num = <int>(scaled_num + 0.5)

    cdef double res
    
    if rounded_num > scaled_num:
        
        res = <double>rounded_num / 10
        
        return res
    
    res = <double>(<int>scaled_num) / 10
    
    return res

@cython.boundscheck(False)
@cython.wraparound(False)

# This function... is self-explanatory.

cdef double neg_num_to_zero(double num) nogil:
    
    if num<0:
        
        return 0.0
    
    return num

@cython.boundscheck(False)
@cython.wraparound(False)

# This function calculates 
# the mean of each column 
# in a 2D typed memory view
# and stores them in a 1D
# typed memory view, all
# while ignoring NaN values.

cpdef void fast_nanmean_2D(cnp.double_t[:, ::1] arr_to_process, 
                           cnp.double_t[::1] output_arr, 
                           int start, 
                           Py_ssize_t end) noexcept nogil:
    
    cdef Py_ssize_t i, j, count, cols = arr_to_process.shape[1]
    
    cdef double sum

    for j in range(cols):
    
        sum = 0.0
    
        count = 0
    
        for i in range(start, end):
    
            if not isnan(arr_to_process[i, j]):
    
                sum += arr_to_process[i, j]
    
                count += 1
    
        output_arr[j] = sum / count if count > 0 else NAN

@cython.boundscheck(False)
@cython.wraparound(False)

# This function splits a 
# 2D numpy array that
# contains player stats into 
# pieces based on player,
# and then stores them in
# a 3d numpy array. It
# calculates the max number
# of games throughout all
# players (max_len), makes
# a 3D numpy array, and
# then populates each part
# of the 3D numpy array
# with a player's NBA data.
# Max_len must be calculated,
# as the dimensions of the
# numpy array must be uniform,
# and each player has played
# a different number of games.
# num_splits is guaranteed
# to be the total number of
# team players.

cpdef cnp.ndarray[cnp.double_t, ndim=3] split_by_indices(cnp.ndarray[cnp.double_t, ndim=2] arr_to_split, 
                                                         cnp.int64_t[::1] indices):
    
    cdef Py_ssize_t n_rows = arr_to_split.shape[0]
    
    cdef Py_ssize_t n_cols = arr_to_split.shape[1]
    
    cdef Py_ssize_t num_splits = indices.shape[0] + 1

    cdef Py_ssize_t indices_len = indices.shape[0]
    
    cdef Py_ssize_t i, start = 0, end, split_len, max_len = 0

    for i in range(indices_len):

        end = indices[i]

        split_len = end - start

        if split_len > max_len:

            max_len = split_len

        start = end

    if n_rows - start > max_len:

        max_len = n_rows - start

    cdef cnp.ndarray[cnp.double_t, ndim=3] result = np.full(
        
        (num_splits, max_len, n_cols),
        
        -1.0,
        
        dtype=np.float64
    )

    start = 0
    
    for i in range(num_splits):
        
        if i < indices_len:
        
            end = indices[i]

        else:

            end = n_rows

        split_len = end - start
        
        result[i, :split_len, :] = arr_to_split[start:end, :]
        
        start = end

    return result

@cython.boundscheck(False)
@cython.wraparound(False)

# This function has the
# same purpose as the
# split_by_indices function,
# except this function
# works on bytes instead
# of doubles. This needed
# to be implemented since
# the split_by_indices
# function cannot be
# used with a 2D 
# bytes memory view.

cpdef unsigned char[:, :, ::1] split_by_indices_bytes(unsigned char[:, ::1] arr_to_split, 
                                                      cnp.int64_t[::1] indices):
    
    cdef Py_ssize_t n_rows = arr_to_split.shape[0]
    
    cdef Py_ssize_t n_cols = arr_to_split.shape[1]
    
    cdef Py_ssize_t num_splits = indices.shape[0] + 1

    cdef Py_ssize_t indices_len = indices.shape[0]
    
    cdef Py_ssize_t i, start = 0, end, split_len, max_len = 0

    for i in range(indices_len):

        end = indices[i]
    
        split_len = end - start
    
        if split_len > max_len:
    
            max_len = split_len
    
        start = end

    if n_rows - start > max_len:
        
        max_len = n_rows - start

    cdef unsigned char[:, :, ::1] result = np.full(

        (num_splits, max_len, n_cols),

        0,

        dtype=np.uint8

    )

    start = 0

    for i in range(num_splits):
        
        if i < indices_len:
        
            end = indices[i]
        
        else:
        
            end = n_rows

        split_len = end - start
        
        result[i, :split_len, :] = arr_to_split[start:end, :]
        
        start = end

    return result

@cython.boundscheck(False)
@cython.wraparound(False)

# This function multiplies
# a 2D typed memory view
# by a 1D typed memory view
# and stores the result into
# a different 2D typed memory
# view.

cdef cnp.double_t[:, ::1] fast_2D_multiply(cnp.double_t[:, ::1] arr_to_process, 
                                           cnp.double_t[::1] multiplier, 
                                           cnp.double_t[:, ::1] output_arr, 
                                           int start, 
                                           int end) noexcept nogil:
    
    cdef Py_ssize_t rows = arr_to_process.shape[0]
    
    cdef Py_ssize_t cols = arr_to_process.shape[1]
    
    cdef Py_ssize_t i, j
    
    for i in range(start, end):
    
        for j in range(cols):
    
            output_arr[i, j] = arr_to_process[i, j] * multiplier[i]

    return output_arr

@cython.boundscheck(False)
@cython.wraparound(False)

# This function calculates
# how much weight should
# be given to a player's
# performance in a game.
# It does this by comparing
# the number of minutes 
# played in a game (num)
# with the average minutes
# a player has played in
# games. If the player has
# not played in the game,
# the weight is 1, as
# that performance does
# not deserve any
# weighting. If num is
# less than or equal to
# the average minutes,
# the player is given
# a weight <= 1,
# whose true value depends
# on the proportion of
# num to average minutes.
# If num is greater
# than average minutes,
# then the player is
# given a weight <= 1,
# whose true value depends
# on 2 - num/avg_minutes.

cdef double get_weight_value(double minutes, double avg_minutes) nogil:

    cdef double res

    if not minutes:

        res = 1

        return res
    
    elif minutes <= avg_minutes:
    
        res = round_to_one_decimal_place((minutes/avg_minutes)*1.5)

        return res
        
    else:
    
        res = round_to_one_decimal_place(neg_num_to_zero(2-(minutes/avg_minutes))*1.5)
        
        return res

@cython.boundscheck(False)
@cython.wraparound(False)

# This function calculates
# and returns the average 
# of a 1D typed memory view, 
# while ignoring NaN values.

cdef double fast_nanmean_1D(cnp.double_t[::1] arr_to_process, int start, int end) nogil:
    
    cdef Py_ssize_t i
    
    cdef double sum = 0.0
    
    cdef Py_ssize_t count = 0
    
    for i in range(start, end):
    
        if not isnan(arr_to_process[i]):
    
            sum += arr_to_process[i]
    
            count += 1
    
    if count == 0:
    
        return NAN
    
    return sum / count

@cython.boundscheck(False)
@cython.wraparound(False)

# This function extracts
# a column from a 2D
# typed memory view into
# a 1D typed memory view.

cdef void extract_column(cnp.double_t[:, ::1] arr_to_get_column_from, 
                         int col_idx, 
                         cnp.double_t[::1] col_arr, 
                         int start, 
                         int end) noexcept nogil:
    
    cdef Py_ssize_t i

    for i in range(start, end):
    
        col_arr[i] = arr_to_get_column_from[i, col_idx]

@cython.boundscheck(False)
@cython.wraparound(False)

# This function calculates
# the weighted average
# of all of a player's stats.
# It calculates the weights
# of a player's stats based
# on minutes and avg_minutes,
# applies those weights to
# all of the player's stats,
# sums ups the stats in each
# column, and then divides
# the column sums by the
# sums of the weights.

cdef void create_player_stats_avg_mv(cnp.double_t[:, ::1] player_stats_arr, 
                                     cnp.double_t[::1] player_stats_avg_mv, 
                                     cnp.double_t[::1] col_arr, 
                                     cnp.double_t[::1] weights, 
                                     cnp.double_t[:, ::1] output_arr, 
                                     cnp.double_t[::1] weighted_sum, 
                                     int start, 
                                     int end) noexcept nogil:

    extract_column(player_stats_arr, 0, col_arr, start, end)
    
    cdef double avg_minutes = round_to_one_decimal_place(fast_nanmean_1D(col_arr, start, end))
    
    cdef Py_ssize_t i

    for i in range(start, end):
    
        weights[i] = get_weight_value(col_arr[i], avg_minutes)
    
    cdef cnp.double_t[:, ::1] mv_arr = player_stats_arr
    
    cdef cnp.double_t[:, ::1] weighted_values_np_arr = fast_2D_multiply(mv_arr, weights, output_arr, start, end)
    
    cdef Py_ssize_t cols = weighted_values_np_arr.shape[1]
    
    cdef Py_ssize_t j
    
    for i in range(start, end):
    
        for j in range(cols):
        
            weighted_values_np_arr[i, j] = round_to_one_decimal_place(weighted_values_np_arr[i, j])
    
    for j in range(cols):
        
        for i in range(start, end):
            
            if not isnan(weighted_values_np_arr[i, j]):
                
                weighted_sum[j] += weighted_values_np_arr[i, j]

    n = weighted_sum.shape[0]
    
    for i in range(n):
        
        weighted_sum[i] = round_to_one_decimal_place(weighted_sum[i])
    
    rows = weights.shape[0]
    
    cdef cnp.double_t weights_view_sum = 0
    
    for i in range(rows):
            
        if not isnan(weights[i]):
                
            weights_view_sum += weights[i]
    
    for i in range(n):
    
        player_stats_avg_mv[i] = round_to_one_decimal_place(weighted_sum[i] / weights_view_sum)

@cython.boundscheck(False)
@cython.wraparound(False)

# This function calculates the stats, team_abbreviations
# stat names and player names of a team.

cpdef calculate_team_stats(str team, 
                           str season, 
                           str season_type, 
                           str opposing_team_abbreviation, 
                           Py_ssize_t recent_games, 
                           cnp.ndarray[cnp.double_t, ndim=2, mode='c'] player_np_arrays, 
                           cnp.ndarray[cnp.int64_t, ndim=1] player_ids, 
                           cnp.ndarray[cnp.uint8_t, ndim=2] player_matchups, 
                           cnp.ndarray[cnp.int64_t, ndim=1] player_id_keys, 
                           cnp.ndarray[cnp.uint8_t, ndim=2] player_name_values):

    cdef Py_ssize_t n = 20 # holder for end variable of range statements
    
    # meant to hold twenty 0.0 values, to be used for a player
    # if they have no stats

    cdef cnp.double_t[::1] zeroes_mv = np.empty(n, dtype=np.float64)
    
    cdef Py_ssize_t i # index variable for for loops
    
    # Populate zeroes_list with twenty 0.0 values

    for i in range(n):
    
        zeroes_mv[i] = 0.0

    # number of stats to be calculated
    
    cdef Py_ssize_t num_stats = 20

    # memory view to speed up player_id processing

    cdef cnp.int64_t[::1] player_ids_mv = player_ids
    
    # set n to player_ids shape for loop execution

    n = player_ids_mv.shape[0]
    
    # create a variable for holding indices
    # of player divisions, so that player_
    # np_arrays can be split into a 3D
    # typed memory view with each player
    # in their own section

    cdef list split_indices_p = []
    
    for i in range(n - 1):
    
        if player_ids_mv[i] != player_ids_mv[i + 1]:
    
            split_indices_p.append(i + 1)

    # convert the indices holder
    # to a typed memory view for
    # faster computing

    cdef cnp.int64_t[::1] split_indices_p_mv = np.ascontiguousarray(split_indices_p, dtype=np.int64)
    
    # compress player_ids into an
    # array with one player_id for
    # each player (player_ids had
    # multiple copies, which are
    # no longer needed)

    n = split_indices_p_mv.shape[0]
    
    cdef cnp.int64_t[::1] player_ids_final = np.empty(n+1, dtype=np.int64)

    player_ids_final[0] = player_ids_mv[0]

    for i in range(n):

        player_ids_final[i+1] = player_ids_mv[split_indices_p_mv[i]]

    # split player_matchups and player_np_arrays based on player,
    # using split_indices

    cdef unsigned char[:, :, ::1] player_matchups_mv = split_by_indices_bytes(player_matchups, split_indices_p_mv)
    
    cdef cnp.double_t[:, :, ::1] player_np_arrays_mv = split_by_indices(player_np_arrays, split_indices_p_mv)

    cdef Py_ssize_t j # index variable for second for loop
    
    # set variable for number of players (needed to pre-allocate
    # certain arrays, arrays cannot be allocated in a parallel
    # for loop that will happen later)

    cdef Py_ssize_t num_players = player_np_arrays_mv.shape[0]
    
    # pre-allocation value for team_abbreviation_mv typed memory view

    n = num_players * num_stats

    # create a 1D bytes typed memory view to increase performance
    # for team abbreviation operations

    cdef Py_ssize_t team_abbreviation_len = 3
    
    cdef unsigned char[:, ::1] team_abbreviation_mv = np.empty((n, team_abbreviation_len), dtype=np.uint8)

    # turn team abbreviation into bytes, and then bytearray

    cdef bytes team_abb_bytes = team.encode("utf8")

    cdef unsigned char[::1] team_abbreviation_bytearray = bytearray(team_abb_bytes)
    
    # populate team_abbreviation_mv (an output value) 
    # with team_abbreviation_bytearray

    for i in range(n):
    
        team_abbreviation_mv[i, :] = team_abbreviation_bytearray
    
    # set n to the first dimension of player_np_arrays
    # for pre-allocation

    n = player_np_arrays_mv.shape[0]

    # Make a typed memory view for the output player_stats_mv

    cdef cnp.double_t[:, ::1] player_stats_mv = np.empty((n, num_stats), dtype=np.float64)
    
    cdef Py_ssize_t index # index variable for upcoming parallel loops

    # the following variables will be used to select the proper
    # data rows from certain arrays, since pre-allocation will
    # leave certain rows of the arrays empty due to players
    # having different numbers of games played

    cdef Py_ssize_t start = recent_games 
    
    cdef int recent

    # this variable will hold the result of the
    # create_player_stats_avg_mv function

    cdef cnp.double_t[:, ::1] player_stats_avg_mv = np.empty((n, num_stats), dtype=np.float64)

    # variable for determining max number of games 
    # out of all players (iteration through 
    # player_np_arrays_mv determines this)

    cdef int max_num_of_games = -1

    for i in range(n):

        if (player_np_arrays_mv[i]).shape[0] > max_num_of_games:

            max_num_of_games = (player_np_arrays_mv[i]).shape[0]

    # variable for holding result of extract_column function

    cdef cnp.double_t[::1] col_arr = np.empty(max_num_of_games, dtype=np.float64)

    # variable for holding result of get_weight_value function

    cdef cnp.double_t[::1] weights = np.empty(max_num_of_games, dtype=np.float64)

    # variable for holding result of fast_2D_multiply function

    cdef cnp.double_t[:, ::1] out = np.empty((max_num_of_games, num_stats), dtype=np.float64)

    # variable for getting rows of player_np_arrays_mv where 
    # the player faced off against the opposing team

    cdef cnp.int64_t[:, ::1] relevant_row_indices = np.empty((n, max_num_of_games), dtype=np.int64)
    
    # variable used to iterate through player_np_arrays_mv
    # to find matchup strings in the rows

    cdef Py_ssize_t player_np_arrays_index_length
    
    # variable used to iterate through matchup strings
    # to find team abbreviation vs. opposing team

    cdef Py_ssize_t matchup_str_len
    
    # used to get the number of rows for a player
    # (needed to get starting index of pre-allocated
    # arrays, since some rows may be empty due to
    # players having different games played)

    cdef int n_rows

    # holds the rows of player_np_arrays_mv where 
    # the player faced off against the opposing team

    cdef cnp.double_t[:, :, ::1] player_stats_opposing_teams_mv = np.empty((n, max_num_of_games, num_stats), dtype=np.float64)

    # variable to hold averages of rows of player_np_arrays_mv where 
    # the player faced off against the opposing team

    cdef cnp.double_t[::1] matchup_avgs = np.empty(num_stats, dtype=np.float64)
    
    # variable to hold averages of player_np_arrays_mv for a player

    cdef cnp.double_t[::1] all_seasons_avgs = np.empty(num_stats, dtype=np.float64)

    # used to iterate through all_seasons_avgs and matchup_avgs
    # to calculate player's additional stats against the 
    # opposing team

    cdef Py_ssize_t n_elements
    
    # used to hold player's additional stats against the 
    # opposing team

    cdef cnp.double_t[:, ::1] player_deltas = np.empty((n, num_stats), dtype=np.float64)

    # used to hold weighted stat averages that include player's
    # additional stats against the opposing team

    cdef cnp.double_t[:, ::1] rounded_player_stats_avg_with_deltas = np.empty((n, num_stats), dtype=np.float64)

    # 2D typed memory view used for access to player_names
    # (needed for filling up player_names_mv)

    cdef unsigned char[:, ::1] player_names_bytes = player_name_values

    # used to iterate through player_ids

    cdef Py_ssize_t n_ids = player_id_keys.shape[0]

    # used to store parallel loop's current player's
    # id

    cdef Py_ssize_t current_id

    # used to store index of current player's name

    cdef Py_ssize_t name_index

    # used to iterate through player_names_bytes

    cdef Py_ssize_t name_len = player_names_bytes.shape[1]
    
    # used to hold player_names, will be an output value

    cdef unsigned char[:, :, ::1] player_names_mv = np.empty((n, num_stats, name_len), dtype=np.uint8)

    # used to get ending index of players_np_arrays_l for a player

    cdef int valid_rows

    # the following lines of code are used to make the output array
    # for opposing_team_abbreviations

    cdef bytes opp_team_abb = opposing_team_abbreviation.encode("utf8")

    cdef unsigned char[::1] opposing_team_abbreviation_bytearray = bytearray(opp_team_abb)

    # used to get the stopping point for matchup strings 
    # (needed due to pre-allocation leaving some spots
    # empty)

    cdef Py_ssize_t str_stop = -1

    # weighted_sum holds summed weighted stats

    cdef cnp.double_t[:, ::1] weighted_sum = np.empty((n, num_stats), dtype=np.float64)

    # counter array used to contain indices of rows where
    # player faced off against opposing team

    cdef cnp.int64_t[::1] counters = np.zeros(n, dtype=np.int64)

    # used to contain matchup_avgs elements minus all_seasons_avgs elements

    cdef cnp.double_t temp_delta_holder

    for index in prange(n, nogil=True): # for each player (parallel loop)

        # get the player's name, represented
        # in bytes, and copy it to the
        # output player_names_mv (copy 0
        # if name not found)

        current_id = player_ids_final[index]

        name_index = -1

        for i in range(n_ids):

            if player_id_keys[i] == current_id:

                name_index = i

                break
    
        if name_index >= 0:
            
            for j in range(num_stats):
            
                for i in range(name_len):

                    player_names_mv[index, j, i] = player_names_bytes[name_index, i]
        
        else:

            for j in range(num_stats):

                for i in range(name_len):

                    player_names_mv[index, j, i] = 0

        # find the starting and ending
        # indices of the player's np
        # array in player_np_arrays_mv

        n_rows = (player_np_arrays_mv[index]).shape[0]

        valid_rows = n_rows

        for i in range(n_rows):

            if player_np_arrays_mv[index][i, 0] == -1.0:

                valid_rows = i

                break

        if start >= valid_rows:

            recent = 0
        
        else:
            
            recent = valid_rows - start

        # since this is a parallel loop,
        # race conditions will occur,
        # unless we empty all arrays
        # that will be reused

        # as such, the following code
        # will set the values of the
        # reused arrays to 0 to avoid
        # race conditions
    
        for i in range(num_stats):

            player_stats_avg_mv[index, i] = 0.0

            matchup_avgs[i] = 0.0

            all_seasons_avgs[i] = 0.0

            player_deltas[index, i] = 0.0

            rounded_player_stats_avg_with_deltas[index, i] = 0.0

            weighted_sum[index, i] = 0.0

        for i in range(counters[index]):

            relevant_row_indices[index, i] = 0
        
            for j in range(player_stats_opposing_teams_mv.shape[2]):
            
                player_stats_opposing_teams_mv[index, i, j] = 0.0

        counters[index] = 0

        for i in range(col_arr.shape[0]):

            col_arr[i] = 0.0

            weights[i] = 0.0

            for j in range(out.shape[1]):

                out[i, j] = 0.0

        # get the weighted stat averages of a player
        # using create_player_stats_avg_mv

        create_player_stats_avg_mv(player_np_arrays_mv[index], 
                                   player_stats_avg_mv[index], 
                                   col_arr, 
                                   weights, 
                                   out, 
                                   weighted_sum[index], 
                                   recent, 
                                   valid_rows)

        # if there is no opposing_team_abbreviation,
        # then record the stats in the output array
        # and move on to the next parallel loop iteration

        if opposing_team_abbreviation_bytearray.shape[0] == 1:
            
            for j in range(player_stats_mv.shape[1]):
                
                player_stats_mv[index, j] = player_stats_avg_mv[index, j]

            continue

        # the following code gets the rows
        # from player_np_arrays_mv[index],
        # where the player faced off against
        # the opposing team, and stores them
        # player_stats_opposing_teams_mv

        # it does this by iterating through
        # the matchups memory view, finding
        # all matchups where the player
        # faced off against the opposing team,
        # and storing the indices of the 
        # matchups in a memory view, while
        # keeping track of how many rows
        # had the opposing team through
        # the counters memory view.

        # if counters[index] == 0, then
        # there were no instances of the
        # player facing off against the
        # opposing team, so the weighted
        # stat averages are stored in
        # the output array and the next
        # parallel loop iteration starts

        # otherwise, the rows of 
        # player_np_arrays_mv corresponding
        # to the stored matchup rows are
        # recorded in 
        # player_stats_opposing_teams_mv

        player_np_arrays_index_length = player_np_arrays_mv[index].shape[0]
        
        for j in range(player_np_arrays_index_length):
            
            matchup_str_len = (player_matchups_mv[index][j]).shape[0]

            for i in range(matchup_str_len):

                str_stop = i

                if player_matchups_mv[index][j][str_stop] == 0:

                    break
            
            if player_matchups_mv[index][j][str_stop - 3] == opposing_team_abbreviation_bytearray[0] and \
            player_matchups_mv[index][j][str_stop - 2] == opposing_team_abbreviation_bytearray[1] and \
            player_matchups_mv[index][j][str_stop - 1] == opposing_team_abbreviation_bytearray[2]:

                relevant_row_indices[index, counters[index]] = j

                counters[index]+=1

        if counters[index] == 0:

            for j in range(player_stats_mv.shape[1]):
                
                player_stats_mv[index, j] = player_stats_avg_mv[index, j]

            continue

        for i in range(counters[index]):
        
            for j in range(player_stats_opposing_teams_mv.shape[2]):
            
                player_stats_opposing_teams_mv[index, i, j] = player_np_arrays_mv[index][relevant_row_indices[index, i], j]

        # calculate the averages of
        # the player overall and the
        # player when facing off against
        # the opposing team, subtract the
        # former from the latter, and
        # place the result in player_deltas

        # player_deltas is meant to hold
        # the additional stats a player
        # has when facing off against
        # the opposing team (hence the
        # name "player_deltas")

        fast_nanmean_2D(player_stats_opposing_teams_mv[index], matchup_avgs, 0, counters[index])

        fast_nanmean_2D(player_np_arrays_mv[index], all_seasons_avgs, recent, valid_rows)

        n_elements = player_deltas.shape[1]

        for i in range(n_elements):

            temp_delta_holder = matchup_avgs[i] - all_seasons_avgs[i]
        
            player_deltas[index, i] = round_to_one_decimal_place(temp_delta_holder)

        # finally, take the additional stats,
        # add them to the weighted stat
        # averages, and store the result
        # in the player_stats output array

        for i in range(n_elements):
        
            rounded_player_stats_avg_with_deltas[index, i] = round_to_one_decimal_place(player_stats_avg_mv[index, i] + player_deltas[index, i])
        
        for j in range(player_stats_mv.shape[1]):
        
            player_stats_mv[index, j] = rounded_player_stats_avg_with_deltas[index, j]

    return team_abbreviation_mv, player_names_mv, player_stats_mv

@cython.boundscheck(False)
@cython.wraparound(False)

# This function calculates the
# stats, stat names, player names
# and team abbreviations of the
# home team and opposing team in
# a matchup.

cpdef calculate_matchup_stats(str team, 
                              str season, 
                              str season_type, 
                              str opposing_team_abbreviation, 
                              Py_ssize_t recent_games, 
                              cnp.ndarray[cnp.double_t, ndim=2, mode='c'] player_np_arrays, 
                              cnp.ndarray[cnp.int64_t, ndim=1] player_ids, 
                              cnp.ndarray[cnp.uint8_t, ndim=2] player_matchups, 
                              cnp.ndarray[cnp.double_t, ndim=2, mode='c'] opp_player_np_arrays, 
                              cnp.ndarray[cnp.int64_t, ndim=1] opp_player_ids, 
                              cnp.ndarray[cnp.uint8_t, ndim=2] opp_player_matchups, 
                              cnp.ndarray[cnp.int64_t, ndim=1] player_id_keys, 
                              cnp.ndarray[cnp.uint8_t, ndim=2] player_name_values):

    cdef Py_ssize_t n = 20 # number of stats
    
    # meant to hold twenty 0.0 values, to be used for a player
    # if they have no stats

    cdef cnp.double_t[::1] zeroes_mv = np.empty(n, dtype=np.float64)
    
    # Populate zeroes_mv with twenty 0.0 values

    for i in range(n):
    
        zeroes_mv[i] = 0.0
    
    # dimensions for error code array, used to
    # propagate errors from this function to backend
    # to frontend

    cdef Py_ssize_t error_code_len = 1

    # error variable, used to specify
    # if an error occurred in this
    # function

    cdef bint error = False

    # the following are the error code
    # arrays, made to provide error
    # codes, and to maintain consistent
    # return values in this function

    cdef unsigned char[:, :, ::1] error_mv_int_3d = np.empty((error_code_len, error_code_len, error_code_len), dtype=np.uint8)

    cdef unsigned char[:, ::1] error_mv_int = np.empty((error_code_len, error_code_len), dtype=np.uint8)

    cdef cnp.double_t[:, ::1] error_mv_float = np.empty((error_code_len, error_code_len), dtype=np.float64)

    # initialize the error code
    # arrays with 0, to signify
    # no errors have happened.

    error_mv_int_3d[0][0][0] = 0
    
    error_mv_int[0][0] = 0

    error_mv_float[0][0] = 0.0

    # if no team abbreviation was specified
    # or there are no player stats, then
    # throw error code 2 and set error
    # equal to true, since there is no 
    # data to process

    if not team or player_np_arrays.shape[0] == 0:

        error_mv_int_3d[0][0][0] = 2

        error_mv_int[0][0] = 2

        error_mv_float[0][0] = 2.0

        error_list_int_3d = (np.asarray(error_mv_int_3d)).tolist()

        error_list_int = (np.asarray(error_mv_int)).tolist()

        error_list_float = (np.asarray(error_mv_float)).tolist()

        error = True

        return error_list_int, error_list_int_3d, error_list_float, error_list_int, error_list_int_3d, error_list_float, error

    # if the opposing_team_abbreviation is
    # the same as the player's team_abbreviation,
    # then set an error code for a matchup
    # that cannot happen, set error
    # to true, error code to 4 and exit the function

    if opposing_team_abbreviation == team:

        error_mv_int_3d[0][0][0] = 4

        error_mv_int[0][0] = 4

        error_mv_float[0][0] = 4.0

        error = True

        error_list_int_3d = (np.asarray(error_mv_int_3d)).tolist()

        error_list_int = (np.asarray(error_mv_int)).tolist()

        error_list_float = (np.asarray(error_mv_float)).tolist()

        return error_list_int, error_list_int_3d, error_list_float, error_list_int, error_list_int_3d, error_list_float, error

    # the following lines of code are used to 
    # determine if an opposing team is not present

    # if so, then the function will return the team
    # data for the player's team, and return blank
    # data for the opposing team

    cdef bytes opp_team_abb = opposing_team_abbreviation.encode("utf8")

    cdef unsigned char[::1] opposing_team_abbreviation_bytearray = bytearray(opp_team_abb)

    # get stats for the main team

    team_stats = calculate_team_stats(team, 
                                      season, 
                                      season_type, 
                                      opposing_team_abbreviation, 
                                      recent_games, 
                                      player_np_arrays, 
                                      player_ids, 
                                      player_matchups, 
                                      player_id_keys, 
                                      player_name_values)

    # the following code sets up memory views
    # for blank teams and players

    # if there are no np arrays for the opposing
    # team, or if there is no opposing team
    # abbreviation, then return the data for
    # the player's team, and return the blank
    # teams and players memory views along with
    # the stat names array and the zeroes_list

    # this is done because no opposing team
    # abbreviation/opposing team data means
    # there is nothing left to process, so
    # the team data and the blank arrays
    # can be sent to the backend immediately

    # blank arrays are sent back to represent
    # no data for the opposing team

    cdef unsigned char[:, ::1] team_abbreviation_mv = team_stats[0]

    cdef unsigned char[:, :, ::1] player_names_mv = team_stats[1]

    cdef cnp.double_t[:, ::1] player_stats_mv = team_stats[2]

    cdef Py_ssize_t column_len_no_teams_mv = 13

    cdef Py_ssize_t column_len_no_players_mv = 16

    cdef Py_ssize_t placeholder_dimension = 1

    cdef str no_team_found_str = "No Team Found"

    cdef str no_players_found_str = "No Players Found"

    cdef bytes no_team_found_bytes = no_team_found_str.encode("utf-8")

    cdef bytes no_players_found_bytes = no_players_found_str.encode("utf-8")

    cdef unsigned char[:, ::1] no_teams_mv = np.empty((n, column_len_no_teams_mv), dtype=np.uint8)

    cdef unsigned char[::1] no_team_found_mv = bytearray(no_team_found_bytes)

    cdef unsigned char[:, :, ::1] no_players_mv = np.empty((placeholder_dimension, n, column_len_no_players_mv), dtype=np.uint8)

    cdef unsigned char[::1] no_players_found_mv = bytearray(no_players_found_bytes)

    cdef cnp.double_t[:, ::1] zeroes_2D_mv = np.empty((placeholder_dimension, n), dtype=np.float64)

    if opp_player_np_arrays.shape[0] == 0 or opposing_team_abbreviation_bytearray.shape[0] == 1:
        
        for i in range(n):
        
            no_teams_mv[i, :] = no_team_found_mv
        
            no_players_mv[0, i, :] = no_players_found_mv

            zeroes_2D_mv[0, i] = zeroes_mv[i]

        team_abbreviation_list = (np.asarray(team_abbreviation_mv)).tolist()

        player_names_list = (np.asarray(player_names_mv)).tolist()

        player_stats_list = (np.asarray(player_stats_mv)).tolist()

        no_teams_list = (np.asarray(no_teams_mv)).tolist()

        no_players_list = (np.asarray(no_players_mv)).tolist()

        zeroes_py_list = (np.asarray(zeroes_2D_mv)).tolist()

        return team_abbreviation_list, player_names_list, player_stats_list, no_teams_list, no_players_list, zeroes_py_list, error

    # get stats for the opposing team

    opposing_team_stats = calculate_team_stats(opposing_team_abbreviation, 
                                               season, 
                                               season_type, 
                                               team, 
                                               recent_games, 
                                               opp_player_np_arrays, 
                                               opp_player_ids, 
                                               opp_player_matchups, 
                                               player_id_keys, 
                                               player_name_values)

    # to finish up the function, the eight
    # output values from the 
    # calculate_team_stats calcs are 
    # converted to python lists and returned 
    # (along with the error boolean) to
    # the backend

    cdef unsigned char[:, ::1] opp_team_abbreviation_mv = opposing_team_stats[0]

    cdef unsigned char[:, :, ::1] opp_player_names_mv = opposing_team_stats[1]

    cdef cnp.double_t[:, ::1] opp_player_stats_mv = opposing_team_stats[2]

    team_abbreviation_list = (np.asarray(team_abbreviation_mv)).tolist()

    player_names_list = (np.asarray(player_names_mv)).tolist()

    player_stats_list = (np.asarray(player_stats_mv)).tolist()

    opp_team_abbreviation_list = (np.asarray(opp_team_abbreviation_mv)).tolist()

    opp_player_names_list = (np.asarray(opp_player_names_mv)).tolist()

    opp_player_stats_list = (np.asarray(opp_player_stats_mv)).tolist()

    return team_abbreviation_list, player_names_list, player_stats_list, opp_team_abbreviation_list, opp_player_names_list, opp_player_stats_list, error
