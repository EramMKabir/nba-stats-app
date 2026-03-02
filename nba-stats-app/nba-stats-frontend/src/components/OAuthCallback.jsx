/*

OAuthCallback.jsx

Function: To handle OAuth callback and set session data.

Inputs:

None.

Output:

None

Time complexity: O(n), where n is the number of characters in the URL query string.

Space complexity: O(n)

###################################################################################
# Date modified              Modifier             What was modified               #
# 01/10/2026                 Eram Kabir           Initial and final Development   #
###################################################################################

*/

/* Libraries and Functions */

import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import exchangeService from "../services/exchange";
import { useAuth } from "../context/authContext";

/*
This function calls the exchange service to exchange
the OAuth code for a session ID, then
calls the session service to get the
session data using that session ID.
It then sets the token and user in
the auth context and navigates to
the home page.

The main purpose of this function is
to finish logging the user in via OAuth,
upon which the user can access the
site and its functionality.
*/

export default function OAuthCallback() {
  const location = useLocation();
  const navigate = useNavigate();
  const { token, setToken, setUser } = useAuth();
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const code = params.get("code");
    const state = params.get("state");
    if (code && state) {
        const performExchange = async () => {
            let res = {};
            try {
                res = await exchangeService.exchange(code, state);
            } catch (error) {
                console.error("OAuth Exchange error: ", error);
            }
            return res;
        };
        const setSession = async () => {
            if (token) {
                return;
            };
            const res = await performExchange();
            setToken(res.data.token);
            setUser(res.data.user);
            window.history.replaceState({}, document.title, window.location.pathname);
            navigate('/');
        };
        setSession();
    };
  }, [location.search]);
  
  return null;
};