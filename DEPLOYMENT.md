# Hosted fleet dashboard

The Render Blueprint in `render.yaml` configures a continuously running web service in Frankfurt, a 1 GB persistent disk for fleet records, a generated admin key, and a health check. Render supplies the public HTTPS URL; vehicles use that URL for their once-per-minute check-ins. Passenger stop requests remain local to each vehicle.

## Estimated hosting cost

The Blueprint uses Render's Starter web service and a 1 GB disk. Current published rates are approximately $7/month for the web service plus $0.25/GB/month for disk storage, or about **$7.25/month** before bandwidth overages. Render's free web services sleep after 15 minutes without traffic and cannot attach a persistent disk, so they are not suitable for this dashboard. Confirm the amount in Render before creating the service.

## Deploy

1. In Render, create a Blueprint from `Jehuru/stagecall` and select the `main` branch.
2. Review the service region, Starter plan, and 1 GB disk in Render's cost summary.
3. Create the service. Render generates `STAGECALL_ADMIN_KEY`; retrieve it from the service's environment settings and keep it private.
4. Open the deployed HTTPS URL. Sign in with the admin key and register each vehicle. Copy each generated vehicle token at registration time; it is shown once.
5. In each vehicle's local admin screen, enter the deployed HTTPS URL and its token. The vehicle server sends only screen connectivity, pending stop count, and uptime once per minute.

`fleet_data.json` is stored on the mounted disk and survives restarts and deploys. Do not add this file, `vehicle_config.json`, admin keys, or vehicle tokens to Git.

The service remains a small pilot deployment: it uses a single-instance JSON store and manual paid/due status. Before onboarding paying Saccos at scale, move the fleet records to a managed database and add scheduled invoices, backups, and admin user accounts.

