/*

dictReducer.js

Function: To manage dictionaries in Redux.

Inputs:

None

Output:

Dictionaries stored in Redux.

Time complexity: O(n), where n is the length of the dictionary being set.

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

/* This file stores states of dictionaries in Redux. */

const dictSlice = createSlice({
    name: "dict",
    initialState: {
        playerStatsDictionary: {},
        teamStatsDictionary: {},
        ratioDictionary: {},
        lastGameStatsDictionary: {},
        injuredPlayersDictionary: {}
    },
    reducers: {
        setPlayerStatsDictionary(state, action) {
            return {
                ...state,
                playerStatsDictionary: { ...action.payload }
            }
        },
        setTeamStatsDictionary(state, action) {
            return {
                ...state,
                teamStatsDictionary: { ...action.payload }
            }
        },
        setRatioDictionary(state, action) {
            return {
                ...state,
                ratioDictionary: { ...action.payload }
            }
        },
        setLastGameStatsDictionary(state, action) {
            return {
                ...state,
                lastGameStatsDictionary: { ...action.payload }
            }
        },
        setInjuredPlayersDictionary(state, action) {
            return {
                ...state,
                injuredPlayersDictionary: { ...action.payload }
            }
        }
    }
});

export const { setPlayerStatsDictionary, setTeamStatsDictionary, setRatioDictionary, setLastGameStatsDictionary, setInjuredPlayersDictionary } = dictSlice.actions;
export default dictSlice.reducer;