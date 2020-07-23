System Design
=============

1. Build on Django admin
------------------------
Why using the admin?

It's much simpler especially around CRUD intensive apps (like ERPs).
* With just one class you can manage all CRUD operations.
* Easily have your url named and reversed
* Multiple Formsets support out of the box.
* It's unified, no need to learn new terminologies. If you worked with the admin you'll know your way around here.
* Admin goodies (list filter, auto form generation, save and continue, save and add new buttons, discovery of related objects that would get deleted)
* Out of the box permissions handling

Now, imagine having to write all of this, again, in class based views.. that's a pain that no one should face.


"But the admin should be for site admins only."

Well, that's an old phrase that gets passed around which i dont find convincing enough.
Maybe it was true in the old days; But now, you dont have to be a `staff` member to be able to log in an admin dashboard.
Also, Ra dashboard is a custom admin site (independent from your typical admin).

2- Reporting
------------

Reporting itself was moved from this package to be an independent package.
However, this package still hold the report organization and menu generation.




Ra Components
--------------

1. Base Models

2. Admin Models

3. Report Registry

4. Front End Report/Widget Loader
