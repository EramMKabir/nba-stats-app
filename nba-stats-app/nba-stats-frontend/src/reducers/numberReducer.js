/*

numberReducer.js

Function: To manage numbers in Redux.

Inputs:

None

Output:

Numbers stored in Redux.

Time complexity: O(1), since setting a number value is a constant-time operation.

Space complexity: O(1)

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

/* This file stores states of numbers in Redux. */

const numberSlice = createSlice({
    name: "number",
    initialState: {
        seed: 1,
        teamPoints: 0,
        oppTeamPoints: 0
    },
    reducers: {
        setSeed(state, action) {
            return {
                ...state,
                seed: action.payload
            }
        },
        setTeamPoints(state, action) {
            return {
                ...state,
                teamPoints: action.payload
            }
        },
        setOppTeamPoints(state, action) {
            return {
                ...state,
                oppTeamPoints: action.payload
            }
        }
    }
});

export const { setSeed, setTeamPoints, setOppTeamPoints } = numberSlice.actions;
export default numberSlice.reducer;