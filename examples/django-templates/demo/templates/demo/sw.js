{% load static %}// The app's own service worker. Caching and offline pages would go here too.
// --8<-- [start:import]
importScripts("{% static 'kvn_notify/sw.js' %}");
// --8<-- [end:import]
