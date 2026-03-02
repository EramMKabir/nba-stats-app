/*

Success.jsx

Function: To display a success message.

Inputs:

message: A success message.

Output:

An HTML Line that displays a success message.

Time complexity: O(1), since the component sets a message in HTML.

Space complexity: O(1)

#################################################################################
# Date modified              Modifier             What was modified             #
# 03/16/2025                 Eram Kabir           Initial Development           #
# 08/13/2025                 Eram Kabir           Finalized V1.0                #
#################################################################################

*/

const Success = ({ message }) => {

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

    /* The success message
       is displayed as 
       an HTML line with
       CSS styling from
       the success block
       of CSS.
    */
  
    return (
      <div className="success">
        {message}
      </div>
    );
  };

export default Success;