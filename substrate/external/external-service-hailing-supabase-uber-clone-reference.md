---
name: external-service-hailing-supabase-uber-clone-reference
type: reference
source: https://supabase.com/blog/flutter-uber-clone
source_sha: 5530018b53d788b0
fetched_at: 2026-07-28T10:48:43Z
last_verified: 2026-07-28
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: service-hailing-supabase-uber-clone-reference
---

## reference · service-hailing-supabase-uber-clone
* To build an Uber-like application, you need Flutter installed and a Supabase account.
* Basic knowledge of Dart and Flutter is required.
* The `google_maps_flutter` package is used to display the map, `geolocator` for GPS information, `duration` to parse duration values, and `intl` to display currencies.
* The `supabase_flutter` package version should be `^2.5.9` or higher.
* To configure Google Maps, follow the instructions in the `google_maps_flutter` package's `readme.md` file.
* The `postgis` extension is required for Postgres to handle geography data efficiently.
* Two tables are needed: `drivers` and `rides`, with specific columns for each.
* Row level security policies should be set for the tables to secure the database.
* Database functions and triggers are needed to update the driver status and find available drivers.
* The `find_driver` function finds the closest available driver within a 3000m radius.
* The app has five different states: choosing location, confirming fare, waiting for pickup, riding, and post-ride.
* The `UberCloneMainScreen` widget manages the different app states.
* The `GoogleMapController` is used to manage the map, and the `CameraPosition` is set to a default location.
* The `LatLng` class is used to represent locations, and the `Polyline` and `Marker` classes are used to draw on the map.
* The `_fare` variable stores the fare in cents, and the `_driverSubscription` and `_rideSubscription` variables store the subscriptions to the driver and ride updates.
* The `_loadIcons` method loads the pin and car icons for the map.
* The `_signInIfNotSignedIn` method signs in the user if they are not already signed in, and the `_checkLocationPermission` method checks for location permission.
* The `_cancelSubscriptions` method cancels the subscriptions to the driver and ride updates when the app is disposed.
* The `AppBar` title is set based on the current app state.
* The `GoogleMap` widget is used to display the map, and the `onMapCreated` callback is used to set the `_mapController`.
* The `onCameraMove` callback is used to update the map when the camera moves.
* The `polylines` and `markers` properties of the `GoogleMap` widget are used to draw on the map.
Sources: https://supabase.com/blog/flutter-uber-clone
