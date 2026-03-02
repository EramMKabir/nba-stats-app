/*

teams.js

Function: To call the teams microservice in the backend.

Inputs:

token: The access token received from the OAuth exchange microservice.

state: The state parameter to prevent CSRF attacks.

Output:

List of dictionaries containing team abbreviations for upcoming games.

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

const upcomingGameTeams = async (token) => {
  const response = await axios.get(`${baseUrl}/upcominggameteams`,
    {
      headers: { Authorization: `Bearer ${token}` }
    });
  return response.data;
};

export default { upcomingGameTeams };