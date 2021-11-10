phile
=====

(Not for public consumption.
This is an over-engineered mess of a codebase.
The only reason it is still here is because I use it.)

A file-based notification management.

Based on the idea that "everything is a file",
users can create files in specific directories
to request notifications to be displayed.
Deleting the files removes the notifications.
File content is treated as notification text,
An empty notification directory would mean there are no notifications.
