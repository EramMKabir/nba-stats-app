/*

teamabbreviations.js

Function: To call the team abbreviations microservice in the backend.

Inputs:

token: The access token received from the OAuth exchange microservice.

Output:

List of dictionaries containing team abbreviations.

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

const teamAbbreviations = async (token) => {
  const response = await axios.get(`${baseUrl}/teamabbreviations`,
    {
      headers: { Authorization: `Bearer ${token}` }
    });
  return response.data;
};

export default { teamAbbreviations };