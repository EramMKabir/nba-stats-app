/*

OAuthLogin.jsx

Function: To initiate OAuth login.

Inputs:

None.

Output:

None

Time complexity: O(1)

Space complexity: O(1)

###################################################################################
# Date modified              Modifier             What was modified               #
# 01/10/2026                 Eram Kabir           Initial and final Development   #
###################################################################################

*/

/* 
All this component does is 
redirect the user to the OAuth 
login page on the backend. 
*/

export default function OAuthLogin() {
  const startLogin = async () => {
    const baseUrl = import.meta.env.VITE_PYTHON_API_BASE_URL;
    window.location.href = `${baseUrl}/oauth/login`;
  };

  return (
    <button onClick={startLogin}>
      Login with Google
    </button>
  );
};