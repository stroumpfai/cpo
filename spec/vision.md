# Vision
the CPO web-application supports the so called Chief Pizza Officer in collecting the pizza order for the time before lunch time.

# Roles
There are two disctint roles with logins:
 - An administator can create new CPO roles
 - A CPO manages one team and can open / close the ordering session. It get a summary of the ordering

Further the team member, or end-user, do not need to login. They just get a link on the session where they can give in their order

# Session
Following is expected:
 - One team has only one ordering link. the link ist unique.
 - The session is open or closed based on the time setting given by the CPO.
   The CPO gives the date, start time and end time where the session will be open. After the end time, the session is automatically closed until a new start date, start time and end time is given.
 - If the session is active, the end-user can give his name, select the type and number of pizza he wants
 - If the session is inactive / closed, then the end-user gets an indication.
 - Only one session for a team exists at a give time, but multiple session can exists if there is multiple teams.
 
# Choice of Pizza
To manage the list of pizza, each CPO can:
 - edit his list by adding and removing pizza item.
 - each pizza is definied by a name and price.
 
# Summary
the CPO gets a summary of the session:
 - the summary is updated during the session at each new order and a last time when the session closes.
 - the summary provides two views:
   - a list per end-user name, type, number and total price for the distribution.
   - a list consolidated per type and number for the ordering at the pizzeria.
 - the summary remains upon a new session is opened. Then it resets.
 - the summary can be printed.
 
# Tech Stack
Following considerations:
  - responsive web application running in a single container.
  - admin password and list of CPO with their credentials are stored in a dedicated JSON configuration, mounted as volume
  - sessions and summaries are stored in a data volume of the container
 

