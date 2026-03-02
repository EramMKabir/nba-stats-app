/*

Error.jsx

Function: To display an error message.

Inputs:

message: An error message.

Output:

An HTML Line that displays an error message.

Time complexity: O(1), since the component sets a message in HTML.

Space complexity: O(1)

#################################################################################
# Date modified              Modifier             What was modified             #
# 03/16/2025                 Eram Kabir           Initial Development           #
# 08/13/2025                 Eram Kabir           Finalized V1.0                #
#################################################################################

*/

const Error = ({ message }) => {

    /* 
    Return if there is no message.
    This is needed since the
    component is loaded
    immediately upon going
    into the website, but
    the message is not.
    */

    if (message === null) {
      return null;
    };

    /* The error message
       is displayed as 
       an HTML line with
       CSS styling from
       the error block
       of CSS.
    */
  
    return (
      <div className="error">
        {message}
      </div>
    );
};

export default Error;