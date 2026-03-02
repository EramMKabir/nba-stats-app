/*

arrayReducer.js

Function: To manage arrays of dictionaries in Redux.

Inputs:

None

Output:

Arrays of dictionaries stored in Redux.

Time complexity: O(n), where n is the length of the array being set.

Space complexity: O(n)

#################################################################################
# Date modified              Modifier             What was modified             #
# 03/16/2025                 Eram Kabir           Initial Development           #
# 08/13/2025                 Eram Kabir           Finalized V1.0                #
#################################################################################

*/

/*
Library 
*/

import { createSlice } from "@reduxjs/toolkit";

/* This file stores states of arrays of dictionaries in Redux. */

const arraySlice = createSlice({
    name: "array",
    initialState: {
        playerNamesArray: [],
        teamAbbreviationsArray: [],
        teamsArray: [],
        playersArray: []
    },
    reducers: {
        setPlayerNamesArray(state, action) {
            return {
                ...state,
                playerNamesArray: action.payload
            }
        },
        setTeamAbbreviationsArray(state, action) {
            return {
                ...state,
                teamAbbreviationsArray: action.payload
            }
        },
        setTeamsArray(state, action) {
            return {
                ...state,
                teamsArray: action.payload
            }
        },
        setPlayersArray(state, action) {
            return {
                ...state,
                playersArray: action.payload
            }
        }
    }
});

export const { setPlayerNamesArray, setTeamAbbreviationsArray, setTeamsArray, setPlayersArray } = arraySlice.actions;
export default arraySlice.reducer;