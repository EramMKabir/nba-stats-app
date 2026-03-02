/*

calculatedmatchupstats.js

Function: To call the second matchup stats microservice in the backend.

Inputs:

credentials: An object containing user inputs for the second matchup stats microservice.

token: The access token received from the OAuth exchange microservice.

Output:

JSON response from the backend containing player and team data.

Time complexity: O(1), since the function makes a single HTTP request.

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

import axios from "axios";

const baseUrl = import.meta.env.VITE_PYTHON_API_BASE_URL;

const calculatedMatchupStats = async (parameters, token) => {
  const response = await axios.get(`${baseUrl}/calculatedmatchupstats`, 
    {
      params: parameters,
      headers: { Authorization: `Bearer ${token}` }
    });
  return response.data;
};

export default { calculatedMatchupStats };